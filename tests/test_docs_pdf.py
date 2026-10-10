from scripts.build_docs_pdf import inline


def test_inline_code_preserves_content_without_control_characters():
    output = inline("Set `LLM_BASE_URL` and `[]` before running")
    assert "LLM_BASE_URL" in output
    assert "[]" in output
    assert "\x01" not in output


def test_inline_code_escapes_markup():
    output = inline("`a < b & c`")
    assert "a &lt; b &amp; c" in output
