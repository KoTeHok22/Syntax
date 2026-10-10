import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

test_database = Path(tempfile.gettempdir()) / f"syntax-test-{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_database.as_posix()}"
os.environ.setdefault("SMTP_HOST", "")
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_MODEL"] = "test-model"
os.environ["SEED_DEMO"] = "0"
os.environ["EMBEDDING_BASE_URL"] = ""
os.environ["EMBEDDING_API_KEY"] = ""
os.environ["EMBEDDING_MODEL"] = ""
os.environ.pop("LLM_VISION_MODEL", None)


@pytest.fixture(autouse=True)
def isolate_vision_config(monkeypatch):
    from backend.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "llm_vision_model", "", raising=False)


@pytest.fixture(autouse=True)
def isolate_embedding_network(monkeypatch):
    from backend.services.embeddings import StubEmbeddingClient

    monkeypatch.setattr("backend.services.embeddings.get_embedding_client", lambda: StubEmbeddingClient())


@pytest.fixture()
def client():
    from backend.db import Base, engine
    from backend.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def seed_grade(email: str, grade: str, specialization: str) -> None:
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, User
    from backend.core.categorization import assign_category

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).first()
        profile.grade = grade
        if specialization:
            profile.specialization = specialization
        assign_category(db, profile, profile.specialization or specialization, grade)
        db.commit()
    finally:
        db.close()
