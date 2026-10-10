import io
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from backend.core.labels import format_date, format_years, grade_label, specialization_label, verdict_label

FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "AdwaitaSans-Regular.ttf"

TITLE_STYLE = ParagraphStyle(
    name="title",
    fontName="ProfileFont",
    fontSize=16,
    spaceAfter=6 * mm,
)
SECTION_STYLE = ParagraphStyle(
    name="section",
    fontName="ProfileFont",
    fontSize=12,
    spaceBefore=4 * mm,
    spaceAfter=2 * mm,
)
BODY_STYLE = ParagraphStyle(
    name="body", fontName="ProfileFont", fontSize=10, leading=14)


def register_font() -> None:
    pdfmetrics.registerFont(TTFont("ProfileFont", str(FONT_PATH)))


def build_profile_pdf(profile, sessions, achievements) -> bytes:
    register_font()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        title=f"Профиль №{profile.id}",
    )
    story = [
        Paragraph("Стандартизированный профиль кандидата", TITLE_STYLE),
        Paragraph(f"Имя: {profile.full_name or 'не указано'}", BODY_STYLE),
        Paragraph(f"Специализация: {specialization_label(profile.specialization) or 'не указана'}", BODY_STYLE),
        Paragraph(f"Грейд: {grade_label(profile.grade) or 'не подтверждён'}", BODY_STYLE),
        Paragraph(f"Стек: {', '.join(profile.stack) if profile.stack else 'не указан'}", BODY_STYLE),
        Paragraph(f"Опыт: {format_years(profile.years_of_experience)}", BODY_STYLE),
        Paragraph(f"Софт-скиллы: {', '.join(profile.soft_skills) if profile.soft_skills else 'не указаны'}", BODY_STYLE),
        Paragraph("История тестирования", SECTION_STYLE),
    ]
    if sessions:
        for session in sessions:
            story.append(
                Paragraph(
                    f"{grade_label(session.grade) or 'Грейд'}: {session.correct_count}/{session.task_count} верно, "
                    f"балл {session.result_score}, {verdict_label(session.verdict)}, "
                    f"дата {format_date(session.completed_at)}",
                    BODY_STYLE,
                )
            )
    else:
        story.append(Paragraph("Тестирование не пройдено", BODY_STYLE))
    story.append(Paragraph("Достижения ПВН", SECTION_STYLE))
    if achievements:
        for achievement in achievements:
            story.append(
                Paragraph(
                    f"{achievement.achievement_type} — {achievement.level}, "
                    f"{format_date(achievement.achieved_at)}",
                    BODY_STYLE,
                )
            )
    else:
        story.append(Paragraph("Без истории ПВН", BODY_STYLE))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Контакты предоставляются только после взаимного согласия в сервисе", BODY_STYLE))
    document.build(story)
    return buffer.getvalue()
