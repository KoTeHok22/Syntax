import json
import os
from functools import lru_cache
from pathlib import Path

PROMPTS_PATH = Path(os.environ.get("PROMPTS_PATH", Path(__file__).resolve().parent.parent.parent / "prompts.json"))


@lru_cache(maxsize=1)
def load_prompts() -> dict:
    try:
        with PROMPTS_PATH.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def get_prompt(key: str, default: str) -> str:
    section = load_prompts().get(key)
    if isinstance(section, dict):
        value = section.get("prompt")
        if isinstance(value, str):
            return value
    if isinstance(section, str):
        return section
    return default


def get_examples(key: str) -> list:
    section = load_prompts().get(key)
    if isinstance(section, dict):
        examples = section.get("examples")
        if isinstance(examples, list):
            return examples
    return []


def render(template: str, **values) -> str:
    import re

    def substitute(match: re.Match) -> str:
        key = match.group(1)
        return str(values[key]) if key in values else match.group(0)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", substitute, template)


def reload_prompts() -> None:
    load_prompts.cache_clear()
