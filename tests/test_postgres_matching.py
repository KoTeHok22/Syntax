import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, defer

from backend.models import CandidateProfile, EmployerProfile, User, Vacancy
from backend.services import semantic_matching


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture(scope="module")
def postgres_engine():
    url = make_url(POSTGRES_URL)
    assert url.get_backend_name() == "postgresql"
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            vector_columns = connection.execute(text(
                "SELECT c.relname, format_type(a.atttypid, a.atttypmod) "
                "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.oid IN (to_regclass('candidate_profiles'), to_regclass('vacancies')) "
                "AND a.attname = 'embedding' AND NOT a.attisdropped"
            )).all()
            assert dict(vector_columns) == {
                "candidate_profiles": "vector(1024)",
                "vacancies": "vector(1024)",
            }
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def postgres_session(postgres_engine):
    connection = postgres_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    session.begin_nested()
    try:
        yield session
    finally:
        try:
            session.close()
        finally:
            try:
                outer_transaction.rollback()
            finally:
                connection.close()
        with Session(postgres_engine) as verification_session:
            for model, row_ids in session.info.get("ephemeral_rows", []):
                assert verification_session.scalar(select(model.id).where(model.id.in_(row_ids))) is None


@pytest.fixture()
def matching_entities(postgres_session):
    suffix = uuid.uuid4().hex
    user = User(
        email=f"pgvector-{suffix}@example.com",
        password_hash="test",
        role="candidate",
        consent_accepted=True,
    )
    employer_user = User(
        email=f"pgvector-employer-{suffix}@example.com",
        password_hash="test",
        role="employer",
        consent_accepted=True,
    )
    postgres_session.add_all([user, employer_user])
    postgres_session.flush()
    postgres_session.info["ephemeral_rows"] = [(User, [user.id, employer_user.id])]

    employer = EmployerProfile(user_id=employer_user.id, company_name="Ephemeral employer")
    candidate = CandidateProfile(
        user_id=user.id,
        full_name="Ephemeral candidate",
        specialization="backend",
        stack=["rust"],
        soft_skills=[],
        contacts={},
    )
    postgres_session.add_all([employer, candidate])
    postgres_session.flush()
    postgres_session.info["ephemeral_rows"].extend([
        (EmployerProfile, [employer.id]), (CandidateProfile, [candidate.id])
    ])

    vacancy = Vacancy(
        employer_profile_id=employer.id,
        title="PostgreSQL vector engineer",
        description="Build reliable data services",
        specialization="backend",
        stack=["python"],
        grade="middle",
        salary_from=100,
        salary_to=200,
    )
    postgres_session.add(vacancy)
    postgres_session.flush()
    postgres_session.info["ephemeral_rows"].append((Vacancy, [vacancy.id]))
    return vacancy, candidate


def vector(axis: int) -> list[float]:
    values = [0.0] * 1024
    values[axis] = 1.0
    return values


@pytest.fixture()
def deterministic_embeddings(monkeypatch):
    settings = SimpleNamespace(
        embeddings_enabled=True, embedding_model="test-model", embedding_dimensions=1024
    )
    monkeypatch.setattr(semantic_matching, "get_settings", lambda: settings)

    async def embed_texts(texts):
        return [vector(1 if "Unrelated illustration work" in value else 0) for value in texts]

    monkeypatch.setattr(semantic_matching, "embed_texts", embed_texts)
    return settings


@pytest.mark.asyncio
async def test_vacancy_similarities_uses_pgvector_cosine_sql_without_contacts(
    postgres_session, matching_entities, deterministic_embeddings, monkeypatch
):
    vacancy, candidate = matching_entities
    candidate_id = candidate.id
    postgres_session.expunge(candidate)
    candidate = postgres_session.scalars(
        select(CandidateProfile).where(CandidateProfile.id == candidate_id)
        .options(defer(CandidateProfile.contacts, raiseload=True))
    ).one()
    statements = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def forbid_python_cosine(*args):
        pytest.fail("The PostgreSQL branch must execute pgvector SQL, not Python cosine")

    monkeypatch.setattr(semantic_matching, "cosine_similarity", forbid_python_cosine)
    event.listen(postgres_session.bind, "before_cursor_execute", record_statement)
    try:
        similarities = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])
    finally:
        event.remove(postgres_session.bind, "before_cursor_execute", record_statement)

    assert postgres_session.bind.dialect.name == "postgresql"
    assert similarities[candidate.id] == pytest.approx(1.0)
    cosine_statements = [statement for statement in statements if "<=>" in statement]
    assert len(cosine_statements) == 1
    assert "contacts" not in cosine_statements[0]
    assert semantic_matching.stack_intersection(candidate.stack, vacancy.stack) == 0.0
    assert candidate.stack == ["rust"]
    assert set(similarities) == {candidate.id}
    breakdown = semantic_matching.relevance_breakdown(candidate.stack, vacancy.stack, similarities[candidate.id])
    assert breakdown["mode"] == "semantic"
    assert breakdown["relevance"] == pytest.approx(0.7)


@pytest.mark.asyncio
@pytest.mark.parametrize("coordinates, expected", [([3.0, 4.0], 0.6), ([-1.0, 0.0], 0.0)])
async def test_pgvector_cosine_normalizes_vectors_and_clamps_negative_similarity(
    postgres_session, matching_entities, deterministic_embeddings, monkeypatch, coordinates, expected
):
    vacancy, candidate = matching_entities
    candidate_text = semantic_matching.candidate_embedding_text(candidate)

    async def embed_texts(texts):
        return [coordinates + [0.0] * 1022 if value == candidate_text else vector(0) for value in texts]

    monkeypatch.setattr(semantic_matching, "embed_texts", embed_texts)
    similarities = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])

    assert similarities[candidate.id] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_current_embeddings_are_reused_after_postgresql_reload(
    postgres_session, matching_entities, deterministic_embeddings, monkeypatch
):
    vacancy, candidate = matching_entities
    expected = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])
    postgres_session.refresh(vacancy)
    postgres_session.refresh(candidate)

    async def forbid_embedding_request(texts):
        pytest.fail("Current stored embeddings must be reused without an embedding request")

    monkeypatch.setattr(semantic_matching, "embed_texts", forbid_embedding_request)

    assert await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate]) == expected


@pytest.mark.asyncio
async def test_semantic_mismatch_without_stack_overlap(
    postgres_session, matching_entities, deterministic_embeddings
):
    vacancy, candidate = matching_entities
    candidate.resume_text = "Unrelated illustration work"

    similarities = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])

    assert similarities == {candidate.id: pytest.approx(0.0)}
    assert semantic_matching.stack_intersection(candidate.stack, vacancy.stack) == 0.0
    breakdown = semantic_matching.relevance_breakdown(candidate.stack, vacancy.stack, similarities[candidate.id])
    assert breakdown["mode"] == "semantic"
    assert breakdown["relevance"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_stale_cache_and_model_mismatch_are_replaced(
    postgres_session, matching_entities, deterministic_embeddings
):
    vacancy, candidate = matching_entities
    candidate.embedding = vector(1)
    candidate.embedding_text = "stale text"
    candidate.embedding_model = "test-model"
    postgres_session.flush()

    assert await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate]) == {
        candidate.id: pytest.approx(1.0)
    }
    assert candidate.embedding_text == semantic_matching.candidate_embedding_text(candidate)
    assert candidate.embedding_model == "test-model"
    assert candidate.embedding == vector(0)

    candidate.embedding_model = "different-model"
    postgres_session.flush()

    assert await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate]) == {
        candidate.id: pytest.approx(1.0)
    }
    assert candidate.embedding_model == "test-model"
    assert candidate.embedding == vector(0)

    vacancy.embedding = vector(0)
    vacancy.embedding_text = "stale vacancy text"
    vacancy.embedding_model = "different-model"
    postgres_session.flush()

    similarities = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])

    assert similarities[candidate.id] == pytest.approx(1.0)
    assert vacancy.embedding_text == semantic_matching.vacancy_embedding_text(vacancy)
    assert vacancy.embedding_model == "test-model"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalidation", ["text", "model"])
async def test_stale_candidate_cache_is_cleared_when_embeddings_are_unavailable(
    postgres_session, matching_entities, deterministic_embeddings, monkeypatch, invalidation
):
    vacancy, candidate = matching_entities
    await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])
    if invalidation == "text":
        candidate.resume_text = "Changed experience"
    else:
        candidate.embedding_model = "different-model"
    postgres_session.flush()
    requests = []

    async def unavailable(texts):
        requests.extend(texts)
        return []

    monkeypatch.setattr(semantic_matching, "embed_texts", unavailable)
    similarities = await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])

    assert requests == [semantic_matching.candidate_embedding_text(candidate)]
    assert similarities == {}
    postgres_session.refresh(candidate)
    assert candidate.embedding is None
    assert candidate.embedding_text is None
    assert candidate.embedding_model is None
    assert semantic_matching.embedding_is_current(vacancy, semantic_matching.vacancy_embedding_text(vacancy))


@pytest.mark.asyncio
async def test_stale_vacancy_cache_is_cleared_when_embeddings_are_unavailable(
    postgres_session, matching_entities, deterministic_embeddings, monkeypatch
):
    vacancy, candidate = matching_entities
    await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate])
    vacancy.description = "Changed vacancy requirements"
    vacancy.embedding_model = "different-model"

    async def unavailable(texts):
        return []

    monkeypatch.setattr(semantic_matching, "embed_texts", unavailable)
    assert await semantic_matching.vacancy_similarities(postgres_session, vacancy, [candidate]) == {}
    postgres_session.refresh(vacancy)
    assert vacancy.embedding is None
    assert vacancy.embedding_text is None
    assert vacancy.embedding_model is None


def test_session_commit_keeps_ephemeral_rows_inside_outer_transaction(postgres_session, matching_entities):
    vacancy, candidate = matching_entities
    postgres_session.commit()

    assert postgres_session.bind.in_transaction()
    assert postgres_session.get(Vacancy, vacancy.id) is vacancy
    assert postgres_session.get(CandidateProfile, candidate.id) is candidate
