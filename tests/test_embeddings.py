import math

import pytest

from backend.core.config import Settings
from backend.services.embeddings import (
    StubEmbeddingClient,
    cosine_similarity,
    embed_texts,
    get_embedding_client,
)


@pytest.mark.asyncio
async def test_stub_embedding_client_returns_empty():
    stub = StubEmbeddingClient()
    assert await stub.embed(["база данных", "postgres"]) == []


@pytest.mark.asyncio
async def test_embed_texts_returns_empty_when_client_is_stub(monkeypatch):
    monkeypatch.setattr("backend.services.embeddings.get_embedding_client", lambda: StubEmbeddingClient())
    assert await embed_texts(["база данных"]) == []


def test_get_embedding_client_returns_stub_or_client():
    client = get_embedding_client()
    assert client is not None


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"embedding_base_url": "https://example/v1"},
        {"embedding_base_url": "https://example/v1", "embedding_api_key": "key"},
        {"embedding_base_url": "https://example/v1", "embedding_model": "model"},
        {"embedding_api_key": "key", "embedding_model": "model"},
    ],
)
def test_embeddings_disabled_until_base_url_key_and_model_are_all_set(config):
    settings = Settings(_env_file=None, **config)
    assert settings.embeddings_enabled is False


def test_embeddings_enabled_when_all_three_are_set():
    settings = Settings(
        _env_file=None,
        embedding_base_url="https://example/v1",
        embedding_api_key="key",
        embedding_model="openai/text-embedding-3-large",
    )
    assert settings.embeddings_enabled is True
    assert settings.embedding_dimensions == 1024


class BrokenEmbeddingClient:
    async def embed(self, texts):
        raise RuntimeError("модель не отвечает")


@pytest.mark.asyncio
async def test_embed_texts_returns_empty_when_client_raises(monkeypatch):
    monkeypatch.setattr("backend.services.embeddings.get_embedding_client", lambda: BrokenEmbeddingClient())
    assert await embed_texts(["база данных"]) == []


@pytest.mark.asyncio
async def test_embed_texts_returns_empty_when_length_mismatch(monkeypatch):
    class ShortClient:
        async def embed(self, texts):
            return [[1.0, 0.0]]

    monkeypatch.setattr("backend.services.embeddings.get_embedding_client", lambda: ShortClient())
    assert await embed_texts(["база данных", "postgres"]) == []


@pytest.mark.asyncio
async def test_hybrid_domains_falls_back_to_lexical_when_model_fails(monkeypatch):
    from backend.services.domain_index import hybrid_domains

    class FakeDomain:
        def __init__(self, domain_id, slug, title, aliases):
            self.id, self.slug, self.title, self.aliases, self.embedding = domain_id, slug, title, aliases, None

    domains = [
        FakeDomain(1, "databases", "Базы данных", ["база данных", "postgres", "субд"]),
        FakeDomain(2, "algorithms", "Алгоритмы", ["алгоритмы", "структуры данных"]),
    ]

    class FakeQuery:
        def all(self):
            return domains

    class FakeSession:
        def query(self, *_args):
            return FakeQuery()

    monkeypatch.setattr("backend.services.domain_index.get_embedding_client", lambda: BrokenEmbeddingClient())
    monkeypatch.setattr("backend.services.domain_index.embed_texts", lambda texts: _empty())

    result = await hybrid_domains(FakeSession(), "база данных")
    assert result, "лексический откат не вернул результаты"
    assert result[0][0].slug == "databases"


async def _empty():
    return []


def test_cosine_similarity_is_one_for_identical_vectors():
    vector = [1.0, 2.0, 3.0]
    assert math.isclose(cosine_similarity(vector, vector), 1.0, rel_tol=1e-9)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_handles_dimension_mismatch_and_empty():
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_stub_client_is_detected():
    assert isinstance(StubEmbeddingClient(), StubEmbeddingClient)
