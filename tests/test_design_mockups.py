from backend.services.design_mockups import (
    FLAW_TEMPLATES,
    build_mockup_html,
    normalize_annotation,
    pick_flaw,
    region_contains,
)


def test_pick_flaw_is_deterministic():
    first = pick_flaw("seed-1")
    second = pick_flaw("seed-1")
    assert first["flaw_id"] == second["flaw_id"]
    assert first["flaw_id"] in {flaw["flaw_id"] for flaw in FLAW_TEMPLATES}


def test_build_mockup_html_has_flaw_and_scenario():
    mockup = build_mockup_html("some-seed")
    assert mockup.html.startswith("<!DOCTYPE html>")
    assert mockup.flaw.description
    assert mockup.flaw.region["w"] > 0
    assert mockup.scenario
    assert "₽" in mockup.html


def test_mockups_differ_between_seeds():
    first = build_mockup_html("candidate:1")
    second = build_mockup_html("candidate:2")
    assert first.html != second.html


def test_same_seed_is_identical():
    assert build_mockup_html("candidate:7").html == build_mockup_html("candidate:7").html


def test_empty_region_never_matches():
    assert not region_contains({}, {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1})
    assert not region_contains(None, {"x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1})


def test_region_contains_uses_rectangle_center():
    region = {"x": 0.0, "y": 0.0, "w": 0.2, "h": 0.2}
    assert region_contains(region, {"x": 0.05, "y": 0.05, "w": 0.05, "h": 0.05})
    assert not region_contains(region, {"x": 0.5, "y": 0.5, "w": 0.05, "h": 0.05})
    assert not region_contains(region, None)


def test_normalize_annotation_rejects_degenerate_and_clamps():
    assert normalize_annotation(None) is None
    assert normalize_annotation({"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.1}) is None
    assert normalize_annotation({"x": "bad", "y": 0.1, "w": 0.2, "h": 0.2}) is None
    clamped = normalize_annotation({"x": -1, "y": 0.5, "w": 2, "h": 0.5})
    assert clamped == {"x": 0.0, "y": 0.5, "w": 1.0, "h": 0.5}
