import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "docs" / "assets" / "fonts"
OUTPUT = ROOT / "docs" / "syntax-documentation.pdf"

PRIMARY = colors.HexColor("#1f00cc")
ACCENT = colors.HexColor("#382bf0")
INK = colors.HexColor("#191b22")
MUTED = colors.HexColor("#464556")
LINE = colors.HexColor("#c7c4da")
SURFACE = colors.HexColor("#f3f3fc")

FONT_FILES = {
    "Text": "DejaVuSans.ttf",
    "TextBold": "DejaVuSans-Bold.ttf",
    "Mono": "DejaVuSansMono.ttf",
    "MonoBold": "DejaVuSansMono-Bold.ttf",
}
FALLBACK_FONTS = {"Text": "Helvetica", "TextBold": "Helvetica-Bold", "Mono": "Courier", "MonoBold": "Courier-Bold"}


def register_document_fonts() -> None:
    for name, filename in FONT_FILES.items():
        path = FONTS / filename
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        else:
            pdfmetrics.registerFont(pdfmetrics.getFont(FALLBACK_FONTS[name]))


register_document_fonts()

body = ParagraphStyle("body", fontName="Text", fontSize=9.5, leading=14, textColor=INK, spaceAfter=6)
listitem = ParagraphStyle("listitem", parent=body, leftIndent=14, bulletIndent=4, spaceAfter=3)
code_inline_font = 'Mono'
h1 = ParagraphStyle("h1", fontName="TextBold", fontSize=19, leading=24, textColor=PRIMARY, spaceBefore=10, spaceAfter=10)
h2 = ParagraphStyle("h2", fontName="TextBold", fontSize=13.5, leading=18, textColor=INK, spaceBefore=14, spaceAfter=6)
h3 = ParagraphStyle("h3", fontName="TextBold", fontSize=11, leading=15, textColor=MUTED, spaceBefore=10, spaceAfter=4)
code_style = ParagraphStyle("code", fontName="Mono", fontSize=7.5, leading=10, textColor=INK)
cell = ParagraphStyle("cell", fontName="Text", fontSize=8.5, leading=11, textColor=INK)
cell_head = ParagraphStyle("cell_head", fontName="TextBold", fontSize=8.5, leading=11, textColor=colors.white)
toc_title = ParagraphStyle("toc_title", fontName="TextBold", fontSize=19, leading=24, textColor=PRIMARY, spaceAfter=14)

DOC_FILES = [
    ("01-architecture.md", "1. Функциональная и компонентная архитектура"),
    ("02-testing-mechanics.md", "2. Механика тестирования и устойчивость к утечке заданий"),
    ("03-matching-mechanics.md", "3. Механика подбора и категоризация кандидатов"),
    ("04-validation.md", "4. Процедура валидации и результаты"),
    ("05-pvn-integration.md", "5. Схема интеграции с реестром ПВН"),
    ("06-antifraud-ats.md", "6. Антифрод и интеграция с ATS"),
    ("07-deploy.md", "7. Сборка, развёртывание и локальный запуск"),
    ("08-libraries.md", "8. Библиотеки и компоненты"),
    ("api.md", "Приложение A. Описание API"),
    ("validation-results.md", "Приложение B. Отчёт валидации"),
]


def escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def inline(text: str) -> str:
    result = escape(text)
    result = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", result)
    result = re.sub(r"`([^`]+)`", lambda match: f'<font face="{code_inline_font}" size="8.5">{match[1]}</font>', result)
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" color="#1f00cc">\1</a>', result)
    return result


def wrap_code_lines(lines: list[str], limit: int = 96) -> list[str]:
    wrapped = []
    for line in lines:
        while len(line) > limit:
            wrapped.append(line[:limit])
            line = "    " + line[limit:]
        wrapped.append(line)
    return wrapped


def build_code_block(lines: list[str]):
    wrapped = wrap_code_lines(lines)
    pre = Preformatted("\n".join(wrapped), code_style)
    table = Table([[pre]], colWidths=[166 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SURFACE),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return [table, Spacer(1, 6)]


def split_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [part.strip() for part in stripped.split("|")]


def build_table(rows: list[list[str]]):
    data = []
    for index, row in enumerate(rows):
        style = cell_head if index == 0 else cell
        data.append([Paragraph(inline(part), style) for part in row])
    widths = [166 * mm / len(rows[0])] * len(rows[0])
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
            ]
        )
    )
    return [Spacer(1, 4), table, Spacer(1, 8)]


def parse_markdown(text: str, chapter: str):
    flow = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            index += 1
            continue
        if line.strip() == "---":
            index += 1
            continue
        if line.startswith("```"):
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index].rstrip())
                index += 1
            index += 1
            flow.extend(build_code_block(code_lines))
            continue
        if line.startswith("|"):
            table_rows = []
            while index < len(lines) and lines[index].startswith("|"):
                row = split_row(lines[index])
                if all(re.fullmatch(r":?-{2,}:?", part) for part in row if part != ""):
                    index += 1
                    continue
                table_rows.append(row)
                index += 1
            if table_rows:
                flow.extend(build_table(table_rows))
            continue
        if line.startswith("# "):
            index += 1
            continue
        if line.startswith("## "):
            title = line[3:].strip()
            flow.append(Paragraph(inline(title), h1))
            index += 1
            continue
        if line.startswith("### "):
            flow.append(Paragraph(inline(line[4:].strip()), h2))
            index += 1
            continue
        if line.startswith("#### "):
            flow.append(Paragraph(inline(line[5:].strip()), h3))
            index += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            item = re.sub(r"^\s*[-*]\s+", "", line).strip()
            flow.append(Paragraph(inline(item), listitem, bulletText="–"))
            index += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            number = re.match(r"^\s*(\d+)\.\s+", line).group(1)
            item = re.sub(r"^\s*\d+\.\s+", "", line).strip()
            flow.append(Paragraph(inline(item), listitem, bulletText=f"{number}."))
            index += 1
            continue
        paragraph_lines = [line.strip()]
        index += 1
        while index < len(lines):
            following = lines[index]
            if (
                following.strip() == ""
                or following.startswith("#")
                or following.startswith("|")
                or following.startswith("```")
                or following.strip() == "---"
                or re.match(r"^\s*[-*]\s+", following)
                or re.match(r"^\s*\d+\.\s+", following)
            ):
                break
            paragraph_lines.append(following.strip())
            index += 1
        flow.append(Paragraph(inline(" ".join(paragraph_lines)), body))
    return flow


class DocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style
            text = flowable.getPlainText()
            if style is h1:
                self.notify("TOCEntry", (0, text, self.page))
            elif style is h2 and text and not text.startswith(("Приложение",)):
                self.notify("TOCEntry", (1, text, self.page))


def title_page():
    elements = []
    elements.append(Spacer(1, 60 * mm))
    elements.append(Paragraph("syntax", ParagraphStyle("logo", fontName="MonoBold", fontSize=40, leading=48, textColor=PRIMARY, alignment=1)))
    elements.append(Paragraph("Платформа обратного найма ИТ-специалистов", ParagraphStyle("sub", fontName="TextBold", fontSize=16, leading=22, textColor=INK, alignment=1)))
    elements.append(Paragraph("Спецтрек Федерации спортивного программирования", ParagraphStyle("sub2", fontName="Text", fontSize=12, leading=18, textColor=MUTED, alignment=1)))
    elements.append(Spacer(1, 30 * mm))
    elements.append(Paragraph("Сопроводительная документация", ParagraphStyle("doc", fontName="TextBold", fontSize=22, leading=28, textColor=INK, alignment=1)))
    elements.append(Paragraph("Функциональная и компонентная архитектура · механики тестирования и подбора · валидация · интеграция с ПВН · API · библиотеки · развёртывание", ParagraphStyle("desc", fontName="Text", fontSize=10.5, leading=16, textColor=MUTED, alignment=1, leftIndent=20 * mm, rightIndent=20 * mm)))
    elements.append(Spacer(1, 20 * mm))
    elements.append(Paragraph(f"Версия 1.0 · {date.today().strftime('%d.%m.%Y')}", ParagraphStyle("date", fontName="Mono", fontSize=10, leading=14, textColor=MUTED, alignment=1)))
    elements.append(Paragraph("Репозиторий: https://github.com/KoTeHok22/Syntax", ParagraphStyle("repo", fontName="Mono", fontSize=9, leading=13, textColor=MUTED, alignment=1)))
    elements.append(PageBreak())
    return elements


def main():
    doc = DocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="syntax — сопроводительная документация",
        author="Команда Syntax",
    )

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("toc1", fontName="TextBold", fontSize=11, leading=16, textColor=INK, leftIndent=6, firstLineIndent=-6, spaceBefore=6),
        ParagraphStyle("toc2", fontName="Text", fontSize=9.5, leading=13, textColor=MUTED, leftIndent=18, firstLineIndent=-6),
    ]

    elements = title_page()
    elements.append(Paragraph("Содержание", toc_title))
    elements.append(toc)
    elements.append(PageBreak())

    for filename, chapter in DOC_FILES:
        path = ROOT / "docs" / filename
        if not path.exists():
            continue
        elements.append(Paragraph(chapter, h1))
        elements.append(Spacer(1, 4))
        elements.extend(parse_markdown(path.read_text(encoding="utf-8"), chapter))
        elements.append(PageBreak())

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Mono", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(22 * mm, 12 * mm, "syntax · сопроводительная документация")
        canvas.drawRightString(A4[0] - 22 * mm, 12 * mm, f"{document.page}")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(22 * mm, 16 * mm, A4[0] - 22 * mm, 16 * mm)
        canvas.restoreState()

    doc.multiBuild(elements, onFirstPage=footer, onLaterPages=footer)
    print(f"built {OUTPUT}")


if __name__ == "__main__":
    main()
