from typing import Generator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.auth.oidc import OIDCValidationError, oidc_settings_from, synchronize_candidate, validate_bearer
from backend.auth.security import decode_access_token
from backend.core.config import get_settings
from backend.db import SessionLocal
from backend.models import CandidateProfile, EmployerProfile, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    try:
        if len(token) > 16384:
            raise jwt.InvalidTokenError("Token exceeds limits")
        payload = decode_access_token(token, settings.jwt_secret, settings.jwt_algorithm, settings.jwt_issuer)
        if "exp" not in payload:
            raise jwt.InvalidTokenError("Token expiration is required")
        user = db.get(User, int(payload["sub"]))
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        try:
            oidc_config = oidc_settings_from(settings)
            if oidc_config is None:
                raise OIDCValidationError("OIDC is not configured")
            payload = validate_bearer(token, oidc_config)
            issuer = payload["iss"]
            subject = payload["sub"]
            issuer_column = getattr(User, "oidc_issuer", None)
            subject_column = getattr(User, "oidc_subject", None)
            if issuer_column is None or subject_column is None:
                raise OIDCValidationError("External identity storage is not configured")
            user = db.query(User).filter(issuer_column == issuer, subject_column == subject).with_for_update().one_or_none()
            if user is not None and user.is_email_confirmed and user.role == "candidate":
                synchronize_candidate(db, user, payload, settings)
                db.commit()
        except (OIDCValidationError, jwt.InvalidTokenError, ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Профиль обновляется. Повторите запрос")
    if user is None or not user.is_email_confirmed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден или email не подтверждён")
    return user


def require_candidate(user: User = Depends(get_current_user)) -> User:
    if user.role != "candidate":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для кандидатов")
    return user


def require_employer(user: User = Depends(get_current_user)) -> User:
    if user.role != "employer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ только для работодателей")
    return user


def get_candidate_profile(user: User = Depends(require_candidate), db: Session = Depends(get_db)) -> CandidateProfile:
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль кандидата не найден")
    return profile


def get_employer_profile(user: User = Depends(require_employer), db: Session = Depends(get_db)) -> EmployerProfile:
    profile = db.query(EmployerProfile).filter(EmployerProfile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль работодателя не найден")
    return profile
