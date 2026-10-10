from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db, get_employer_profile
from backend.models import EmployerProfile
from backend.services.ats import deliver_application, validate_webhook_url
from backend.core.config import get_settings

router = APIRouter()


class ATSConfiguration(BaseModel):
    webhook_url: str | None = Field(default=None, max_length=2048)
    available_webhook_urls: list[str] = Field(default_factory=list)
    configured: bool = False
    available: bool = False


class ATSDeliveryRequest(BaseModel):
    application_id: int = Field(gt=0)


@router.get("/ats/config", response_model=ATSConfiguration)
def get_configuration(employer_profile: EmployerProfile = Depends(get_employer_profile)):
    urls = get_settings().ats_allowed_webhook_urls
    return ATSConfiguration(webhook_url=employer_profile.ats_webhook_url, available_webhook_urls=urls,
                            configured=bool(employer_profile.ats_webhook_url), available=bool(urls))


@router.put("/ats/config", response_model=ATSConfiguration)
def update_configuration(
    request: ATSConfiguration,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    employer_profile.ats_webhook_url = validate_webhook_url(request.webhook_url) if request.webhook_url else None
    db.commit()
    return get_configuration(employer_profile)


@router.post("/ats/webhook")
def retry_delivery(
    request: ATSDeliveryRequest,
    db: Session = Depends(get_db),
    employer_profile: EmployerProfile = Depends(get_employer_profile),
):
    return deliver_application(db, request.application_id, employer_profile.id)
