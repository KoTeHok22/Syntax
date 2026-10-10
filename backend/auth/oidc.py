from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
import jwt


class OIDCValidationError(ValueError):
    pass


@dataclass(frozen=True)
class OIDCSettings:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 300
    trusted_client_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.issuer or not self.audience or not self.jwks_url:
            raise OIDCValidationError("OIDC issuer, audience and JWKS URL are required")
        if len(self.issuer) > 512 or len(self.audience) > 255 or len(self.jwks_url) > 2048:
            raise OIDCValidationError("OIDC configuration exceeds length limits")
        for value in (self.issuer, self.jwks_url):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise OIDCValidationError("OIDC endpoints must be HTTPS URLs without query or fragment")
        if not self.algorithms or any(value not in JWKS_ALGORITHMS for value in self.algorithms):
            raise OIDCValidationError("OIDC algorithms must be asymmetric JWKS algorithms")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0 or self.timeout_seconds > 10:
            raise OIDCValidationError("OIDC timeout is outside the permitted range")
        if self.cache_ttl_seconds <= 0 or self.cache_ttl_seconds > 86400:
            raise OIDCValidationError("OIDC cache TTL is outside the permitted range")


@dataclass(frozen=True)
class AchievementClaim:
    external_id: str
    achievement_type: str
    level: str
    achieved_at: date
    score: float


@dataclass(frozen=True)
class PvnEnrichment:
    issuer: str
    subject: str
    pvn_id: str | None
    achievements: tuple[AchievementClaim, ...]


JWKS_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
    }
)
MAX_TOKEN_LENGTH = 16384
MAX_JWKS_BYTES = 262144
MAX_JWKS_KEYS = 64
MAX_ACHIEVEMENTS = 256
_jwks_cache: dict[OIDCSettings, tuple[float, tuple[dict[str, Any], ...]]] = {}
_jwks_retry_after: dict[OIDCSettings, float] = {}
_jwks_refresh_after: dict[OIDCSettings, float] = {}
_jwks_lock = threading.RLock()


def oidc_settings_from(settings: Any) -> OIDCSettings | None:
    issuer = str(getattr(settings, "pvn_oidc_issuer", "") or "").strip()
    audience = str(getattr(settings, "pvn_oidc_audience", "") or "").strip()
    jwks_url = str(getattr(settings, "pvn_oidc_jwks_url", "") or "").strip()
    if not issuer and not audience and not jwks_url:
        return None
    algorithms = getattr(settings, "pvn_oidc_algorithms", ("RS256",)) or ("RS256",)
    if isinstance(algorithms, str):
        algorithms = tuple(part.strip() for part in algorithms.split(",") if part.strip())
    return OIDCSettings(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        algorithms=tuple(algorithms),
        timeout_seconds=float(getattr(settings, "pvn_oidc_http_timeout_seconds", 5.0)),
        cache_ttl_seconds=int(getattr(settings, "pvn_oidc_cache_ttl_seconds", 300)),
        trusted_client_ids=tuple(getattr(settings, "pvn_oidc_trusted_client_ids", ()) or ()),
    )


def _fetch_jwks(config: OIDCSettings, *, force: bool = False) -> tuple[dict[str, Any], ...]:
    with _jwks_lock:
        now = time.monotonic()
        cached = _jwks_cache.get(config)
        if not force and cached is not None and cached[0] > now:
            return cached[1]
        if force and _jwks_refresh_after.get(config, 0) > now:
            if cached is not None:
                return cached[1]
            raise OIDCValidationError("OIDC JWKS is temporarily unavailable")
        if not force and _jwks_retry_after.get(config, 0) > now:
            raise OIDCValidationError("OIDC JWKS is temporarily unavailable")
        if len(_jwks_retry_after) >= 16 and config not in _jwks_retry_after:
            _jwks_retry_after.pop(next(iter(_jwks_retry_after)))
        _jwks_retry_after[config] = now + 10
        if force:
            if len(_jwks_refresh_after) >= 16 and config not in _jwks_refresh_after:
                _jwks_refresh_after.pop(next(iter(_jwks_refresh_after)))
            _jwks_refresh_after[config] = now + 10
        try:
            with httpx.Client(timeout=config.timeout_seconds, follow_redirects=False, trust_env=False) as client:
                with client.stream("GET", config.jwks_url, headers={"Accept": "application/json"}) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        if time.monotonic() - now > config.timeout_seconds or len(body) + len(chunk) > MAX_JWKS_BYTES:
                            raise OIDCValidationError("OIDC JWKS response exceeds limits")
                        body.extend(chunk)
            document = json.loads(body)
            keys = document.get("keys") if isinstance(document, dict) else None
            if not isinstance(keys, list) or not 0 < len(keys) <= MAX_JWKS_KEYS:
                raise OIDCValidationError("OIDC JWKS response has an invalid key set")
            normalized = tuple(key for key in keys if isinstance(key, dict))
            if len(normalized) != len(keys):
                raise OIDCValidationError("OIDC JWKS contains an invalid key")
        except OIDCValidationError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise OIDCValidationError("OIDC JWKS could not be loaded") from exc
        if len(_jwks_cache) >= 16 and config not in _jwks_cache:
            _jwks_cache.pop(next(iter(_jwks_cache)))
        _jwks_cache[config] = (time.monotonic() + config.cache_ttl_seconds, normalized)
        _jwks_retry_after.pop(config, None)
        return normalized


def _key_for_token(token: str, config: OIDCSettings) -> Any:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as exc:
        raise OIDCValidationError("OIDC token header is invalid") from exc
    algorithm = header.get("alg")
    key_id = header.get("kid")
    if header.get("crit"):
        raise OIDCValidationError("OIDC token uses unsupported critical headers")
    if not isinstance(algorithm, str) or algorithm not in config.algorithms or algorithm not in JWKS_ALGORITHMS or not isinstance(key_id, str) or not 0 < len(key_id) <= 255:
        raise OIDCValidationError("OIDC token algorithm or key id is not trusted")
    keys = _fetch_jwks(config)
    candidates = [key for key in keys if key.get("kid") == key_id and key.get("alg", algorithm) == algorithm]
    if not any(key.get("kid") == key_id for key in keys):
        keys = _fetch_jwks(config, force=True)
        candidates = [key for key in keys if key.get("kid") == key_id and key.get("alg", algorithm) == algorithm]
    if len(candidates) != 1:
        raise OIDCValidationError("OIDC signing key is not trusted")
    jwk = candidates[0]
    expected_type = "EC" if algorithm.startswith("ES") else "RSA"
    if jwk.get("kty") != expected_type or jwk.get("use", "sig") != "sig" or "d" in jwk:
        raise OIDCValidationError("OIDC signing key type is invalid")
    if "key_ops" in jwk and jwk["key_ops"] != ["verify"]:
        raise OIDCValidationError("OIDC signing key operations are invalid")
    if algorithm.startswith("ES") and jwk.get("crv") != {"ES256": "P-256", "ES384": "P-384", "ES512": "P-521"}[algorithm]:
        raise OIDCValidationError("OIDC signing curve is invalid")
    try:
        key = jwt.algorithms.get_default_algorithms()[algorithm].from_jwk(json.dumps(jwk))
        if expected_type == "RSA" and key.key_size < 2048:
            raise OIDCValidationError("OIDC RSA key is too small")
        return key
    except (KeyError, ValueError, TypeError, jwt.PyJWTError) as exc:
        raise OIDCValidationError("OIDC signing key is invalid") from exc


def validate_bearer(token: str, config: OIDCSettings) -> dict[str, Any]:
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH:
        raise OIDCValidationError("OIDC bearer token is invalid")
    try:
        untrusted = jwt.decode(token, options={"verify_signature": False})
        if untrusted.get("iss") != config.issuer:
            raise OIDCValidationError("OIDC issuer is not trusted")
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise OIDCValidationError("OIDC bearer token is invalid") from exc
    key = _key_for_token(token, config)
    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=list(config.algorithms),
            issuer=config.issuer,
            audience=config.audience,
            options={"require": ["sub", "iss", "aud", "exp", "iat"]},
        )
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError) as exc:
        raise OIDCValidationError("OIDC bearer token is invalid") from exc
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise OIDCValidationError("OIDC subject is invalid")
    for name in ("exp", "iat", "nbf"):
        value = claims.get(name)
        if name in claims and (type(value) not in (int, float) or not math.isfinite(value)):
            raise OIDCValidationError("OIDC time claim is invalid")
    if config.trusted_client_ids:
        client_id = claims.get("azp")
        if not isinstance(client_id, str) or client_id not in config.trusted_client_ids:
            raise OIDCValidationError("OIDC client is not trusted")
    return claims


def extract_enrichment(
    claims: Mapping[str, Any],
    *,
    issuer: str,
    pvn_id_claim: str = "",
    achievements_claim: str = "",
) -> PvnEnrichment:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise OIDCValidationError("OIDC subject is invalid")
    pvn_id = None
    if pvn_id_claim:
        value = claims.get(pvn_id_claim)
        if value is not None:
            if not isinstance(value, str) or not value.strip() or len(value) > 64:
                raise OIDCValidationError("PVN id claim is invalid")
            pvn_id = value.strip()
    achievements: list[AchievementClaim] = []
    seen_ids: set[str] = set()
    if achievements_claim:
        raw = claims.get(achievements_claim, [])
        if not isinstance(raw, list) or len(raw) > MAX_ACHIEVEMENTS:
            raise OIDCValidationError("PVN achievements claim is invalid")
        for item in raw:
            if not isinstance(item, dict):
                raise OIDCValidationError("PVN achievement is invalid")
            values = {key: item.get(key) for key in ("id", "type", "level", "achieved_at", "score")}
            if not all(isinstance(values[key], str) and values[key].strip() for key in ("id", "type", "level", "achieved_at")):
                raise OIDCValidationError("PVN achievement fields are invalid")
            if len(values["id"]) > 255 or len(values["type"]) > 64 or len(values["level"]) > 32 or values["id"] in seen_ids:
                raise OIDCValidationError("PVN achievement fields are invalid")
            seen_ids.add(values["id"])
            try:
                achieved_at = date.fromisoformat(values["achieved_at"])
                score = float(values["score"])
            except (TypeError, ValueError) as exc:
                raise OIDCValidationError("PVN achievement values are invalid") from exc
            if type(values["score"]) not in (int, float) or not math.isfinite(score) or score < 0 or score > 100 or achieved_at > date.today():
                raise OIDCValidationError("PVN achievement score is invalid")
            achievements.append(
                AchievementClaim(
                    external_id=values["id"],
                    achievement_type=values["type"].strip(),
                    level=values["level"].strip(),
                    achieved_at=achieved_at,
                    score=score,
                )
            )
    return PvnEnrichment(issuer=issuer, subject=subject, pvn_id=pvn_id, achievements=tuple(achievements))


def clear_jwks_cache() -> None:
    with _jwks_lock:
        _jwks_cache.clear()
        _jwks_retry_after.clear()
        _jwks_refresh_after.clear()


def synchronize_candidate(db: Any, user: Any, claims: Mapping[str, Any], settings: Any) -> int:
    from backend.models import CandidateProfile, PvnAchievement

    if user.role != "candidate" or user.oidc_issuer != claims.get("iss") or user.oidc_subject != claims.get("sub"):
        raise OIDCValidationError("External identity does not own this candidate")
    trusted_clients = tuple(getattr(settings, "pvn_oidc_trusted_client_ids", ()) or ())
    trust_custom_claims = bool(trusted_clients) and claims.get("azp") in trusted_clients
    enrichment = extract_enrichment(
        claims,
        issuer=user.oidc_issuer,
        pvn_id_claim=getattr(settings, "pvn_oidc_id_claim", "") if trust_custom_claims else "",
        achievements_claim=getattr(settings, "pvn_oidc_achievements_claim", "") if trust_custom_claims else "",
    )
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == user.id).one_or_none()
    if profile is None:
        raise OIDCValidationError("Candidate profile is missing")
    user.pvn_id = enrichment.pvn_id or (enrichment.subject if len(enrichment.subject) <= 64 else None)
    name = claims.get("name")
    if not profile.full_name and isinstance(name, str) and len(name) <= 255:
        profile.full_name = name.strip()
    if claims.get("email_verified") is True and claims.get("email") == user.email:
        profile.contacts = {"email": user.email, **(profile.contacts or {})}
    rows = db.query(PvnAchievement).filter(
        PvnAchievement.candidate_profile_id == profile.id,
        PvnAchievement.source_issuer == enrichment.issuer,
    ).all()
    by_external_id = {row.external_id: row for row in rows}
    achievement_claim_name = getattr(settings, "pvn_oidc_achievements_claim", "")
    if trust_custom_claims and achievement_claim_name and achievement_claim_name in claims:
        current_ids = {achievement.external_id for achievement in enrichment.achievements}
        for row in rows:
            if row.external_id not in current_ids:
                db.delete(row)
    for achievement in enrichment.achievements:
        row = by_external_id.get(achievement.external_id)
        if row is None:
            row = PvnAchievement(
                candidate_profile_id=profile.id,
                source_issuer=enrichment.issuer,
                external_id=achievement.external_id,
            )
            db.add(row)
        row.achievement_type = achievement.achievement_type
        row.level = achievement.level
        row.achieved_at = achievement.achieved_at
        row.score = achievement.score
    return len(enrichment.achievements)
