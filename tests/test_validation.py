import asyncio
import random

import pytest

from backend.api.routes import candidates
from backend.core.testing import VERDICT_SUGGEST_HIGHER, adaptive_verdict, suggested_grade
from scripts import validate


def test_dataset_has_exact_independent_labels_and_varied_adversarial_cases():
    cases = validate.stress_dataset()
    expected = 12 * len(validate.CASE_INPUTS)
    assert len(cases) == expected
    assert len({case["id"] for case in cases}) == expected
    assert len({case["vacancy"]["id"] for case in cases}) == 12
    assert {case["case_type"] for case in cases} == {inputs[0] for inputs in validate.CASE_INPUTS}
    for case in cases:
        assert case["claimed"]["stack"] == case["vacancy"]["stack"]
        assert case["claimed"]["correct_count"] in (None, 0, 1)
        assert case["verified"]["correct_count"] >= 4
        assert not case["claimed"]["relevant"]
        assert case["verified"]["relevant"]


def test_stress_counts_show_verified_never_loses_to_claimed():
    result = validate.run_stress_suite("lexical")
    rows = result["rows"]
    assert result["pairs"] == len(rows)
    assert result["verified_higher_count"] == sum(row["verified_higher"] for row in rows)
    assert result["claimed_higher_count"] == sum(row["claimed_higher"] for row in rows)
    assert result["tie_count"] == sum(row["tie"] for row in rows)
    assert (result["verified_higher_count"], result["tie_count"], result["claimed_higher_count"]) == (84, 0, 0)
    assert result["perfect_claimed_stack_count"] == 84
    assert result["top5_slots"] == 60
    assert result["precision_at_5"] == result["relevant_top5_slots"] / result["top5_slots"]


def test_actual_card_scoring_is_called_and_score_mutation_changes_results(monkeypatch):
    calls = []
    original = validate.build_card

    def record_call(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(validate, "build_card", record_call)
    initial = validate.run_stress_suite("lexical")
    assert len(calls) == 168
    monkeypatch.setattr(candidates, "compute_score", lambda components: (0.0, {}))
    changed = validate.run_stress_suite("lexical")
    assert changed["rows"] != initial["rows"]


def test_semantic_mock_session_and_lexical_fallback_agree_on_gate():
    lexical = validate.run_stress_suite("lexical")
    semantic = validate.run_stress_suite("semantic_mock")
    lexical_row = next(row for row in lexical["rows"] if row["case_type"] == "misleading_semantic_mock")
    semantic_row = next(row for row in semantic["rows"] if row["id"] == lexical_row["id"])
    assert lexical_row["verified_higher"]
    assert semantic_row["verified_higher"]
    assert (semantic["verified_higher_count"], semantic["tie_count"], semantic["claimed_higher_count"]) == (84, 0, 0)


@pytest.mark.parametrize("mode", ["lexical", "semantic_mock"])
def test_no_completed_session_keyword_stuffing_cannot_outrank_proven_profile(mode):
    result = validate.run_stress_suite(mode)
    rows = [row for row in result["rows"] if row["case_type"] == "unverified_keyword_stuffing"]
    assert len(rows) == 12
    for row in rows:
        assert row["claimed_correct"] is None
        assert row["verified_score"] == 100.0
        assert row["verified_higher"]
        assert not row["tie"]
        assert not row["claimed_higher"]


def test_real_embedding_pipeline_has_mocked_vectors_cache_and_unavailable_fallback():
    result = asyncio.run(validate.run_embedding_mock_checks())
    assert result["passed"] == result["checks"] == 3
    assert result["embed_calls"] == 3
    assert result["similarity"] == pytest.approx(0.8)


def test_test_retest_is_reproducible_and_reports_actual_recommendations():
    result = validate.run_test_retest(random.Random(validate.SEED))
    assert result == validate.run_test_retest(random.Random(validate.SEED))
    assert 0 < result["verdict_matches"] < result["trials"]
    assert 0 < result["recommendation_matches"] <= result["trials"]


def test_report_is_reproducible_and_explicit_about_synthetic_limits():
    first = validate.run_validation()
    assert first == validate.run_validation()
    report = validate.render_report(first)
    assert "не оценка качества подбора на рынке труда" in report
    assert "PostgreSQL pgvector branch" in report
    assert str(12 * len(validate.CASE_INPUTS)) in report


def test_adaptation_still_uses_backend_verdict_and_grade_suggestion():
    verdict = adaptive_verdict(5, 5, "middle")
    assert verdict == VERDICT_SUGGEST_HIGHER
    assert suggested_grade("middle", verdict) == "senior"
