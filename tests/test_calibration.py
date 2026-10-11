import random
from functools import lru_cache

from scripts import calibrate_items as cal


@lru_cache(maxsize=None)
def run_simulation(seed=cal.SEED):
    return cal.simulate(random.Random(seed))


def test_simulation_is_reproducible_with_fixed_seed():
    first = cal.simulate(random.Random(cal.SEED))
    second = cal.simulate(random.Random(cal.SEED))
    assert first == second


def test_different_seed_changes_reliability():
    first = cal.simulate(random.Random(cal.SEED))
    second = cal.simulate(random.Random(cal.SEED + 1))
    assert first["reliability"] != second["reliability"]


def test_se_theta_is_positive_and_finite():
    result = run_simulation()
    assert result["mean_se_theta"] > 0
    assert 0 < result["se_theta_by_level"]["0.0"] < 1
    for value in result["se_theta_by_level"].values():
        assert 0 < value < 1


def test_reliability_in_unit_interval():
    result = run_simulation()
    assert 0.0 <= result["reliability"] <= 1.0


def test_separation_and_strata_derive_from_reliability():
    result = run_simulation()
    separation = cal.separation_from_reliability(result["reliability"])
    strata = cal.strata_from_separation(separation)
    assert abs(separation - result["separation_index"]) < 0.01
    assert abs(strata - result["strata"]) < 0.05


def test_distinguishable_bands_in_valid_range():
    result = run_simulation()
    assert 1 <= result["distinguishable_bands"] <= 3
    assert result["distinguishable_bands"] <= result["benchmark_bands_high"]
    assert result["benchmark_bands_low"] <= result["benchmark_bands_high"]


def test_probability_and_information_bounds():
    assert cal.probability_correct(0.0, 1.0, 0.0) == 0.5
    assert 0.0 < cal.probability_correct(-5.0, 1.0, 0.0) < 0.5
    assert 0.5 < cal.probability_correct(5.0, 1.0, 0.0) < 1.0
    info = cal.item_information(0.0, 1.0, 0.0)
    assert 0.0 < info <= 0.25


def test_standard_error_matches_information():
    items = [{"a": 1.0, "b": 0.0}]
    info = cal.test_information(0.0, items)
    assert cal.standard_error(0.0, items) == 1.0 / (info ** 0.5)


def test_spearman_brown_increases_with_length():
    reliability = 0.7
    short = cal.spearman_brown(reliability, 20, 10)
    same = cal.spearman_brown(reliability, 20, 20)
    long = cal.spearman_brown(reliability, 20, 40)
    assert short < reliability < long
    assert abs(same - reliability) < 1e-9


def test_grade_pass_difficulty_is_ordered():
    result = run_simulation()
    assert result["grade_pass_difficulty"]["junior"] < result["grade_pass_difficulty"]["middle"]
    assert result["grade_pass_difficulty"]["middle"] < result["grade_pass_difficulty"]["senior"]


def test_item_bank_covers_all_concepts():
    items = cal.build_item_bank(random.Random(cal.SEED))
    assert len(items) == len(cal.CONCEPTS)
    grades = {item["grade"] for item in items}
    assert grades == {"junior", "middle", "senior"}
