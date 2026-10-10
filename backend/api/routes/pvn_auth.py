from __future__ import annotations

import secrets

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.routes.auth import issue_token
from backend.auth.oidc import OIDCValidationError, oidc_settings_from, synchronize_candidate, validate_bearer
from backend.auth.security import decode_access_token, hash_password
from backend.core.config import get_settings
from backend.models import CandidateProfile, User

router = APIRouter()


class PVNExchangeRequest(BaseModel):
    access_token: str = Field(min_length=1, max_length=16384)
    consent_accepted: bool


class PvnExchangeResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    created: bool
    enriched_achievements: int


@router.post("/pvn", response_model=PvnExchangeResponse)
def exchange_pvn_token(
    request: PVNExchangeRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    settings = get_settings()
    try:
        config = oidc_settings_from(settings)
        if config is None:
            raise OIDCValidationError("OIDC is not configured")
        claims = validate_bearer(request.access_token, config)
    except OIDCValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный PVN токен") from exc
    if not request.consent_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Требуется согласие на обработку персональных данных (152-ФЗ)")
    issuer_column = getattr(User, "oidc_issuer", None)
    subject_column = getattr(User, "oidc_subject", None)
    if issuer_column is None or subject_column is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Внешняя идентичность не настроена")
    local_user = None
    if authorization:
        scheme, _, local_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not local_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный локальный токен")
        try:
            local_claims = decode_access_token(
                local_token,
                settings.jwt_secret,
                settings.jwt_algorithm,
                settings.jwt_issuer,
            )
            if "exp" not in local_claims:
                raise jwt.InvalidTokenError("Token expiration is required")
            local_user = db.get(User, int(local_claims["sub"]))
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный локальный токен")
        if local_user is None or local_user.role != "candidate" or not local_user.is_email_confirmed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуется подтверждённый профиль кандидата")
    user = db.query(User).filter(issuer_column == config.issuer, subject_column == claims["sub"]).with_for_update().one_or_none()
    if local_user is not None and user is not None and user.id != local_user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PVN учётная запись уже связана с другим профилем")
    if local_user is not None and user is None:
        if local_user.oidc_issuer is not None or local_user.oidc_subject is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Профиль уже связан с другой PVN учётной записью")
        user = local_user
        user.oidc_issuer = config.issuer
        user.oidc_subject = claims["sub"]
    created = user is None
    if user is None:
        if claims.get("email_verified") is not True:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется подтверждённый email или вход в локальный профиль")
        try:
            email = str(TypeAdapter(EmailStr).validate_python(claims.get("email")))
        except ValidationError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный подтверждённый email")
        if db.query(User).filter(User.email == email).first() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Войдите в локальный профиль, чтобы связать PVN учётную запись")
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="candidate",
            consent_accepted=True,
            is_email_confirmed=True,
            oidc_issuer=config.issuer,
            oidc_subject=claims["sub"],
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Учётная запись уже связана. Повторите вход") from exc
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    elif user.role != "candidate" or not user.is_email_confirmed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Внешняя учётная запись не является профилем кандидата")
    else:
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).one_or_none()
        if profile is None:
            profile = CandidateProfile(user_id=user.id)
            db.add(profile)
            db.flush()
    try:
        enriched = synchronize_candidate(db, user, claims, settings)
        db.commit()
    except OIDCValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительные данные ПВН") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Учётная запись уже связана. Повторите вход") from exc
    return PvnExchangeResponse(
        access_token=issue_token(user).access_token,
        role=user.role,
        created=created,
        enriched_achievements=enriched,
    )
