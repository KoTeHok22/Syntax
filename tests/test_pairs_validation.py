import math

import pytest

from scripts import validate_pairs


def grades_for(ranking):
    return {name: (2 if name in ranking[:2] else 0) for name in ranking}


def test_precision_at_k_on_known_example():
    ranking = ["a", "b", "c", "d", "e"]
    grades = {"a": 2, "b": 0, "c": 2, "d": 0, "e": 0}
    assert validate_pairs.precision_at_k(ranking, grades, 5) == pytest.approx(2 / 5)
    assert validate_pairs.precision_at_k(ranking, grades, 2) == pytest.approx(1 / 2)
    assert validate_pairs.precision_at_k(ranking, grades, 1) == pytest.approx(1.0)


def test_recall_at_k_on_known_example():
    ranking = ["a", "b", "c", "d", "e"]
    grades = {"a": 2, "b": 0, "c": 2, "d": 0, "e": 0}
    assert validate_pairs.recall_at_k(ranking, grades, 10) == pytest.approx(1.0)
    assert validate_pairs.recall_at_k(ranking, grades, 2) == pytest.approx(0.5)


def test_ndcg_at_k_matches_bruteforce():
    ranking = ["a", "b", "c", "d"]
    grades = {"a": 2, "b": 2, "c": 0, "d": 0}
    dcg = 1 / math.log2(2) + 1 / math.log2(3)
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    assert validate_pairs.ndcg_at_k(ranking, grades, 4) == pytest.approx(dcg / idcg)


def test_ndcg_at_k_penalizes_relevant_below_irrelevant():
    ranking = ["b", "a", "c", "d"]
    grades = {"a": 2, "b": 0, "c": 0, "d": 2}
    assert 0.0 < validate_pairs.ndcg_at_k(ranking, grades, 4) < 1.0


def test_ndcg_at_k_perfect_and_zero_examples():
    perfect = {"a": 2, "b": 2, "c": 0}
    assert validate_pairs.ndcg_at_k(["a", "b", "c"], perfect, 3) == pytest.approx(1.0)
    assert validate_pairs.ndcg_at_k(["c", "b", "a"], perfect, 3) < 1.0


def test_reciprocal_rank_on_known_example():
    assert validate_pairs.reciprocal_rank(["x", "a", "b"], {"a": 2, "b": 2}) == pytest.approx(1 / 2)
    assert validate_pairs.reciprocal_rank(["a", "b"], {"a": 2, "b": 2}) == pytest.approx(1.0)
    assert validate_pairs.reciprocal_rank(["x", "y"], {"a": 2}) == pytest.approx(0.0)


def test_dataset_shape_and_labels():
    assert len(validate_pairs.PAIR_VACANCIES) == 12
    for vacancy in validate_pairs.PAIR_VACANCIES:
        assert 4 <= len(vacancy.candidates) <= 8
        assert any(c.grade_label == 2 for c in vacancy.candidates)
        assert any(c.grade_label == 0 for c in vacancy.candidates)
        names = [c.name for c in vacancy.candidates]
        assert len(names) == len(set(names))
        for candidate in vacancy.candidates:
            assert candidate.grade_label in (0, 1, 2)


def test_validation_is_reproducible_with_fixed_seed():
    first = validate_pairs.run_validation()
    second = validate_pairs.run_validation()
    assert first == second
    assert first["seed"] == validate_pairs.SEED
    assert first["results"] == second["results"]


def test_metrics_are_bounded_and_gate_delta_is_reported():
    results = validate_pairs.run_validation()
    for (mode, gate), result in results["results"].items():
        assert 0.0 <= result["precision_at_5"] <= 1.0
        assert 0.0 <= result["ndcg_at_5"] <= 1.0
        assert 0.0 <= result["mrr"] <= 1.0
        assert 0.0 <= result["recall_at_10"] <= 1.0
        assert result["gate"] is gate
        assert result["mode"] == mode
    report = validate_pairs.render_report(results)
    assert "без gate" in report and "с gate" in report
    assert "Precision@5" in report


def test_gate_changes_ranking_only_through_proof_tier():
    lexical_before = validate_pairs.evaluate("lexical", False)
    lexical_after = validate_pairs.evaluate("lexical", True)
    assert lexical_before["rows"] == lexical_after["rows"] or any(
        before["ranking"] != after["ranking"]
        for before, after in zip(lexical_before["rows"], lexical_after["rows"])
    )
