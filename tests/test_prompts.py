from backend.services.prompts import get_examples, get_prompt, render


def test_prompts_load_from_json():
    assert get_prompt("task_generation", "fallback") != "fallback"
    assert get_prompt("design_grading", "fallback") != "fallback"


def test_examples_are_present():
    examples = get_examples("task_generation")
    assert examples
    assert "statement" in examples[0]


def test_render_keeps_literal_braces():
    template = 'Верни JSON: {"correct": true} и подставь {reference}'
    out = render(template, reference="дефект")
    assert "дефект" in out
    assert '{"correct": true}' in out


def test_missing_key_is_left_intact():
    assert render("значение {unknown}", known="x") == "значение {unknown}"
