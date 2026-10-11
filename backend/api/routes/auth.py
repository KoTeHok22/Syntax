import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user, get_db
from backend.auth.security import create_access_token, hash_password, verify_password
from backend.core.categorization import assign_category
from backend.core.config import get_settings
from backend.models import CandidateProfile, EmployerProfile, User
from backend.schemas.auth import (
    EmailConfirmResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)
from backend.services.email import send_confirmation_email

router = APIRouter()


def issue_token(user: User) -> TokenResponse:
    settings = get_settings()
    access_token = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        pvn_id=user.pvn_id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expires_minutes,
        issuer=settings.jwt_issuer,
    )
    return TokenResponse(access_token=access_token, role=user.role)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if not request.consent_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Требуется согласие на обработку персональных данных (152-ФЗ)")
    if db.query(User).filter(User.email == request.email).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email уже зарегистрирован")
    if request.pvn_id is not None and db.query(User).filter(User.pvn_id == request.pvn_id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Этот ПВН ID уже привязан к другому аккаунту")
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        consent_accepted=True,
        pvn_id=request.pvn_id,
        email_confirmation_token=secrets.token_urlsafe(32),
    )
    db.add(user)
    db.flush()
    category_id = None
    if request.role == "candidate":
        profile = CandidateProfile(user_id=user.id, specialization=request.specialization or "")
        db.add(profile)
        db.flush()
        if request.specialization and request.grade:
            profile.grade = request.grade
            profile.grade_changed_at = datetime.now(timezone.utc)
            category_id = assign_category(db, profile, request.specialization, request.grade).id
    else:
        db.add(EmployerProfile(user_id=user.id))
    db.commit()
    delivered = send_confirmation_email(user.email, user.email_confirmation_token)
    from backend.services.email import confirmation_url

    return RegisterResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_email_confirmed=user.is_email_confirmed,
        confirmation_url=None if delivered else confirmation_url(user.email_confirmation_token),
        category_id=category_id,
    )


@router.get("/confirm/{token}", response_model=EmailConfirmResponse)
def confirm_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_confirmation_token == token).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Токен подтверждения не найден")
    user.is_email_confirmed = True
    user.email_confirmation_token = None
    db.commit()
    return EmailConfirmResponse(email=user.email, is_email_confirmed=True)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username).first()
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    if not user.is_email_confirmed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Подтвердите email перед входом")
    return issue_token(user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
