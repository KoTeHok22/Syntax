from backend.api.routes.candidates import apply_card_filters, sort_cards
from backend.core.scoring import (
    PROOF_TIER_CLAIMED,
    PROOF_TIER_VERIFIED,
    RELEVANCE_MAX_BONUS,
    RELEVANCE_MIN,
    final_score as compute_final_score,
    meets_relevance_floor,
)
from backend.schemas.matching import CandidateCardResponse


def make_card(candidate_id: int, score: float, relevance: float, proof_tier: str) -> CandidateCardResponse:
    return CandidateCardResponse(
        candidate_profile_id=candidate_id,
        grade="junior",
        specialization="backend",
        stack=["python"],
        score=score,
        score_breakdown={},
        has_pvn_history=False,
        pvn_achievements=[],
        match_relevance=relevance,
        final_score=round(compute_final_score(score, relevance), 2),
        proof_tier=proof_tier,
        is_verified=proof_tier == PROOF_TIER_VERIFIED,
    )


def test_verified_with_strong_test_outranks_claimed_with_full_stack():
    claimed = make_card(1, score=36.0, relevance=1.0, proof_tier=PROOF_TIER_CLAIMED)
    verified = make_card(2, score=84.0, relevance=0.333, proof_tier=PROOF_TIER_VERIFIED)
    ordered = sort_cards([claimed, verified])
    assert [card.candidate_profile_id for card in ordered] == [2, 1]
    assert ordered[0].proof_tier == PROOF_TIER_VERIFIED


def test_relevance_still_rewards_better_match_at_equal_score():
    weak = make_card(1, score=70.0, relevance=0.3, proof_tier=PROOF_TIER_VERIFIED)
    strong = make_card(2, score=70.0, relevance=1.0, proof_tier=PROOF_TIER_VERIFIED)
    ordered = sort_cards([weak, strong])
    assert [card.candidate_profile_id for card in ordered] == [2, 1]


def test_meets_relevance_floor_on_boundary():
    assert meets_relevance_floor(RELEVANCE_MIN) is True
    assert meets_relevance_floor(RELEVANCE_MIN + 0.01) is True
    assert meets_relevance_floor(RELEVANCE_MIN - 0.01) is False


def test_require_relevance_filter_is_off_by_default():
    relevant = make_card(1, score=70.0, relevance=0.8, proof_tier=PROOF_TIER_VERIFIED)
    irrelevant = make_card(2, score=70.0, relevance=0.1, proof_tier=PROOF_TIER_VERIFIED)
    cards = [relevant, irrelevant]
    assert apply_card_filters(cards, None, None) == cards
    assert apply_card_filters(cards, None, None, require_relevance=False) == cards
    filtered = apply_card_filters(cards, None, None, require_relevance=True)
    assert [card.candidate_profile_id for card in filtered] == [1]


def test_final_score_formula_uses_bounded_bonus():
    assert compute_final_score(80.0, 1.0) == 80.0 + RELEVANCE_MAX_BONUS
    assert compute_final_score(80.0, 0.0) == 80.0
    assert compute_final_score(80.0, 0.5, proof_tier_value=PROOF_TIER_VERIFIED) == 90.0
