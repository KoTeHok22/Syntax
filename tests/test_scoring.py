from backend.core.scoring import (
    ScoreComponents,
    compute_score,
    has_pvn_history,
)


def test_full_score_matches_weights():
    score, breakdown = compute_score(
        ScoreComponents(
            test_score=100.0,
            pvn_achievements=100.0,
            regular_task_score=100.0,
            profile_completeness=100.0,
        )
    )
    assert score == 100.0
    assert breakdown["test_score"]["weight"] == 0.4
    assert breakdown["pvn_achievements"]["weight"] == 0.3


def test_weights_renormalize_without_pvn_history():
    score, breakdown = compute_score(
        ScoreComponents(
            test_score=100.0,
            pvn_achievements=None,
            regular_task_score=None,
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
            regular_task_score=50.0,
            profile_completeness=50.0,
        )
    )
    expected = 0.4 / 0.7 * 80.0 + 0.2 / 0.7 * 50.0 + 0.1 / 0.7 * 50.0
    assert abs(score - round(expected, 2)) < 0.01


def test_has_pvn_history_flag():
    assert has_pvn_history(ScoreComponents(pvn_achievements=10.0))
    assert not has_pvn_history(ScoreComponents())
