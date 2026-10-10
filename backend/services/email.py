import smtplib
from email.message import EmailMessage

from backend.core.config import get_settings


def confirmation_url(token: str) -> str:
    settings = get_settings()
    return f"{settings.app_base_url}/auth/confirm/{token}"


def send_confirmation_email(to_email: str, token: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_user
    message["To"] = to_email
    message["Subject"] = "Подтверждение регистрации syntax"
    message.set_content(f"Перейдите по ссылке для подтверждения: {confirmation_url(token)}")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
    return True
