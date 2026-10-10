import time

import httpx

from backend.core.config import get_settings

_skip_until = 0.0


def rerank_enabled() -> bool:
    return get_settings().rerank_enabled


def _endpoint() -> tuple[str, str]:
    settings = get_settings()
    base = (settings.rerank_base_url or settings.embedding_base_url).rstrip("/")
    key = settings.rerank_api_key or settings.embedding_api_key
    return f"{base}/rerank", key


async def rerank(query: str, documents: list[str], top_n: int | None = None) -> list[tuple[int, float]] | None:
    global _skip_until
    if not rerank_enabled() or not documents or not query.strip():
        return None
    settings = get_settings()
    if time.monotonic() < _skip_until:
        return None
    url, key = _endpoint()
    payload = {
        "model": settings.rerank_model,
        "query": query[:4000],
        "documents": [document[:4000] for document in documents],
        "top_n": min(top_n or len(documents), len(documents)),
    }
    try:
        async with httpx.AsyncClient(timeout=settings.rerank_timeout_seconds) as client:
            response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload)
            if response.status_code >= 400:
                _skip_until = time.monotonic() + settings.embedding_failure_cooldown_seconds
                return None
            body = response.json()
    except Exception:
        _skip_until = time.monotonic() + settings.embedding_failure_cooldown_seconds
        return None
    results = body.get("results")
    if not isinstance(results, list) or not results:
        return None
    scored = []
    for item in results:
        index = item.get("index")
        score = item.get("relevance_score")
        if isinstance(index, int) and isinstance(score, (int, float)):
            scored.append((index, float(score)))
    if not scored:
        return None
    return scored
