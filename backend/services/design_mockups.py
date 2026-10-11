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
        "region": {"x": 0.06, "y": 0.6, "w": 0.6, "h": 0.08},
        "html": """
        <div style="background:#ffffff;color:#e6e6e6;font-size:15px;padding:10px 12px;border-radius:10px;">Итоговая сумма к оплате уточняется</div>
        """,
    },
    {
        "flaw_id": "tiny_tap_target",
        "title": "Слишком маленькая цель для нажатия",
        "description": "Кнопка закрытия или действия меньше 44×44 px, в неё трудно попасть пальцем на телефоне.",
        "region": {"x": 0.86, "y": 0.02, "w": 0.1, "h": 0.05},
        "html": """
        <div style="display:flex;justify-content:flex-end;"><span style="display:inline-flex;width:16px;height:16px;align-items:center;justify-content:center;color:#8891a8;font-size:14px;">✕</span></div>
        """,
    },
    {
        "flaw_id": "missing_state",
        "title": "Нет обратной связи о состоянии",
        "description": "Кнопка запускает долгую операцию, но интерфейс не показывает загрузку и не меняет состояние — пользователь не понимает, что происходит.",
        "region": {"x": 0.06, "y": 0.6, "w": 0.88, "h": 0.08},
        "html": """
        <div style="background:#2f5cff;color:#ffffff;text-align:center;padding:14px;border-radius:12px;font-size:16px;font-weight:600;">{action}</div>
        """,
    },
    {
        "flaw_id": "no_confirmation",
        "title": "Опасное действие без подтверждения",
        "description": "Удаление или очистка выполняется одним нажатием без подтверждения и без возможности отмены.",
        "region": {"x": 0.06, "y": 0.3, "w": 0.5, "h": 0.1},
        "html": """
        <div style="color:#5c6480;font-size:14px;padding:6px 0;text-decoration:underline;cursor:pointer;">Очистить всё</div>
        """,
    },
    {
        "flaw_id": "unclear_hierarchy",
        "title": "Нарушена визуальная иерархия",
        "description": "Второстепенное действие оформлено так же ярко, как основное, и конкурирует с ним за внимание пользователя.",
        "region": {"x": 0.06, "y": 0.42, "w": 0.4, "h": 0.09},
        "html": """
        <div style="display:flex;gap:10px;"><span style="background:#2f5cff;color:#fff;padding:12px 18px;border-radius:10px;font-size:15px;">{action}</span></div>
        """,
    },
]

PRODUCTS = [
    "Кроссовки Nike Air",
    "Куртка Columbia",
    "Рюкзак Eastpak",
    "Наушники Sony",
    "Термокружка Stanley",
    "Клавиатура Logitech",
    "Кресло Ergo",
    "Лампа Xiaomi",
    "Футболка Uniqlo",
    "Часы Casio",
]
NOTES = [
    "Заказ №4821 · оплачен",
    "Промокод SALE10 применён",
    "Курьер до двери · завтра 10:00–18:00",
    "Самовывоз · пункт на Ленина, 5",
    "Доставка 2–3 дня · СДЭК",
]
ACTIONS = [
    "Перейти к оплате",
    "Подтвердить заказ",
    "Сохранить изменения",
    "Оформить доставку",
    "Отправить заявку",
]

SCREEN_CONTEXTS = [
    {"title": "Корзина"},
    {"title": "Оформление заказа"},
    {"title": "Профиль"},
    {"title": "Доставка"},
    {"title": "Подтверждение заказа"},
    {"title": "Мои заказы"},
]


def _seeded(seed: str, index: int) -> bytes:
    return hashlib.sha256(f"{seed}:{index}".encode("utf-8")).digest()


def pick_flaw(seed: str) -> dict:
    digest = _seeded(seed, 0)
    return FLAW_TEMPLATES[int.from_bytes(digest[:4], "big") % len(FLAW_TEMPLATES)]


def pick_context(seed: str) -> dict:
    digest = _seeded(seed, 1)
    return SCREEN_CONTEXTS[int.from_bytes(digest[:4], "big") % len(SCREEN_CONTEXTS)]


def pick_variety(seed: str) -> dict:
    digest = _seeded(seed, 2)
    return {
        "product": PRODUCTS[int.from_bytes(digest[0:4], "big") % len(PRODUCTS)],
        "note": NOTES[int.from_bytes(digest[4:8], "big") % len(NOTES)],
        "action": ACTIONS[int.from_bytes(digest[8:12], "big") % len(ACTIONS)],
        "price": 490 + int.from_bytes(digest[12:16], "big") % 12900,
        "quantity": 1 + int.from_bytes(digest[16:18], "big") % 4,
    }


def build_mockup_html(seed: str) -> Mockup:
    flaw = pick_flaw(seed)
    context = pick_context(seed)
    variety = pick_variety(seed)
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #eef0f5;color:#1c2130;font-size:14px;">'
        f'<span>{line}</span><span style="color:#5c6480;">—</span></div>'
        for line in [variety["product"], variety["note"]]
    )
    flaw_html = flaw["html"].replace("{product}", variety["product"]).replace("{action}", variety["action"])
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
  <div class="bar"><h1>{context["title"]}</h1><div style="color:#8891a8;font-size:13px;">Закрыть</div></div>
  <div class="card">{rows}</div>
  <div class="card">{flaw_html}</div>
  <div class="card"><div class="muted">Итого · {variety["quantity"]} шт.</div><div style="font-size:20px;font-weight:700;color:#1c2130;">{variety["price"]:,} ₽</div></div>
  <div style="background:#1c2130;color:#ffffff;text-align:center;padding:14px;border-radius:12px;font-size:16px;font-weight:600;">{variety["action"]}</div>
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


MOCKUP_PROMPT = """Сгенерируй HTML мобильного экрана приложения «{app}».
Экран: «{title}». Сценарий: {scenario}
Внеси ровно одну намеренную ошибку дизайна: {flaw}.
Требования: ширина 390px, белый фон, крупные читаемые шрифты, только инлайн-стили, без скриптов.
Верни строго HTML-документ без markdown и без пояснений."""


async def build_llm_mockup_html(seed: str) -> Mockup:
    deterministic = build_mockup_html(seed)
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return deterministic
    try:
        raw = await client.complete(
            MOCKUP_PROMPT.format(
                app="Мобильный клиент",
                title=pick_context(seed)["title"],
                scenario=deterministic.scenario,
                flaw=deterministic.flaw.description,
            )
        )
    except Exception:
        return deterministic
    html = _extract_html(raw or "")
    if not html or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        return deterministic
    return Mockup(
        html=html,
        scenario=deterministic.scenario,
        flaw=MockupFlaw(
            flaw_id=deterministic.flaw.flaw_id,
            title=deterministic.flaw.title,
            description=deterministic.flaw.description,
            region={},
        ),
        source="llm",
    )


def _extract_html(raw: str) -> str | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if "<" not in text or ">" not in text:
        return None
    lowered = text.lower()
    if "<script" in lowered or "javascript:" in lowered or "http://" in lowered or "https://" in lowered:
        return None
    start = lowered.find("<!doctype")
    if start == -1:
        start = lowered.find("<html")
    if start == -1:
        start = text.find("<")
    return text[start:]


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
    if not annotation or not region or "x" not in region:
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


VISION_GRADE_PROMPT = """Ты проверяешь ответ дизайнера. На изображении мобильного экрана намеренно внесена одна ошибка дизайна.
Какой именно дефект заложен: «{reference}».
Что сделал кандидат: выделил область и написал пояснение: «{note}».
Оцени по двум условиям: (1) выделенная область действительно указывает на заложенный дефект; (2) пояснение называет суть нарушения.
Отвечай доброжелательно и по делу, без домыслов о том, чего кандидат «не заметил».
Верни строго JSON без markdown: {{"correct": true|false, "feedback": "одно короткое предложение на русском"}}"""


async def grade_annotation(image_data_url: str, reference: str, note: str, annotation: dict | None, region: dict | None) -> tuple[bool, str]:
    note = (note or "").strip()
    if not note:
        return False, "Пояснение не заполнено — опишите, что нарушено."
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
                return parsed
        except Exception:
            pass
    if region_ok:
        return True, "Область указана верно, пояснение принято."
    return False, "Выделенная область не совпадает с заложенным дефектом."


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
