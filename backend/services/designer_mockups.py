import base64
import importlib.util
import json
import re
from dataclasses import dataclass, field

from backend.core.config import get_settings
from backend.services.llm import StubLLMClient, get_llm_client

MAX_HTML_BYTES = 60000
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
MAX_DEFECTS = 8
ALLOWED_HEURISTICS = {"fitts_targets", "contrast", "hierarchy", "nielsen_user_control", "nielsen_visibility", "nielsen_consistency", "nielsen_error_prevention"}


@dataclass
class GeneratedMockup:
    html: str
    scenario: str
    defects: list[dict] = field(default_factory=list)
    source: str = "deterministic"


def renderer_available() -> bool:
    settings = get_settings()
    return bool(getattr(settings, "html_render_enabled", False)) and importlib.util.find_spec("playwright") is not None


def strip_html(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if len(text.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("Слишком большой HTML-макет")
    return text


def clean_defects(items) -> list[dict]:
    defects = []
    seen = set()
    if not isinstance(items, list):
        return defects
    for item in items:
        if not isinstance(item, dict):
            continue
        heuristic = str(item.get("heuristic_id", "")).strip()
        description = " ".join(str(item.get("description", "")).split())[:300]
        if heuristic not in ALLOWED_HEURISTICS or not description or heuristic in seen:
            continue
        seen.add(heuristic)
        defects.append({
            "heuristic_id": heuristic,
            "description": description,
            "severity": item.get("severity") if item.get("severity") in {"low", "medium", "high"} else "medium",
        })
        if len(defects) >= MAX_DEFECTS:
            break
    return defects


def parse_generation(raw: str) -> tuple[str, str, list[dict]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    html = strip_html(str(payload.get("html", "")))
    if not html:
        raise ValueError("HTML отсутствует")
    scenario = " ".join(str(payload.get("scenario", "")).split())[:4000]
    if len(scenario) < 10:
        raise ValueError("Сценарий короче 10 символов")
    defects = clean_defects(payload.get("defects"))
    if not defects:
        raise ValueError("Эталон дефектов пуст")
    return html, scenario, defects


async def generate_mockup() -> GeneratedMockup | None:
    if not renderer_available():
        return None
    settings = get_settings()
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return None
    prompt = (
        "Сгенерируй один HTML-документ случайного, но правдоподобного мобильного веб-интерфейса "
        "(какой-либо продуктовый сценарий: доставка, бронирование, оформление заказа, подписка, профиль). "
        "Инлайн CSS только, без внешних ресурсов, изображений, скриптов и шрифтов; ширина фиксирована 100%, "
        "контент читается на экране 390x650. Намеренно внеси от 3 до 5 реалистичных ошибок UX из допустимых "
        "эвристик: fitts_targets, contrast, hierarchy, nielsen_user_control, nielsen_visibility, "
        "nielsen_consistency, nielsen_error_prevention. Текст интерфейса — на русском. "
        "Верни строго JSON без пояснений: {\"html\": \"...\", \"scenario\": \"краткое задание на русском\", "
        "\"defects\": [{\"heuristic_id\": \"<id>\", \"description\": \"что именно нарушено\", \"severity\": \"low|medium|high\"}]}. "
        "Поля defects должны описывать только реально внесённые ошибки."
    )
    try:
        raw = await client.complete(prompt)
        html, scenario, defects = parse_generation(raw or "")
    except Exception:
        return None
    return GeneratedMockup(html=html, scenario=scenario, defects=defects, source="llm")


async def render_html_to_png(html: str) -> bytes:
    if importlib.util.find_spec("playwright") is None:
        raise ValueError("HTML-рендерер недоступен")
    settings = get_settings()
    from playwright.async_api import async_playwright

    timeout_ms = int(getattr(settings, "html_render_timeout_seconds", 30) * 1000)
    width = int(getattr(settings, "html_render_viewport_width", 390))
    height = int(getattr(settings, "html_render_viewport_height", 650))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
            await page.set_content(html, wait_until="load", timeout=timeout_ms)
            return await page.screenshot(full_page=False, type="png", timeout=timeout_ms)
        finally:
            await browser.close()


def mockup_data_url(png: bytes) -> str:
    if len(png) > MAX_SCREENSHOT_BYTES:
        raise ValueError("Отрендеренный макет больше 2 МБ")
    return f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"
