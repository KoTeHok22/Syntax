import math
import time
from functools import lru_cache

from openai import AsyncOpenAI, BadRequestError, OpenAIError

from backend.core.config import get_settings

BATCH_SIZE = 32
QUERY_CACHE_TTL_SECONDS = 300
QUERY_CACHE_MAX_ENTRIES = 256
_query_cache: dict[tuple, tuple[float, list[float]]] = {}
_skip_until = 0.0
_last_failure_at: float | None = None


class StubEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return []


class OpenAICompatibleEmbeddingClient:
    def __init__(self, base_url: str, api_key: str, model: str, dimensions: int, timeout_seconds: int, supports_dimensions: bool = True):
        self.model = model
        self.dimensions = dimensions
        self.supports_dimensions = supports_dimensions
        self.timeout_seconds = timeout_seconds
        self.client = AsyncOpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            if self.supports_dimensions:
                try:
                    response = await self.client.embeddings.create(
                        model=self.model,
                        input=batch,
                        dimensions=self.dimensions,
                    )
                except TypeError:
                    response = await self.client.embeddings.create(model=self.model, input=batch)
                except BadRequestError:
                    response = await self.client.embeddings.create(model=self.model, input=batch)
            else:
                response = await self.client.embeddings.create(model=self.model, input=batch)
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend([list(item.embedding) for item in ordered])
        return vectors


@lru_cache
def _cached_client(base_url: str, api_key: str, model: str, dimensions: int, timeout_seconds: int, supports_dimensions: bool):
    return OpenAICompatibleEmbeddingClient(base_url, api_key, model, dimensions, timeout_seconds, supports_dimensions)


def model_supports_dimensions(model: str) -> bool:
    lowered = model.lower()
    if "bge-m3" in lowered or "bge_m3" in lowered:
        return False
    return True


def get_embedding_client():
    settings = get_settings()
    if not settings.embeddings_enabled:
        return StubEmbeddingClient()
    return _cached_client(
        settings.embedding_base_url,
        settings.embedding_api_key,
        settings.embedding_model,
        settings.embedding_dimensions,
        settings.embedding_timeout_seconds,
        model_supports_dimensions(settings.embedding_model),
    )


def _cache_lookup(key: tuple) -> list[float] | None:
    entry = _query_cache.get(key)
    if entry is None:
        return None
    stored_at, vector = entry
    if time.monotonic() - stored_at > QUERY_CACHE_TTL_SECONDS:
        _query_cache.pop(key, None)
        return None
    return vector


def _cache_store(key: tuple, vector: list[float]) -> None:
    if len(_query_cache) >= QUERY_CACHE_MAX_ENTRIES:
        oldest = min(_query_cache, key=lambda item: _query_cache[item][0])
        _query_cache.pop(oldest, None)
    _query_cache[key] = (time.monotonic(), vector)


async def embed_texts(texts: list[str]) -> list[list[float]]:
    global _skip_until
    client = get_embedding_client()
    if isinstance(client, StubEmbeddingClient):
        return []
    cleaned = [text.strip() or " " for text in texts]
    model = getattr(client, "model", "")
    results: list[list[float] | None] = [None] * len(cleaned)
    missing: list[int] = []
    for index, text in enumerate(cleaned):
        cached = _cache_lookup((model, text))
        if cached is None:
            missing.append(index)
        else:
            results[index] = cached
    if missing:
        settings = get_settings()
        if time.monotonic() < _skip_until:
            return []
        try:
            vectors = await client.embed([cleaned[index] for index in missing])
        except (OpenAIError, ValueError):
            _skip_until = time.monotonic() + settings.embedding_failure_cooldown_seconds
            return []
        except Exception:
            _skip_until = time.monotonic() + settings.embedding_failure_cooldown_seconds
            return []
        if len(vectors) != len(missing):
            _skip_until = time.monotonic() + settings.embedding_failure_cooldown_seconds
            return []
        for index, vector in zip(missing, vectors):
            results[index] = vector
            _cache_store((model, cleaned[index]), vector)
    if any(vector is None for vector in results):
        return []
    return [vector for vector in results if vector is not None]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
