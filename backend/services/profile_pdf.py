import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.core.labels import format_date, format_years, grade_label, specialization_label, verdict_label

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONT_PATH = FONT_DIR / "AdwaitaSans-Regular.ttf"
DEFAULT_FALLBACK_FONT = "Helvetica"

INK = colors.HexColor("#191b22")
MUTED = colors.HexColor("#5a5870")
PRIMARY = colors.HexColor("#1f00cc")
LINE = colors.HexColor("#d9d6ea")
SURFACE = colors.HexColor("#f4f3fc")
GOOD = colors.HexColor("#0f7a4a")
GOOD_SURFACE = colors.HexColor("#e7f4ed")

REGULAR_FONT = "ProfileFont"
BOLD_FONT = "ProfileFontBold"

TITLE_STYLE = ParagraphStyle(
    name="title",
    fontName=BOLD_FONT,
    fontSize=19,
    leading=23,
    textColor=INK,
)
SUBTITLE_STYLE = ParagraphStyle(
    name="subtitle",
    fontName=REGULAR_FONT,
    fontSize=10.5,
    leading=15,
    textColor=MUTED,
)
SECTION_STYLE = ParagraphStyle(
    name="section",
    fontName=BOLD_FONT,
    fontSize=11.5,
    leading=15,
    textColor=PRIMARY,
    spaceBefore=2 * mm,
    spaceAfter=1.5 * mm,
)
LABEL_STYLE = ParagraphStyle(
    name="label",
    fontName=REGULAR_FONT,
    fontSize=8.5,
    leading=12,
    textColor=MUTED,
)
VALUE_STYLE = ParagraphStyle(
    name="value",
    fontName=REGULAR_FONT,
    fontSize=10.5,
    leading=14,
    textColor=INK,
    alignment=TA_LEFT,
)
BODY_STYLE = ParagraphStyle(
    name="body",
    fontName=REGULAR_FONT,
    fontSize=10,
    leading=14,
    textColor=INK,
)
NOTE_STYLE = ParagraphStyle(
    name="note",
    fontName=REGULAR_FONT,
    fontSize=9,
    leading=13,
    textColor=MUTED,
)
SCORE_VALUE_STYLE = ParagraphStyle(
    name="score_value",
    fontName=BOLD_FONT,
    fontSize=26,
    leading=28,
    textColor=PRIMARY,
)
SCORE_LABEL_STYLE = ParagraphStyle(
    name="score_label",
    fontName=BOLD_FONT,
    fontSize=9,
    leading=12,
    textColor=INK,
)
TABLE_HEADER_STYLE = ParagraphStyle(
    name="th",
    fontName=BOLD_FONT,
    fontSize=9,
    leading=12,
    textColor=colors.white,
)
TABLE_CELL_STYLE = ParagraphStyle(
    name="td",
    fontName=REGULAR_FONT,
    fontSize=9,
    leading=12.5,
    textColor=INK,
)


def _register_font(name: str, path: Path, fallback: str) -> str:
    if path.exists():
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        return name
    return fallback


def register_font() -> None:
    _register_font(REGULAR_FONT, FONT_PATH, DEFAULT_FALLBACK_FONT)
    _register_font(BOLD_FONT, FONT_PATH, DEFAULT_FALLBACK_FONT)


def _escape(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _joined(values, empty: str) -> str:
    if not values:
        return empty
    return ", ".join(_escape(item) for item in values)


def _section(title: str):
    return [
        Spacer(1, 3 * mm),
        Paragraph(_escape(title), SECTION_STYLE),
        HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=0, spaceAfter=2.5 * mm),
    ]


def _facts_table(rows: list[tuple[str, str]]) -> Table:
    data = [
        [Paragraph(f"{_escape(label)}: {value}", VALUE_STYLE)]
        for label, value in rows
    ]
    table = Table(data, colWidths=[None])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
            ]
        )
    )
    return table


def _sessions_table(sessions) -> Table:
    header = ["Дата", "Грейд", "Результат", "Балл", "Вердикт"]
    data = [[Paragraph(head, TABLE_HEADER_STYLE) for head in header]]
    for session in sessions:
        verdict = verdict_label(session.verdict)
        grade = grade_label(session.grade) or "Грейд"
        data.append(
            [
                Paragraph(_escape(format_date(session.completed_at)), TABLE_CELL_STYLE),
                Paragraph(_escape(grade), TABLE_CELL_STYLE),
                Paragraph(f"{session.correct_count} из {session.task_count}", TABLE_CELL_STYLE),
                Paragraph(_escape(session.result_score if session.result_score is not None else "—"), TABLE_CELL_STYLE),
                Paragraph(_escape(verdict), TABLE_CELL_STYLE),
            ]
        )
    table = Table(data, colWidths=[26 * mm, 24 * mm, 32 * mm, 20 * mm, None], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.6 * mm),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ]
        )
    )
    return table


def _achievements_table(achievements) -> Table:
    header = ["Тип", "Уровень", "Балл", "Дата"]
    data = [[Paragraph(head, TABLE_HEADER_STYLE) for head in header]]
    for achievement in achievements:
        data.append(
            [
                Paragraph(_escape(achievement.achievement_type), TABLE_CELL_STYLE),
                Paragraph(_escape(achievement.level or "—"), TABLE_CELL_STYLE),
                Paragraph(_escape(f"{achievement.score:g}"), TABLE_CELL_STYLE),
                Paragraph(_escape(format_date(achievement.achieved_at)), TABLE_CELL_STYLE),
            ]
        )
    table = Table(data, colWidths=[None, 34 * mm, 22 * mm, 28 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.6 * mm),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ]
        )
    )
    return table


def _header_block(profile, score) -> Table:
    name = _escape(profile.full_name) if profile.full_name else "Имя не указано"
    specialization = specialization_label(profile.specialization) or "Специализация не указана"
    grade = grade_label(profile.grade) or "Грейд не подтверждён"
    contacts = "Контакты передаются через сервис после взаимного согласия"

    left = [
        Paragraph(name, TITLE_STYLE),
        Paragraph(f"{_escape(specialization)} · {_escape(grade)}", SUBTITLE_STYLE),
        Spacer(1, 1.5 * mm),
        Paragraph(contacts, NOTE_STYLE),
    ]

    if score is None:
        right = [Paragraph("ПВН ID", LABEL_STYLE), Paragraph(f"#{profile.id}", SCORE_LABEL_STYLE)]
    else:
        right = [
            Paragraph("Балл ПВН", LABEL_STYLE),
            Paragraph(f"{round(float(score))}", SCORE_VALUE_STYLE),
        ]

    table = Table([[left, right]], colWidths=[None, 34 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "TOP"),
                ("VALIGN", (1, 0), (1, 0), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BACKGROUND", (1, 0), (1, 0), SURFACE),
                ("BOX", (1, 0), (1, 0), 0.6, LINE),
                ("TOPPADDING", (1, 0), (1, 0), 3 * mm),
                ("BOTTOMPADDING", (1, 0), (1, 0), 3 * mm),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 4 * mm),
            ]
        )
    )
    return table


def _best_result(sessions):
    scored = [session for session in sessions if session.result_score is not None]
    if not scored:
        return None
    return max(scored, key=lambda session: session.result_score)


def _summary_block(profile, sessions, achievements) -> Table:
    best = _best_result(sessions)
    completed = [session for session in sessions if getattr(session, "status", "completed") == "completed"]
    cells = [
        ("Тестов пройдено", str(len(completed or sessions))),
        ("Лучший результат", str(best.result_score) if best else "—"),
        ("Достижений ПВН", str(len(achievements))),
        ("Опыт", format_years(profile.years_of_experience) if profile.years_of_experience else "—"),
    ]
    data = [
        [Paragraph(_escape(label), LABEL_STYLE) for label, _ in cells],
        [Paragraph(value, SCORE_LABEL_STYLE) for _, value in cells],
    ]
    table = Table(data, colWidths=[None, None, None, None])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.white),
                ("TOPPADDING", (0, 0), (-1, 0), 2.4 * mm),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 2.4 * mm),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return table


def _empty_note(text: str) -> Paragraph:
    return Paragraph(_escape(text), BODY_STYLE)


def build_profile_pdf(profile, sessions, achievements, score=None) -> bytes:
    register_font()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        title=f"Профиль ПВН №{profile.id}",
        author=profile.full_name or "Кандидат",
        subject="Стандартизированный профиль кандидата",
    )

    sessions = list(sessions or [])
    achievements = list(achievements or [])

    story = []
    story.append(_header_block(profile, score))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Сводка", SECTION_STYLE))
    story.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=2.5 * mm))
    story.append(_summary_block(profile, sessions, achievements))

    story.extend(_section("Профиль"))
    story.append(
        _facts_table(
            [
                ("Имя", _escape(profile.full_name) if profile.full_name else "не указано"),
                ("Специализация", _escape(specialization_label(profile.specialization) or "не указана")),
                ("Грейд", _escape(grade_label(profile.grade) or "не подтверждён")),
                ("Опыт работы", _escape(format_years(profile.years_of_experience)) if profile.years_of_experience else "не указан"),
                ("Стек", _joined(profile.stack, "не указан")),
                ("Софт-скиллы", _joined(profile.soft_skills, "не указаны")),
            ]
        )
    )

    story.extend(_section("История тестирования"))
    if sessions:
        story.append(_sessions_table(sessions))
    else:
        story.append(_empty_note("Тестирование не пройдено."))

    story.extend(_section("Достижения ПВН"))
    if achievements:
        story.append(_achievements_table(achievements))
    else:
        story.append(_empty_note("История ПВН отсутствует."))

    story.append(Spacer(1, 5 * mm))
    story.append(
        KeepTogether(
            [
                HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=2.5 * mm),
                Paragraph(
                    "Профиль сформирован автоматически. Контакты предоставляются только после взаимного согласия в сервисе.",
                    NOTE_STYLE,
                ),
            ]
        )
    )

    document.build(story)
    return buffer.getvalue()
