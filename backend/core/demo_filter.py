E2E_MARKERS = (
    "E2E ",
    "e2e-",
    " e2e ",
    "@e2e.",
    "@syntax.dev",
    "для e2e-прогона",
)


def is_demo_visible(*values: str | None) -> bool:
    for value in values:
        if value is None:
            continue
        lowered = value.lower()
        if any(marker.lower() in lowered for marker in E2E_MARKERS):
            return False
    return True
