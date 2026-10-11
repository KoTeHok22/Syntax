from backend.api.routes.candidates import sort_cards
from backend.core.scoring import PROOF_TIER_CLAIMED, PROOF_TIER_VERIFIED
from backend.schemas.matching import CandidateCardResponse

from tests.test_api import auth, register_and_login


def make_card(candidate_id: int, final_score: float, score: float, proof_tier: str) -> CandidateCardResponse:
    return CandidateCardResponse(
        candidate_profile_id=candidate_id,
        grade="junior",
        specialization="backend",
        stack=["python"],
        score=score,
        score_breakdown={},
        has_pvn_history=False,
        pvn_achievements=[],
        match_relevance=1.0,
        final_score=final_score,
        proof_tier=proof_tier,
        is_verified=proof_tier == PROOF_TIER_VERIFIED,
    )


def test_claimed_does_not_outrank_verified_with_weaker_stack():
    claimed = make_card(1, final_score=100.0, score=100.0, proof_tier=PROOF_TIER_CLAIMED)
    verified = make_card(2, final_score=24.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    ordered = sort_cards([claimed, verified])
    assert [card.candidate_profile_id for card in ordered] == [2, 1]
    assert ordered[0].proof_tier == PROOF_TIER_VERIFIED


def test_within_tier_orders_by_final_score_then_score():
    low = make_card(1, final_score=30.0, score=80.0, proof_tier=PROOF_TIER_VERIFIED)
    high = make_card(2, final_score=50.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    tie_low = make_card(3, final_score=50.0, score=60.0, proof_tier=PROOF_TIER_CLAIMED)
    tie_high = make_card(4, final_score=50.0, score=70.0, proof_tier=PROOF_TIER_CLAIMED)
    ordered = sort_cards([low, high, tie_low, tie_high])
    assert [card.candidate_profile_id for card in ordered] == [2, 1, 4, 3]


def test_cards_preserve_input_order_on_full_tie():
    first = make_card(1, final_score=50.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    second = make_card(2, final_score=50.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    ordered = sort_cards([first, second])
    assert [card.candidate_profile_id for card in ordered] == [1, 2]


def test_verified_gate_applies_through_search_endpoint(client):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, TestSession
    from backend.core.categorization import assign_category

    claimed_token = register_and_login(client, "gate-claimed@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Идеальный Стек",
            "contacts": {"email": "best@example.com"},
            "stack": ["python", "fastapi", "postgresql"],
            "years_of_experience": 5,
            "soft_skills": ["коммуникация"],
            "specialization": "backend",
        },
        headers=auth(claimed_token),
    )
    verified_token = register_and_login(client, "gate-verified@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={
            "full_name": "Слабый Стек",
            "contacts": {"email": "weak@example.com"},
            "stack": ["python"],
            "years_of_experience": 1,
            "specialization": "backend",
        },
        headers=auth(verified_token),
    )

    db = SessionLocal()
    claimed_profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == "Идеальный Стек").one()
    claimed_profile.grade = "junior"
    assign_category(db, claimed_profile, "backend", "junior")
    claimed_id = claimed_profile.id

    verified_profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == "Слабый Стек").one()
    verified_profile.grade = "junior"
    assign_category(db, verified_profile, "backend", "junior")
    verified_id = verified_profile.id
    db.add(
        TestSession(
            candidate_profile_id=verified_id,
            grade="junior",
            status="completed",
            result_score=10.0,
            task_count=5,
            correct_count=1,
        )
    )
    db.commit()
    db.close()

    employer_token = register_and_login(client, "gate-emp@example.com", "employer")
    results = client.get(
        "/employer/search",
        params={"specialization": "backend", "stack": ["python", "fastapi", "postgresql"]},
        headers=auth(employer_token),
    ).json()

    tiers = {card["candidate_profile_id"]: card["proof_tier"] for card in results}
    assert tiers[claimed_id] == PROOF_TIER_CLAIMED
    assert tiers[verified_id] == PROOF_TIER_VERIFIED
    order = [card["candidate_profile_id"] for card in results]
    assert order.index(verified_id) < order.index(claimed_id)


def test_proof_tier_field_present_and_correct_in_response(client):
    from backend.db import SessionLocal
    from backend.models import CandidateProfile, TestSession
    from backend.core.categorization import assign_category

    untested_token = register_and_login(client, "tier-untested@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "Без Теста", "contacts": {"email": "nt@example.com"}, "stack": ["python"], "specialization": "backend"},
        headers=auth(untested_token),
    )
    tested_token = register_and_login(client, "tier-tested@example.com", "candidate")
    client.put(
        "/candidates/me",
        json={"full_name": "С Тестом", "contacts": {"email": "wt@example.com"}, "stack": ["python"], "specialization": "backend"},
        headers=auth(tested_token),
    )

    db = SessionLocal()
    untested_profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == "Без Теста").one()
    untested_profile.grade = "junior"
    assign_category(db, untested_profile, "backend", "junior")
    untested_id = untested_profile.id

    tested_profile = db.query(CandidateProfile).filter(CandidateProfile.full_name == "С Тестом").one()
    tested_profile.grade = "junior"
    assign_category(db, tested_profile, "backend", "junior")
    tested_id = tested_profile.id
    db.add(
        TestSession(
            candidate_profile_id=tested_id,
            grade="junior",
            status="completed",
            result_score=0.0,
            task_count=5,
            correct_count=0,
        )
    )
    db.commit()
    db.close()

    employer_token = register_and_login(client, "tier-emp@example.com", "employer")
    results = client.get(
        "/employer/search",
        params={"specialization": "backend"},
        headers=auth(employer_token),
    ).json()

    by_id = {card["candidate_profile_id"]: card for card in results}
    assert set(by_id[untested_id].keys()) >= {"proof_tier", "is_verified"}
    assert by_id[untested_id]["proof_tier"] == PROOF_TIER_CLAIMED
    assert by_id[untested_id]["is_verified"] is False
    assert by_id[tested_id]["proof_tier"] == PROOF_TIER_VERIFIED
    assert by_id[tested_id]["is_verified"] is True
    assert results[0]["candidate_profile_id"] == tested_id
