import base64
import hashlib
import importlib.util
import json
import re
from dataclasses import dataclass

from backend.core.config import get_settings
from backend.services.llm import StubLLMClient, get_llm_client
from backend.services.prompts import get_examples, get_prompt, render

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
        "description": "Подпись набрана почти белым цветом на белом фоне — текст практически не читается.",
        "region": {"x": 0.05, "y": 0.36, "w": 0.7, "h": 0.07},
        "html": """
        <div style="color:#f0f0f0;font-size:15px;">Итоговая сумма к оплате уточняется</div>
        """,
    },
    {
        "flaw_id": "tiny_tap_target",
        "title": "Слишком маленькая цель для нажатия",
        "description": "Кнопка действия размером около 16×16 px — в неё почти невозможно попасть пальцем на телефоне.",
        "region": {"x": 0.08, "y": 0.36, "w": 0.09, "h": 0.05},
        "html": """
        <div><span style="display:inline-flex;width:16px;height:16px;align-items:center;justify-content:center;color:#2f5cff;font-size:14px;border:1px solid #cdd3e0;border-radius:4px;">＋</span></div>
        """,
    },
    {
        "flaw_id": "clipped_text",
        "title": "Обрезанный текст надписи",
        "description": "Подпись обрезана и не помещается в контейнер — часть текста скрыта, пользователь не видит полное значение.",
        "region": {"x": 0.05, "y": 0.36, "w": 0.9, "h": 0.06},
        "html": """
        <div style="background:#eef1f7;border-radius:10px;padding:12px 14px;overflow:hidden;white-space:nowrap;text-overflow:clip;font-size:15px;color:#1c2130;">Доставка курьером до двери по адресу: г. Москва, улица Ленина, дом 14, корпус 3</div>
        """,
    },
    {
        "flaw_id": "overlapping_elements",
        "title": "Элементы перекрывают друг друга",
        "description": "Кнопка наложена поверх текста и скрывает его часть — содержимое нечитаемо из-за перекрытия.",
        "region": {"x": 0.05, "y": 0.34, "w": 0.9, "h": 0.1},
        "html": """
        <div style="position:relative;height:72px;border:1px solid #e6e9f0;border-radius:12px;">
          <div style="position:absolute;left:14px;top:14px;right:14px;font-size:15px;color:#1c2130;">Ваш заказ будет доставлен завтра с 10:00 до 18:00</div>
          <div style="position:absolute;left:14px;top:26px;background:#2f5cff;color:#fff;padding:10px 16px;border-radius:10px;font-size:15px;">Изменить адрес</div>
        </div>
        """,
    },
    {
        "flaw_id": "unclear_hierarchy",
        "title": "Нарушена визуальная иерархия",
        "description": "Второстепенное действие оформлено такой же яркой заливкой, как основное, и конкурирует с ним за внимание.",
        "region": {"x": 0.05, "y": 0.36, "w": 0.6, "h": 0.07},
        "html": """
        <div style="display:flex;gap:12px;"><span style="background:#2f5cff;color:#fff;padding:10px 16px;border-radius:10px;font-size:15px;">{action}</span></div>
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
        f'<div style="display:flex;justify-content:space-between;align-items:center;padding:12px 0;border-bottom:1px solid #e6e9f0;color:#1c2130;font-size:15px;">'
        f'<span>{line}</span><span style="color:#3a4256;font-weight:600;">{amount}</span></div>'
        for line, amount in [(variety["product"], f'{variety["price"]:,} ₽'), (variety["note"], "1 шт.")]
    )
    flaw_html = flaw["html"].replace("{product}", variety["product"]).replace("{action}", variety["action"])
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; font-family: -apple-system, Segoe UI, Roboto, sans-serif; }}
body {{ margin:0; background:#ffffff; }}
.screen {{ width:100%; min-height:100vh; background:#ffffff; padding:20px; }}
.bar {{ display:flex; align-items:center; justify-content:space-between; padding:4px 0 18px; }}
.bar h1 {{ font-size:20px; margin:0; color:#1c2130; }}
.card {{ background:#ffffff; border:1px solid #e6e9f0; border-radius:14px; padding:14px; margin-bottom:14px; }}
.label {{ color:#3a4256; font-size:15px; margin-bottom:6px; }}
.total {{ font-size:22px; font-weight:700; color:#1c2130; }}
</style></head><body>
<div class="screen">
  <div class="bar"><h1>{context["title"]}</h1><span style="color:#2f5cff;font-size:15px;font-weight:600;">Готово</span></div>
  <div class="card">{rows}</div>
  <div class="card">{flaw_html}</div>
  <div class="card"><div class="label">Итого · {variety["quantity"]} шт.</div><div class="total">{variety["price"]:,} ₽</div></div>
  <div style="background:#2f5cff;color:#ffffff;text-align:center;padding:16px;border-radius:12px;font-size:16px;font-weight:600;">{variety["action"]}</div>
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


MOCKUP_PROMPT = """Сгенерируй мобильный экран приложения «{app}» и верни строго JSON без markdown:
{{"html": "<полный HTML-документ>", "flaw_title": "кратко", "flaw_description": "суть", "region": {{"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}}}}
Экран: «{title}». Сценарий: {scenario}
Внеси ровно одну намеренную ошибку дизайна: {flaw}.
region — доля от ширины и высоты экрана (0..1), где находится проблемный элемент.
В HTML: ширина 390px, белый фон, только инлайн-стили, без скриптов."""


def _mockup_examples_block() -> str:
    examples = get_examples("design_mockup")
    if not examples:
        return ""
    lines = ["Примеры корректных макетов (ПРИМЕРЫ, не копируй дословно):"]
    for example in examples[:2]:
        lines.append(json.dumps(example, ensure_ascii=False))
    return "\n".join(lines)


def _parse_json_object(raw: str) -> dict | None:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


async def build_llm_mockup_html(seed: str) -> Mockup:
    deterministic = build_mockup_html(seed)
    client = get_llm_client()
    if isinstance(client, StubLLMClient):
        return deterministic
    template = get_prompt("design_mockup", MOCKUP_PROMPT)
    prompt = render(
        template,
        app="Мобильный клиент",
        title=pick_context(seed)["title"],
        scenario=deterministic.scenario,
        flaw=deterministic.flaw.description,
    )
    block = _mockup_examples_block()
    if block:
        prompt = prompt + "\n" + block
    try:
        raw = await client.complete(prompt)
    except Exception:
        return deterministic
    data = _parse_json_object(raw or "")
    if data is None:
        return deterministic
    html = _extract_html(str(data.get("html", "")))
    if not html or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        return deterministic
    region = normalize_annotation(data.get("region")) or {}
    return Mockup(
        html=html,
        scenario=deterministic.scenario,
        flaw=MockupFlaw(
            flaw_id=deterministic.flaw.flaw_id,
            title=str(data.get("flaw_title") or deterministic.flaw.title)[:200],
            description=str(data.get("flaw_description") or deterministic.flaw.description)[:600],
            region=region,
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
            return await page.screenshot(full_page=True, type="png", timeout=timeout_ms)
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


def annotate_png(png_bytes: bytes, annotation: dict | None) -> bytes:
    if not annotation:
        return png_bytes
    try:
        import io

        from PIL import Image, ImageDraw

        image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        width, height = image.size
        draw = ImageDraw.Draw(image, "RGBA")
        x0 = int(annotation["x"] * width)
        y0 = int(annotation["y"] * height)
        x1 = int((annotation["x"] + annotation["w"]) * width)
        y1 = int((annotation["y"] + annotation["h"]) * height)
        thickness = max(3, width // 120)
        for offset in range(thickness):
            draw.rectangle(
                [x0 - offset, y0 - offset, x1 + offset, y1 + offset],
                outline=(220, 40, 40, 255),
            )
        draw.rectangle([x0, y0, x1, y1], fill=(220, 40, 40, 48))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:
        return png_bytes


def annotated_data_url(image_data_url: str, annotation: dict | None) -> str:
    if not image_data_url or not image_data_url.startswith("data:image/"):
        return image_data_url
    try:
        header, _, payload = image_data_url.partition(",")
        png = base64.b64decode(payload)
    except Exception:
        return image_data_url
    return to_data_url(annotate_png(png, annotation))


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
Красным прямоугольником отмечена область, которую выбрал кандидат.
Какой именно дефект заложен: «{reference}».
Пояснение кандидата: «{note}».
Оцени по двум условиям: (1) красная область действительно указывает на заложенный дефект; (2) пояснение называет суть нарушения.
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
            marked = annotated_data_url(image_data_url, annotation)
            template = get_prompt("design_grading", VISION_GRADE_PROMPT)
            raw = await client.complete_with_image(
                render(template, reference=reference, note=note[:600]),
                marked,
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
