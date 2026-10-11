import base64
import hashlib
import importlib.util
import json
import re
from dataclasses import dataclass

from backend.core.config import get_settings
from backend.services.llm import StubLLMClient, get_llm_client

MAX_HTML_BYTES = 60000
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024


@dataclass
class MockupFlaw:
    flaw_id: str
    title: str
    description: str
    region: dict


@dataclass
class Mockup:
    html: str
    scenario: str
    flaw: MockupFlaw
    source: str = "deterministic"


def renderer_available() -> bool:
    settings = get_settings()
    return bool(getattr(settings, "html_render_enabled", False)) and importlib.util.find_spec("playwright") is not None


FLAW_TEMPLATES: list[dict] = [
    {
        "flaw_id": "low_contrast",
        "title": "Недостаточный контраст текста",
        "description": "Подпись или текст набраны слишком бледным цветом на светлом фоне, контраст ниже 4,5:1 — текст плохо читается.",
        "region": {"x": 0.06, "y": 0.42, "w": 0.6, "h": 0.1},
        "html": """
        <div style="background:#ffffff;color:#e3e3e3;font-size:15px;padding:10px 12px;border-radius:10px;">Итоговая сумма к оплате: 4 320 ₽</div>
        """,
    },
    {
        "flaw_id": "tiny_tap_target",
        "title": "Слишком маленькая цель для нажатия",
        "description": "Кнопка закрытия или действия меньше 44×44 px, в неё трудно попасть пальцем на телефоне.",
        "region": {"x": 0.82, "y": 0.06, "w": 0.12, "h": 0.06},
        "html": """
        <div style="display:flex;justify-content:flex-end;"><span style="display:inline-flex;width:16px;height:16px;align-items:center;justify-content:center;color:#8891a8;font-size:14px;">✕</span></div>
        """,
    },
    {
        "flaw_id": "missing_state",
        "title": "Нет обратной связи о состоянии",
        "description": "Кнопка запускает долгую операцию, но интерфейс не показывает загрузку и не меняет состояние — пользователь не понимает, что происходит.",
        "region": {"x": 0.06, "y": 0.72, "w": 0.88, "h": 0.12},
        "html": """
        <div style="background:#2f5cff;color:#ffffff;text-align:center;padding:14px;border-radius:12px;font-size:16px;font-weight:600;">Оформить заказ</div>
        """,
    },
    {
        "flaw_id": "no_confirmation",
        "title": "Опасное действие без подтверждения",
        "description": "Удаление или отмена выполняется одним нажатием без подтверждения и без возможности отмены.",
        "region": {"x": 0.06, "y": 0.3, "w": 0.5, "h": 0.12},
        "html": """
        <div style="color:#5c6480;font-size:14px;padding:6px 0;text-decoration:underline;cursor:pointer;">Очистить корзину</div>
        """,
    },
    {
        "flaw_id": "unclear_hierarchy",
        "title": "Нарушена визуальная иерархия",
        "description": "Второстепенное действие выглядит так же ярко, как основное, и конкурирует с ним за внимание пользователя.",
        "region": {"x": 0.06, "y": 0.58, "w": 0.4, "h": 0.1},
        "html": """
        <div style="display:flex;gap:10px;"><span style="background:#2f5cff;color:#fff;padding:12px 18px;border-radius:10px;font-size:15px;">Оплатить</span></div>
        """,
    },
]

SCREEN_CONTEXTS = [
    {
        "title": "Корзина",
        "lines": ["Кроссовки Nike Air", "Носки спортивные"],
        "action": "Перейти к оплате",
    },
    {
        "title": "Оформление заказа",
        "lines": ["Курьер до двери · Завтра 10:00–18:00", "Промокод применён"],
        "action": "Подтвердить заказ",
    },
    {
        "title": "Профиль",
        "lines": ["Иван Петров", "ivan@example.com"],
        "action": "Сохранить изменения",
    },
]


def pick_flaw(seed: str) -> dict:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % len(FLAW_TEMPLATES)
    return FLAW_TEMPLATES[index]


def pick_context(seed: str) -> dict:
    digest = hashlib.sha256(("ctx:" + seed).encode("utf-8")).digest()
    return SCREEN_CONTEXTS[int.from_bytes(digest[:4], "big") % len(SCREEN_CONTEXTS)]


def build_mockup_html(seed: str) -> Mockup:
    flaw = pick_flaw(seed)
    context = pick_context(seed)
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #eef0f5;color:#1c2130;font-size:14px;">'
        f'<span>{line}</span><span style="color:#5c6480;">—</span></div>'
        for line in context["lines"]
    )
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; font-family: -apple-system, Segoe UI, Roboto, sans-serif; }}
body {{ margin:0; background:#f4f5f8; }}
.screen {{ width:100%; min-height:100vh; background:#ffffff; padding:16px; }}
.bar {{ display:flex; align-items:center; justify-content:space-between; padding:6px 0 14px; }}
.bar h1 {{ font-size:18px; margin:0; color:#1c2130; }}
.card {{ background:#ffffff; border-radius:14px; box-shadow:0 2px 10px rgba(20,25,50,0.06); padding:14px; margin-bottom:12px; }}
.muted {{ color:#8891a8; font-size:13px; }}
</style></head><body>
<div class="screen">
  <div class="bar"><h1>{context["title"]}</h1><div style="color:#8891a8;font-size:13px;">Очистить</div></div>
  <div class="card">{rows}</div>
  <div class="card">{flaw["html"]}</div>
  <div class="card"><div class="muted">Итого</div><div style="font-size:20px;font-weight:700;color:#1c2130;">4 320 ₽</div></div>
  <div style="background:#1c2130;color:#ffffff;text-align:center;padding:14px;border-radius:12px;font-size:16px;font-weight:600;">{context["action"]}</div>
</div>
</body></html>"""
    scenario = (
        f"Пользователь открыл экран «{context['title']}» мобильного приложения. "
        "Найдите одну ошибку дизайна: выделите проблемный элемент и опишите, что именно нарушено."
    )
    return Mockup(
        html=html,
        scenario=scenario,
        flaw=MockupFlaw(
            flaw_id=flaw["flaw_id"],
            title=flaw["title"],
            description=flaw["description"],
            region=flaw["region"],
        ),
    )


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


async def build_mockup_png(seed: str) -> Mockup | None:
    if not renderer_available():
        return None
    mockup = build_mockup_html(seed)
    try:
        png = await render_html_to_png(mockup.html)
    except Exception:
        return None
    if len(png) > MAX_SCREENSHOT_BYTES:
        return None
    return mockup, png


def to_data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def region_contains(region: dict, annotation: dict) -> bool:
    if not annotation:
        return False
    cx = annotation.get("x", 0) + annotation.get("w", 0) / 2
    cy = annotation.get("y", 0) + annotation.get("h", 0) / 2
    return (
        region["x"] <= cx <= region["x"] + region["w"]
        and region["y"] <= cy <= region["y"] + region["h"]
    )


def normalize_annotation(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        x = float(raw.get("x"))
        y = float(raw.get("y"))
        w = float(raw.get("w"))
        h = float(raw.get("h"))
    except (TypeError, ValueError):
        return None
    if w <= 0.01 or h <= 0.01:
        return None
    return {
        "x": max(0.0, min(x, 1.0)),
        "y": max(0.0, min(y, 1.0)),
        "w": max(0.0, min(w, 1.0)),
        "h": max(0.0, min(h, 1.0)),
    }


VISION_GRADE_PROMPT = """Ты оцениваешь ответ дизайнера в тестовом задании.
На изображении мобильного интерфейса намеренно внесена одна ошибка дизайна.
Эталон ошибки: «{reference}».
Кандидат выделил область и написал пояснение: «{note}».
Оцени, верно ли кандидат нашёл именно эту ошибку и содержательно ли объяснил её.
Верни строго JSON без markdown: {{"correct": true|false, "feedback": "одно короткое предложение на русском"}}."""


async def grade_annotation(image_data_url: str, reference: str, note: str, annotation: dict | None, region: dict | None) -> tuple[bool, str]:
    note = (note or "").strip()
    if not note:
        return False, "Нет пояснения к выделенной области."
    region_ok = region_contains(region, annotation) if region and annotation else False
    client = get_llm_client()
    if not isinstance(client, StubLLMClient):
        try:
            raw = await client.complete_with_image(
                VISION_GRADE_PROMPT.format(reference=reference, note=note[:600]),
                image_data_url,
            )
            parsed = _parse_grade(raw or "")
            if parsed is not None:
                correct, feedback = parsed
                if correct and not region_ok:
                    return True, "Ошибка найдена и объяснена."
                return correct, feedback
        except Exception:
            pass
    return region_ok, "Проверено по выделенной области." if region_ok else "Выделена не та область."


def _parse_grade(raw: str) -> tuple[bool, str] | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "correct" not in data:
        return None
    return bool(data["correct"]), str(data.get("feedback", ""))[:300]
