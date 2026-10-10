import hashlib
import hmac
import ipaddress
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.models import Application, EmployerProfile, TestSession, Vacancy
from backend.services.embeddings import cosine_similarity
from backend.services.semantic_matching import candidate_embedding_text, embedding_is_current, vacancy_embedding_text


def validate_webhook_url(url: str) -> str:
    settings = get_settings()
    if not url or url != url.strip() or url not in settings.ats_allowed_webhook_urls:
        raise HTTPException(422, "Адрес ATS не разрешен администратором. Обратитесь к администратору для подключения.")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or parsed.port not in (None, 443)
                or "\\" in url or any(ord(char) < 33 or ord(char) == 127 for char in url)):
            raise ValueError
        hostname = parsed.hostname.casefold().rstrip(".")
        if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError
    except ValueError:
        raise HTTPException(422, "Для ATS требуется разрешенный публичный HTTPS-адрес без перенаправлений.")
    return url


def deliver_application(db: Session, application_id: int, employer_profile_id: int) -> dict:
    application = (
        db.query(Application)
        .join(Vacancy, Application.vacancy_id == Vacancy.id)
        .filter(Application.id == application_id, Vacancy.employer_profile_id == employer_profile_id)
        .with_for_update(of=Application)
        .populate_existing()
        .first()
    )
    if application is None:
        raise HTTPException(404, "Отклик не найден")
    if application.status != "accepted":
        raise HTTPException(409, "В ATS можно передать только принятый отклик.")
    employer = db.get(EmployerProfile, employer_profile_id)
    if application.ats_delivery_status == "delivered":
        return delivery_response(application)
    if not employer.ats_webhook_url:
        return {"application_id": application.id, "status": "not_configured", "attempts": application.ats_delivery_attempts,
                "error": "Подключите ATS перед отправкой отклика."}
    try:
        url = validate_webhook_url(employer.ats_webhook_url)
    except HTTPException:
        application.ats_delivery_status = "failed"
        application.ats_delivery_error = "Адрес ATS больше не разрешен. Обновите настройки подключения."
        db.commit()
        return delivery_response(application)
    settings = get_settings()
    application.ats_delivery_attempts += 1
    try:
        from backend.api.routes.candidates import build_card

        candidate = application.candidate_profile
        vacancy = application.vacancy
        similarity = None
        if (embedding_is_current(candidate, candidate_embedding_text(candidate))
                and embedding_is_current(vacancy, vacancy_embedding_text(vacancy))):
            similarity = cosine_similarity(list(candidate.embedding), list(vacancy.embedding))
        card = build_card(db, candidate, vacancy.stack or [], similarity)
        completed_tests = (db.query(TestSession).filter(
            TestSession.candidate_profile_id == candidate.id, TestSession.status == "completed",
        ).order_by(TestSession.completed_at.desc(), TestSession.id.desc()).limit(50).all())
        event_id = f"syntax.application.accepted:{application.id}"
        payload = {
            "event": "application.accepted", "event_id": event_id,
            "application": {"id": application.id, "status": application.status, "message": application.message},
            "vacancy": {"id": vacancy.id, "title": vacancy.title},
            "candidate": {
                "id": candidate.id, "full_name": candidate.full_name, "contacts": candidate.contacts or {},
                "grade": candidate.grade, "specialization": candidate.specialization, "stack": candidate.stack or [],
                "score": card.score, "score_breakdown": card.score_breakdown,
                "match_relevance": card.match_relevance, "final_score": card.final_score,
                "match_breakdown": card.match_breakdown,
                "completed_tests": [
                    {"id": session.id, "grade": session.grade, "result_score": session.result_score,
                     "verdict": session.verdict,
                     "completed_at": session.completed_at.isoformat() if session.completed_at else None}
                    for session in completed_tests
                ],
            },
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Idempotency-Key": event_id}
        if settings.ats_webhook_secret:
            headers["X-Syntax-Signature"] = "sha256=" + hmac.new(
                settings.ats_webhook_secret.encode("utf-8"), body, hashlib.sha256,
            ).hexdigest()
        timeout = max(0.1, min(float(settings.ats_timeout_seconds), 10.0))
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.post(url, content=body, headers=headers)
        if not 200 <= response.status_code < 300:
            raise httpx.HTTPStatusError("ATS delivery failed", request=response.request, response=response)
        application.ats_delivery_status = "delivered"
        application.ats_delivery_error = None
        application.ats_delivered_at = datetime.now(timezone.utc)
    except Exception:
        application.ats_delivery_status = "failed"
        application.ats_delivery_error = "ATS не подтвердил получение. Повторите отправку."
    db.commit()
    return delivery_response(application)


def delivery_response(application: Application) -> dict:
    return {"application_id": application.id, "status": application.ats_delivery_status,
            "attempts": application.ats_delivery_attempts, "error": application.ats_delivery_error}
