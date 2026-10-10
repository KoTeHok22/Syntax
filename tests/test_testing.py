from datetime import datetime, timedelta, timezone

from backend.core.testing import (
    VERDICT_CONFIRMED,
    VERDICT_SUGGEST_HIGHER,
    VERDICT_SUGGEST_LOWER,
    adaptive_verdict,
    grade_change_allowed,
    grade_confirmation_active,
    pass_threshold,
    result_score,
    suggested_grade,
)


def test_adaptive_verdict_boundaries():
    assert adaptive_verdict(5, 5, "junior") == VERDICT_SUGGEST_HIGHER
    assert adaptive_verdict(4, 5, "junior") == VERDICT_CONFIRMED
    assert adaptive_verdict(3, 5, "junior") == VERDICT_CONFIRMED
    assert adaptive_verdict(2, 5, "junior") == VERDICT_SUGGEST_LOWER
    assert adaptive_verdict(0, 5, "junior") == VERDICT_SUGGEST_LOWER
    assert adaptive_verdict(4, 5, "middle") == VERDICT_CONFIRMED
    assert adaptive_verdict(3, 5, "middle") == VERDICT_SUGGEST_LOWER
    assert adaptive_verdict(4, 5, "senior") == VERDICT_SUGGEST_LOWER


def test_pass_threshold_per_grade():
    assert pass_threshold("junior") == 60
    assert pass_threshold("middle") == 75
    assert pass_threshold("senior") == 85
    assert pass_threshold("unknown") == 60


def test_grade_confirmation_active_window():
    fresh = datetime.now(timezone.utc) - timedelta(days=30)
    stale = datetime.now(timezone.utc) - timedelta(days=400)
    assert grade_confirmation_active(fresh, valid_months=12)
    assert not grade_confirmation_active(stale, valid_months=12)
    assert not grade_confirmation_active(None, valid_months=12)


def test_suggested_grade_never_forces_downgrade():
    assert suggested_grade("junior", VERDICT_SUGGEST_LOWER) is None
    assert suggested_grade("middle", VERDICT_SUGGEST_LOWER) == "junior"
    assert suggested_grade("middle", VERDICT_SUGGEST_HIGHER) == "senior"
    assert suggested_grade("senior", VERDICT_SUGGEST_HIGHER) is None
    assert suggested_grade("middle", VERDICT_CONFIRMED) is None


def test_result_score_normalization():
    assert result_score(4, 5) == 80
    assert result_score(0, 0) == 0


def test_grade_cooldown_blocks_recent_change():
    recently = datetime.now(timezone.utc) - timedelta(days=30)
    long_ago = datetime.now(timezone.utc) - timedelta(days=100)
    assert not grade_change_allowed(recently, cooldown_months=3)
    assert grade_change_allowed(long_ago, cooldown_months=3)
    assert grade_change_allowed(None, cooldown_months=3)
