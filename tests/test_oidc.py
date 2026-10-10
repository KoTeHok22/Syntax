import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import deps
from backend.api.routes import auth, pvn_auth
from backend.auth import oidc
from backend.auth.security import create_access_token, hash_password
from backend.db import Base
from backend.models import CandidateProfile, PvnAchievement, User


@pytest.fixture()
def identity_provider(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="key-1", alg="RS256", use="sig")
    provider = SimpleNamespace(
        key=key,
        jwks={"keys": [jwk]},
        requests=[],
        status=200,
        raw=None,
        config=oidc.OIDCSettings("https://issuer.test", "syntax-api", "https://issuer.test/keys"),
    )
    client_type = httpx.Client

    def handle(request):
        provider.requests.append(request)
        if provider.raw is not None:
            return httpx.Response(provider.status, content=provider.raw)
        return httpx.Response(provider.status, json=provider.jwks)

    def mocked_client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        assert 0 < kwargs["timeout"] <= 10
        return client_type(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(oidc.httpx, "Client", mocked_client)
    oidc.clear_jwks_cache()
    yield provider
    oidc.clear_jwks_cache()


def signed_token(provider, changes=None, headers=None, key=None):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "pvn-subject-1",
        "iss": provider.config.issuer,
        "aud": provider.config.audience,
        "iat": now.timestamp(),
        "exp": (now + timedelta(minutes=5)).timestamp(),
        "azp": "syntax-client",
        "email": "external@example.com",
        "email_verified": True,
        "name": "External Candidate",
        "pvn_id": "pvn-42",
        "achievements": [
            {"id": "a-1", "type": "olympiad", "level": "gold", "achieved_at": "2026-01-02", "score": 40}
        ],
    }
    payload.update(changes or {})
    payload = {name: value for name, value in payload.items() if value is not None}
    return jwt.encode(payload, key or provider.key, algorithm="RS256", headers={"kid": "key-1", **(headers or {})})


def test_oidc_validates_signature_and_enrichment(identity_provider):
    claims = oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    enrichment = oidc.extract_enrichment(
        claims, issuer=identity_provider.config.issuer, pvn_id_claim="pvn_id", achievements_claim="achievements"
    )
    assert enrichment.subject == "pvn-subject-1"
    assert enrichment.pvn_id == "pvn-42"
    assert enrichment.achievements[0].score == 40
    assert str(identity_provider.requests[0].url) == identity_provider.config.jwks_url


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://other.test"},
        {"aud": "other-api"},
        {"exp": (datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()},
        {"exp": None},
        {"aud": None},
        {"iss": None},
        {"iat": None},
        {"sub": None},
        {"sub": 42},
        {"sub": ""},
        {"sub": "s" * 256},
        {"exp": "99999999999"},
        {"exp": float("nan")},
        {"nbf": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()},
        {"iat": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()},
    ],
)
def test_oidc_rejects_invalid_registered_claims(identity_provider, changes):
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider, changes), identity_provider.config)


def test_oidc_rejects_wrong_signature(identity_provider):
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider, key=attacker_key), identity_provider.config)


@pytest.mark.parametrize("algorithm", ["none", "HS256"])
def test_oidc_rejects_algorithm_confusion_without_fetching(identity_provider, algorithm):
    token = jwt.encode({"sub": "subject", "iss": identity_provider.config.issuer}, "s" * 32 if algorithm == "HS256" else None, algorithm=algorithm, headers={"kid": "key-1"})
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(token, identity_provider.config)
    assert identity_provider.requests == []


def test_oidc_ignores_token_key_urls_and_caches_unknown_key(identity_provider):
    token = signed_token(identity_provider, headers={"jku": "https://attacker.test/keys", "x5u": "https://attacker.test/cert"})
    oidc.validate_bearer(token, identity_provider.config)
    oidc.validate_bearer(token, identity_provider.config)
    for index in range(10):
        with pytest.raises(oidc.OIDCValidationError):
            oidc.validate_bearer(signed_token(identity_provider, headers={"kid": f"unknown-{index}"}), identity_provider.config)
    assert len(identity_provider.requests) == 2
    assert all(str(request.url) == identity_provider.config.jwks_url for request in identity_provider.requests)


@pytest.mark.parametrize("status,raw", [(302, b""), (500, b""), (200, b"x" * (oidc.MAX_JWKS_BYTES + 1)), (200, b"not json")], ids=["redirect", "server-error", "too-large", "malformed"])
def test_oidc_jwks_fail_closed_and_bound_retry(identity_provider, status, raw):
    identity_provider.status = status
    identity_provider.raw = raw
    for _ in range(2):
        with pytest.raises(oidc.OIDCValidationError):
            oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    assert len(identity_provider.requests) == 1


def test_oidc_cache_expiry_refreshes_keys(identity_provider, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(oidc.time, "monotonic", lambda: clock[0])
    oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    clock[0] = 301
    identity_provider.jwks["keys"] = []
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    assert len(identity_provider.requests) == 2


def test_oidc_unknown_kid_forces_one_bounded_refresh(identity_provider):
    rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rotated_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rotated_key.public_key()))
    rotated_jwk.update(kid="key-2", alg="RS256", use="sig")
    token = signed_token(identity_provider, headers={"kid": "key-2"}, key=rotated_key)
    oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    identity_provider.jwks = {"keys": [rotated_jwk]}
    assert oidc.validate_bearer(token, identity_provider.config)["sub"] == "pvn-subject-1"
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider, headers={"kid": "missing"}), identity_provider.config)
    assert len(identity_provider.requests) == 2


def test_oidc_rotating_key_refresh_does_not_stampede(identity_provider):
    oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rotated_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rotated_key.public_key()))
    rotated_jwk.update(kid="key-2", alg="RS256", use="sig")
    identity_provider.jwks = {"keys": [rotated_jwk]}
    token = signed_token(identity_provider, headers={"kid": "key-2"}, key=rotated_key)
    ready = threading.Barrier(8)

    def validate(index):
        ready.wait(timeout=5)
        return oidc.validate_bearer(token, identity_provider.config)["sub"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(validate, range(8))) == ["pvn-subject-1"] * 8
    assert len(identity_provider.requests) == 2


def test_oidc_failed_forced_refresh_is_bounded_and_can_recover(identity_provider, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(oidc.time, "monotonic", lambda: clock[0])
    valid = signed_token(identity_provider)
    oidc.validate_bearer(valid, identity_provider.config)
    identity_provider.status = 500
    for index in range(8):
        with pytest.raises(oidc.OIDCValidationError):
            oidc.validate_bearer(signed_token(identity_provider, headers={"kid": f"missing-{index}"}), identity_provider.config)
    assert len(identity_provider.requests) == 2
    assert oidc.validate_bearer(valid, identity_provider.config)["sub"] == "pvn-subject-1"
    rotated_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rotated_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(rotated_key.public_key()))
    rotated_jwk.update(kid="key-2", alg="RS256", use="sig")
    identity_provider.status = 200
    identity_provider.jwks = {"keys": [rotated_jwk]}
    clock[0] = 11.0
    token = signed_token(identity_provider, headers={"kid": "key-2"}, key=rotated_key)
    assert oidc.validate_bearer(token, identity_provider.config)["sub"] == "pvn-subject-1"
    assert len(identity_provider.requests) == 3


@pytest.mark.parametrize("change", [{"kty": "oct"}, {"use": "enc"}, {"key_ops": ["sign"]}, {"alg": "HS256"}, {"d": "private"}], ids=["oct", "encryption", "signing", "algorithm", "private"])
def test_oidc_rejects_incompatible_jwk(identity_provider, change):
    identity_provider.jwks["keys"][0].update(change)
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)


@pytest.mark.parametrize(
    "changes",
    [{"algorithms": ("HS256",)}, {"jwks_url": "http://issuer.test/keys"}, {"issuer": "https://user:pass@issuer.test"}, {"timeout_seconds": float("nan")}, {"cache_ttl_seconds": 0}],
)
def test_oidc_rejects_unsafe_configuration(changes):
    params = {"issuer": "https://issuer.test", "audience": "api", "jwks_url": "https://issuer.test/keys", **changes}
    with pytest.raises(oidc.OIDCValidationError):
        oidc.OIDCSettings(**params)


@pytest.mark.parametrize("score", [-1, 101, True, "40", float("nan")])
def test_oidc_rejects_invalid_achievement_scores(score):
    claims = {"sub": "subject", "achievements": [{"id": "a", "type": "contest", "level": "gold", "achieved_at": "2026-01-01", "score": score}]}
    with pytest.raises(oidc.OIDCValidationError):
        oidc.extract_enrichment(claims, issuer="https://issuer.test", achievements_claim="achievements")


@pytest.fixture()
def oidc_api(identity_provider, monkeypatch):
    settings = SimpleNamespace(
        jwt_secret="local-test-secret-with-32-or-more-bytes",
        jwt_algorithm="HS256",
        jwt_issuer="local-syntax",
        jwt_expires_minutes=60,
        pvn_oidc_issuer=identity_provider.config.issuer,
        pvn_oidc_audience=identity_provider.config.audience,
        pvn_oidc_jwks_url=identity_provider.config.jwks_url,
        pvn_oidc_algorithms=["RS256"],
        pvn_oidc_trusted_client_ids=["syntax-client"],
        pvn_oidc_id_claim="pvn_id",
        pvn_oidc_achievements_claim="achievements",
    )
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    def get_db():
        with sessions() as db:
            yield db

    monkeypatch.setattr(deps, "get_settings", lambda: settings)
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(pvn_auth, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(auth.router, prefix="/auth")
    app.include_router(pvn_auth.router, prefix="/auth")
    app.dependency_overrides[deps.get_db] = get_db
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sessions=sessions, provider=identity_provider, settings=settings)
    engine.dispose()


def exchange(api, changes=None, authorization=None, consent=True):
    return api.client.post(
        "/auth/pvn",
        json={"access_token": signed_token(api.provider, changes), "consent_accepted": consent},
        headers={"Authorization": f"Bearer {authorization}"} if authorization else {},
    )


def add_local_user(api, email="external@example.com", role="candidate"):
    with api.sessions() as db:
        user = User(email=email, password_hash=hash_password("password123"), role=role, is_email_confirmed=True, consent_accepted=True)
        db.add(user)
        db.flush()
        db.add(CandidateProfile(user_id=user.id, full_name="Local Name"))
        db.commit()
        return create_access_token(user.id, email, role, None, api.settings.jwt_secret, "HS256", 60, api.settings.jwt_issuer), user.id


def test_pvn_enrollment_and_external_bearer_refresh_are_idempotent(oidc_api):
    api = oidc_api
    response = exchange(api)
    assert response.status_code == 200, response.text
    assert response.json()["created"] is True
    local = response.json()["access_token"]
    assert api.client.get("/auth/me", headers={"Authorization": f"Bearer {local}"}).status_code == 200
    assert exchange(api).json()["created"] is False
    refreshed = signed_token(api.provider, {"achievements": [{"id": "a-1", "type": "contest", "level": "silver", "achieved_at": "2026-01-03", "score": 20}]})
    assert api.client.get("/auth/me", headers={"Authorization": f"Bearer {refreshed}"}).status_code == 200
    with api.sessions() as db:
        user = db.query(User).one()
        profile = db.query(CandidateProfile).one()
        assert user.oidc_subject == "pvn-subject-1"
        assert user.pvn_id == "pvn-42"
        assert profile.full_name == "External Candidate"
        assert profile.contacts == {"email": "external@example.com"}
        assert profile.grade is None
        assert db.query(PvnAchievement).one().score == 20


def test_pvn_never_links_by_email_without_local_authentication(oidc_api):
    local, user_id = add_local_user(oidc_api)
    assert exchange(oidc_api).status_code == 409
    with oidc_api.sessions() as db:
        assert db.get(User, user_id).oidc_subject is None
        assert db.query(PvnAchievement).count() == 0
    response = exchange(oidc_api, authorization=local)
    assert response.status_code == 200, response.text
    assert response.json()["created"] is False
    with oidc_api.sessions() as db:
        assert db.query(User).count() == 1
        assert db.get(User, user_id).oidc_subject == "pvn-subject-1"
        assert db.query(CandidateProfile).one().full_name == "Local Name"


def test_pvn_refuses_identity_theft_and_rebinding(oidc_api):
    first, _ = add_local_user(oidc_api)
    assert exchange(oidc_api, authorization=first).status_code == 200
    second, second_id = add_local_user(oidc_api, "second@example.com")
    assert exchange(oidc_api, authorization=second).status_code == 409
    assert exchange(oidc_api, {"sub": "different-subject"}, authorization=first).status_code == 409
    with oidc_api.sessions() as db:
        assert db.get(User, second_id).oidc_subject is None
        assert db.query(PvnAchievement).count() == 1


def test_pvn_requires_consent_and_rejects_unverified_local_identity(oidc_api):
    assert exchange(oidc_api, consent=False).status_code == 400
    assert exchange(oidc_api, authorization="bad").status_code == 401
    assert exchange(oidc_api, {"azp": "untrusted-client"}).status_code == 401
    assert exchange(oidc_api, {"email_verified": False}).status_code == 401
    assert exchange(oidc_api, {"email_verified": True, "email": "not-an-email"}).status_code == 401
    with oidc_api.sessions() as db:
        assert db.query(User).count() == 0


def test_pvn_ignores_untrusted_custom_claims_and_role_grade(oidc_api):
    oidc_api.settings.pvn_oidc_trusted_client_ids = []
    response = exchange(oidc_api, {"role": "employer", "grade": "senior", "achievements": "untrusted", "pvn_id": {"bad": True}})
    assert response.status_code == 200, response.text
    with oidc_api.sessions() as db:
        user = db.query(User).one()
        assert user.role == "candidate"
        assert user.pvn_id == "pvn-subject-1"
        assert db.query(CandidateProfile).one().grade is None
        assert db.query(PvnAchievement).count() == 0


def test_pvn_refresh_only_removes_provider_owned_achievements(oidc_api):
    assert exchange(oidc_api).status_code == 200
    with oidc_api.sessions() as db:
        profile = db.query(CandidateProfile).one()
        db.add(PvnAchievement(candidate_profile_id=profile.id, achievement_type="local", level="gold", achieved_at=datetime(2026, 1, 1).date(), score=50))
        db.commit()
    assert exchange(oidc_api, {"achievements": []}).status_code == 200
    with oidc_api.sessions() as db:
        assert db.query(PvnAchievement).count() == 1
        assert db.query(PvnAchievement).one().achievement_type == "local"


def test_pvn_external_token_does_not_select_local_integer_user_id(oidc_api):
    _, user_id = add_local_user(oidc_api)
    token = signed_token(oidc_api.provider, {"sub": str(user_id)})
    assert oidc_api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pvn_malformed_local_subject_returns_unauthorized(oidc_api):
    token = jwt.encode({"iss": oidc_api.settings.jwt_issuer, "sub": "not-an-id", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)}, oidc_api.settings.jwt_secret, algorithm="HS256")
    assert oidc_api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_pvn_achievements_cannot_cross_candidate_ownership(oidc_api):
    api = oidc_api
    assert exchange(api).status_code == 200
    assert exchange(api, {"sub": "second-subject", "email": "second@example.com"}).status_code == 200
    with api.sessions() as db:
        rows = db.query(PvnAchievement).order_by(PvnAchievement.id).all()
        assert len(rows) == 2
        assert rows[0].candidate_profile_id != rows[1].candidate_profile_id
    assert exchange(api, {"achievements": []}).status_code == 200
    with api.sessions() as db:
        row = db.query(PvnAchievement).one()
        profile = db.get(CandidateProfile, row.candidate_profile_id)
        assert db.get(User, profile.user_id).oidc_subject == "second-subject"


def test_pvn_malformed_achievements_roll_back_enrollment(oidc_api):
    assert exchange(oidc_api, {"achievements": [{"id": "bad", "score": 999999}]}).status_code == 401
    with oidc_api.sessions() as db:
        assert db.query(User).count() == 0
        assert db.query(CandidateProfile).count() == 0
        assert db.query(PvnAchievement).count() == 0


def test_local_bearer_without_exp_is_rejected(oidc_api):
    _, user_id = add_local_user(oidc_api)
    token = jwt.encode({"iss": oidc_api.settings.jwt_issuer, "sub": str(user_id)}, oidc_api.settings.jwt_secret, algorithm="HS256")
    assert oidc_api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_oidc_rejects_oversized_tokens_without_network(identity_provider):
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer("x" * 16385, identity_provider.config)
    assert identity_provider.requests == []


def test_oidc_no_trusted_key_on_unknown_issuer(identity_provider):
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider, {"iss": "https://attacker.test"}), identity_provider.config)
    assert identity_provider.requests == []


def test_oidc_rejects_duplicates_and_unsupported_critical_headers(identity_provider):
    identity_provider.jwks["keys"].append(dict(identity_provider.jwks["keys"][0]))
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider), identity_provider.config)
    oidc.clear_jwks_cache()
    with pytest.raises(oidc.OIDCValidationError):
        oidc.validate_bearer(signed_token(identity_provider, headers={"crit": ["custom"]}), identity_provider.config)


def test_pvn_linked_candidate_without_provider_email_can_refresh(oidc_api):
    local, _ = add_local_user(oidc_api)
    assert exchange(oidc_api, {"email": None, "email_verified": False}, authorization=local).status_code == 200
    token = signed_token(oidc_api.provider, {"email": None, "email_verified": False})
    assert oidc_api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
