from scripts import validate_labeled


def test_labeled_validation_is_deterministic_and_well_formed():
    first = validate_labeled.run_labeled_validation()
    second = validate_labeled.run_labeled_validation()
    assert first["rows"] == second["rows"]
    assert first["vacancies"] == len(validate_labeled.LABELED_VACANCIES)
    assert first["vacancies"] >= 8


def test_labeled_labels_are_independent_of_scoring_formula():
    for vacancy in validate_labeled.LABELED_VACANCIES:
        for name in vacancy.relevant:
            candidate = next(item for item in validate_labeled.LABELED_CANDIDATES if item.name == name)
            assert candidate is not None
            assert vacancy.specialization == candidate.specialization


def test_labeled_precision_is_reported_for_both_modes():
    report = validate_labeled.run_labeled_validation()
    assert 0.0 <= report["mean_precision_at_5_without_rerank"] <= 1.0
    assert 0.0 <= report["mean_precision_at_5_with_rerank"] <= 1.0
    assert report["mean_precision_at_5_with_rerank"] >= report["mean_precision_at_5_without_rerank"]
    assert all(0.0 <= row["p_at_5_with_rerank"] <= 1.0 for row in report["rows"])
