import pytest
from types import SimpleNamespace

from backend.models import CandidateProfile, Vacancy
from backend.services.semantic_matching import (
    candidate_embedding_text,
    relevance_breakdown,
    stack_intersection,
    vacancy_embedding_text,
)


def test_stack_intersection_is_case_insensitive():
    assert stack_intersection(["Airflow", "Kafka"], ["airflow", "ETL"]) == 0.5


def test_stack_intersection_splits_multi_word_requirements():
    assert stack_intersection(["airflow", "kafka"], ["kafka airflow"]) == 1.0
    assert stack_intersection(["airflow"], ["kafka airflow"]) == 0.5
    assert stack_intersection(["airflow"], ["airflow, kafka"]) == 0.5
    assert stack_intersection(["airflow", "kafka"], ["airflow,kafka"]) == 1.0


def test_relevance_uses_semantic_similarity_when_available():
    result = relevance_breakdown(["Airflow"], ["ETL"], 0.8)
    assert result["mode"] == "semantic"
    assert result["relevance"] == pytest.approx(0.56)


def test_relevance_falls_back_to_lexical_when_embedding_is_unavailable():
    result = relevance_breakdown(["Airflow"], ["ETL"], None)
    assert result["mode"] == "lexical"
    assert result["relevance"] == 0.0


def test_embedding_text_contains_resume_and_assessment():
    candidate = CandidateProfile(
        specialization="data",
        stack=["Airflow"],
        soft_skills=["communication"],
        resume_text="Built ETL pipelines",
        assessment_text="Designed a resilient DAG",
    )
    text = candidate_embedding_text(candidate)
    assert "Built ETL pipelines" in text
    assert "Designed a resilient DAG" in text


def test_vacancy_embedding_text_contains_job_context():
    vacancy = Vacancy(title="Data engineer", description="Build event pipelines", specialization="data", stack=["Kafka"])
    text = vacancy_embedding_text(vacancy)
    assert "Build event pipelines" in text
    assert "Kafka" in text


@pytest.mark.asyncio
async def test_changed_text_clears_stale_vector_when_provider_fails(monkeypatch):
    from backend.services.semantic_matching import index_candidate

    candidate = CandidateProfile(specialization="data", stack=["Airflow"], soft_skills=[],
                                 embedding=[1.0] + [0.0] * 1023, embedding_text="old", embedding_model="bge")
    settings = SimpleNamespace(embeddings_enabled=True, embedding_model="bge", embedding_dimensions=1024)
    monkeypatch.setattr("backend.services.semantic_matching.get_settings", lambda: settings)

    async def empty(texts):
        return []

    monkeypatch.setattr("backend.services.semantic_matching.embed_texts", empty)
    assert await index_candidate(candidate) is False
    assert candidate.embedding is None
    assert candidate.embedding_text is None


@pytest.mark.asyncio
async def test_index_candidate_rejects_malformed_vectors(monkeypatch):
    from backend.services.semantic_matching import index_candidate

    candidate = CandidateProfile(specialization="data", stack=["Airflow"], soft_skills=[])
    settings = SimpleNamespace(embeddings_enabled=True, embedding_model="bge", embedding_dimensions=1024)
    monkeypatch.setattr("backend.services.semantic_matching.get_settings", lambda: settings)

    async def malformed(texts):
        return [[float("nan")] * 1024]

    monkeypatch.setattr("backend.services.semantic_matching.embed_texts", malformed)
    assert await index_candidate(candidate) is False
    assert candidate.embedding is None


def test_vacancy_search_finds_semantic_candidate_without_stack_overlap(client, monkeypatch):
    from tests.test_api import auth, register_and_login
    from backend.db import SessionLocal
    from backend.models import User

    employer = register_and_login(client, "semantic-employer@example.com", "employer")
    candidate_token = register_and_login(client, "semantic-data@example.com", "candidate")
    client.put("/candidates/me", headers=auth(candidate_token), json={"stack": ["Airflow", "Kafka"], "specialization": "data"})
    db = SessionLocal()
    user = db.query(User).filter_by(email="semantic-data@example.com").one()
    candidate_id = db.query(CandidateProfile).filter_by(user_id=user.id).one().id
    db.close()
    vacancy = client.post("/vacancies", headers=auth(employer), json={"title": "Data engineer", "description": "Build resilient event pipelines",
                           "stack": ["ETL"], "specialization": "data", "salary_from": 100000, "salary_to": 200000}).json()

    async def similarities(db, vacancy, candidates):
        return {candidate_id: 0.9}

    monkeypatch.setattr("backend.api.routes.candidates.vacancy_similarities", similarities)
    response = client.get("/employer/search", headers=auth(employer), params={"vacancy_id": vacancy["id"]})
    assert response.status_code == 200
    card = next(card for card in response.json() if card["candidate_profile_id"] == candidate_id)
    assert card["match_relevance"] == pytest.approx(0.63)
    assert card["match_breakdown"]["mode"] == "semantic"
    other_employer = register_and_login(client, "semantic-other@example.com", "employer")
    assert client.get("/employer/search", headers=auth(other_employer), params={"vacancy_id": vacancy["id"]}).status_code == 404


def test_empty_session_cannot_assign_grade(client):
    from tests.test_api import auth, register_and_login

    token = register_and_login(client, "empty-task@example.com", "candidate")
    response = client.post("/test-sessions", json={"grade": "senior"}, headers=auth(token))
    assert response.status_code == 409
    assert client.get("/candidates/me", headers=auth(token)).json()["grade"] is None


def test_duplicate_answers_cannot_inflate_test_score(client):
    from tests.test_api import auth, register_and_login
    from backend.db import SessionLocal
    from backend.models import Concept, Task

    token = register_and_login(client, "duplicate-task@example.com", "candidate")
    db = SessionLocal()
    db.add(Concept(name="proof", domain="backend", grade="middle", question_template="Choose correct value",
                   correct_answer="correct", distractors=["incorrect"]))
    db.commit()
    session = client.post("/test-sessions", json={"grade": "middle"}, headers=auth(token)).json()
    task_id = session["tasks"][0]["id"]
    task = db.get(Task, task_id)
    answer = {"task_id": task_id, "option_index": task.reference_answer}
    db.close()
    response = client.post(f"/test-sessions/{session['id']}/answers", headers=auth(token), json=[answer, answer])
    assert response.status_code == 400
    assert client.get("/candidates/me", headers=auth(token)).json()["grade"] is None
