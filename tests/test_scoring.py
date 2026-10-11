from backend.core.scoring import (
    PROOF_TIER_CLAIMED,
    PROOF_TIER_VERIFIED,
    RankableCandidate,
    ScoreComponents,
    compute_score,
    has_pvn_history,
    is_verified,
    proof_tier,
    rank_candidates,
    ranking_key,
)


def test_full_score_matches_weights():
    score, breakdown = compute_score(
        ScoreComponents(
            test_score=100.0,
            pvn_achievements=100.0,
            profile_completeness=100.0,
        )
    )
    assert score == 100.0
    assert breakdown["test_score"]["weight"] == 0.5
    assert breakdown["pvn_achievements"]["weight"] == 0.375


def test_weights_renormalize_without_pvn_history():
    score, breakdown = compute_score(
        ScoreComponents(
            test_score=100.0,
            pvn_achievements=None,
            profile_completeness=100.0,
        )
    )
    assert score == 100.0
    assert breakdown["test_score"]["weight"] == 0.8
    assert breakdown["profile_completeness"]["weight"] == 0.2
    assert "pvn_achievements" not in breakdown


def test_partial_components():
    score, _ = compute_score(
        ScoreComponents(
            test_score=80.0,
            pvn_achievements=None,
            profile_completeness=50.0,
        )
    )
    expected = 0.4 / 0.5 * 80.0 + 0.1 / 0.5 * 50.0
    assert abs(score - round(expected, 2)) < 0.01


def test_has_pvn_history_flag():
    assert has_pvn_history(ScoreComponents(pvn_achievements=10.0))
    assert not has_pvn_history(ScoreComponents())


def test_proof_tier_from_test_session():
    assert proof_tier(ScoreComponents(test_score=0.0)) == PROOF_TIER_VERIFIED
    assert proof_tier(ScoreComponents(test_score=72.0)) == PROOF_TIER_VERIFIED
    assert proof_tier(ScoreComponents(test_score=None)) == PROOF_TIER_CLAIMED
    assert is_verified(ScoreComponents(test_score=1.0))
    assert not is_verified(ScoreComponents(test_score=None))


def test_verified_ranks_above_claimed_at_equal_score():
    verified = RankableCandidate(final_score=100.0, score=100.0, proof_tier=PROOF_TIER_VERIFIED)
    claimed = RankableCandidate(final_score=100.0, score=100.0, proof_tier=PROOF_TIER_CLAIMED)
    assert ranking_key(verified.final_score, verified.score, proof_tier_value=verified.proof_tier) > ranking_key(
        claimed.final_score, claimed.score, proof_tier_value=claimed.proof_tier
    )
    assert rank_candidates([claimed, verified]) == [verified, claimed]


def test_untested_profile_cannot_outrank_verified():
    verified = RankableCandidate(final_score=24.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    claimed = RankableCandidate(final_score=100.0, score=100.0, proof_tier=PROOF_TIER_CLAIMED)
    assert rank_candidates([claimed, verified]) == [verified, claimed]
    assert ranking_key(claimed.final_score, claimed.score, proof_tier_value=claimed.proof_tier) < ranking_key(
        verified.final_score, verified.score, proof_tier_value=verified.proof_tier
    )


def test_tier_derived_from_components_in_ranking_key():
    verified_components = ScoreComponents(test_score=40.0, profile_completeness=50.0)
    claimed_components = ScoreComponents(test_score=None, profile_completeness=50.0)
    assert ranking_key(20.0, 20.0, verified_components) > ranking_key(20.0, 20.0, claimed_components)
    assert ranking_key(20.0, 20.0, verified_components)[0] == 1
    assert ranking_key(20.0, 20.0, claimed_components)[0] == 0
    assert ranking_key(20.0, 20.0)[0] == 0


def test_final_score_breaks_ties_within_same_tier():
    low = RankableCandidate(final_score=30.0, score=80.0, proof_tier=PROOF_TIER_VERIFIED)
    high = RankableCandidate(final_score=50.0, score=60.0, proof_tier=PROOF_TIER_VERIFIED)
    assert rank_candidates([low, high]) == [high, low]
