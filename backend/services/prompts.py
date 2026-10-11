import json
import os
import re
from pathlib import Path

PROMPTS_PATH = Path(os.environ.get("PROMPTS_PATH", Path(__file__).resolve().parent.parent.parent / "prompts.json"))

_cache: dict = {"mtime": None, "data": {}}


def _read_file() -> dict:
    try:
        with PROMPTS_PATH.open(encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def load_prompts() -> dict:
    try:
        mtime = PROMPTS_PATH.stat().st_mtime
    except OSError:
        return _cache["data"] if isinstance(_cache["data"], dict) else {}
    if _cache["mtime"] != mtime:
        _cache["data"] = _read_file()
        _cache["mtime"] = mtime
    return _cache["data"]


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
    def substitute(match: re.Match) -> str:
        key = match.group(1)
        return str(values[key]) if key in values else match.group(0)

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", substitute, template)


def reload_prompts() -> None:
    _cache["mtime"] = None
    _cache["data"] = {}
