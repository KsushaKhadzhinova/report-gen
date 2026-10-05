from __future__ import annotations

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

from reportgen.domain import enterprise_standard as standard

BLANK_LINE = Pt(standard.LINE_SPACING_PT)
TABLE_FONT_PT = 12
KEEP_TOGETHER_MAX_ROWS = 12
TEXT_WIDTH_CM = 21.0 - standard.MARGIN_LEFT_MM / 10 - standard.MARGIN_RIGHT_MM / 10
CHAR_WIDTH_CM = 0.22
CELL_PADDING_CM = 0.4
BREAKABLE_WORD_CHARS = 22
MONTHS = "январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь"
CITY_DATE_RE = re.compile(rf"^(Минск),?\s+(?:{MONTHS})\s+(\d{{4}})\s*$", re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r"^Таблица\s+[\dА-Я]+(\.\d+)?\s*[–-]")
FIGURE_CAPTION_RE = re.compile(r"^Рисунок\s+[\dА-Я]+(\.\d+)?\s*[–-]")
LEADING_MARK_RE = re.compile(r"^\s*[–—\-•]\s*")
KEEP_UPPER = frozenset({"ЛР", "КП", "БГУИР", "ИС", "ИТ", "ООП", "СУБД", "СТП", "ЭБ", "URL", "API"})
HEADING_ENDS = ("Heading",)
SOURCES_TITLE = "список использованных источников"


def _paragraphs_and_tables(document):
    """Элементы тела документа по порядку: абзацы и таблицы."""
    for element in document.element.body.iterchildren():
        if element.tag == qn("w:p"):
            yield Paragraph(element, document)
        elif element.tag == qn("w:tbl"):
            yield Table(element, document)


def _has_picture(paragraph) -> bool:
    return bool(paragraph._p.xpath(".//w:drawing"))


def _is_heading(paragraph) -> bool:
    return paragraph.style.name.startswith(HEADING_ENDS) and bool(paragraph.text.strip())


def _set_text(paragraph, text: str) -> None:
    for run in paragraph.runs[1:]:
        run._r.getparent().remove(run._r)
    if paragraph.runs:
        paragraph.runs[0].text = text
    else:
        paragraph.add_run(text)


def fix_title_date(document) -> int:
    """На титульном листе «Минск 2026» без месяца."""
    fixed = 0
    for paragraph in document.paragraphs[:60]:
        match = CITY_DATE_RE.match(paragraph.text.strip())
        if match:
            _set_text(paragraph, f"{match.group(1)} {match.group(2)}")
            fixed += 1
    return fixed


def _sentence_case(text: str) -> str:
    def convert(token: str, first: bool) -> str:
        letters = re.sub(r"[^А-Яа-яЁёA-Za-z]", "", token)
        if not letters or any(ch.isdigit() for ch in token) or token.strip(".,;:()«»") in KEEP_UPPER or len(letters) == 1:
            return token
        lowered = token.lower()
        return lowered[:1].upper() + lowered[1:] if first else lowered

    tokens = re.split(r"(\s+)", text)
    result, first_word_done = [], False
    for token in tokens:
        if token.strip() and re.search(r"[А-Яа-яЁёA-Za-z]", token):
            result.append(convert(token, not first_word_done))
            first_word_done = True
        else:
            result.append(token)
    return "".join(result)


def fix_section_headings(document) -> int:
    """Заголовки разделов набраны обычным регистром, прописными их показывает стиль Heading 1."""
    document.styles["Heading 1"].font.all_caps = True
    fixed = 0
    for paragraph in document.paragraphs:
        if paragraph.style.name != "Heading 1" or not paragraph.text.strip():
            continue
        letters = re.sub(r"[^А-Яа-яЁёA-Za-z]", "", paragraph.text)
        if letters and letters.isupper():
            _set_text(paragraph, _sentence_case(paragraph.text))
            fixed += 1
    return fixed


def _space_before(paragraph, value) -> None:
    paragraph.paragraph_format.space_before = value


def fix_subsection_spacing(document) -> int:
    fixed = 0
    for paragraph in document.paragraphs:
        if paragraph.style.name in ("Heading 2", "Heading 3") and paragraph.text.strip():
            _space_before(paragraph, BLANK_LINE)
            fixed += 1
    return fixed


def _fix_figure(paragraph, caption: Paragraph | None) -> None:
    fmt = paragraph.paragraph_format
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.first_line_indent = Cm(0)
    fmt.space_before = BLANK_LINE
    fmt.space_after = Pt(0)
    fmt.keep_with_next = True
    if caption is not None:
        caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption.paragraph_format.first_line_indent = Cm(0)
        caption.paragraph_format.space_before = Pt(0)
        caption.paragraph_format.space_after = BLANK_LINE


def _fix_table_cell_paragraphs(table: Table) -> None:
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                fmt = paragraph.paragraph_format
                fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
                fmt.first_line_indent = Cm(0)
                fmt.space_before = Pt(0)
                fmt.space_after = Pt(0)
                if paragraph.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                for run in paragraph.runs:
                    run.font.name = standard.FONT
                    run.font.size = Pt(TABLE_FONT_PT)


def _has_merged_cells(table: Table) -> bool:
    return bool(table._tbl.xpath(".//w:gridSpan | .//w:vMerge"))


def _column_texts(table: Table) -> list[list[str]]:
    columns: list[list[str]] = [[] for _ in table.columns]
    for row in table.rows:
        for index, cell in enumerate(row.cells):
            columns[index].append(cell.text)
    return columns


def column_widths_cm(columns: list[list[str]], total: float = TEXT_WIDTH_CM) -> list[float]:
    """Ширины столбцов: минимум по самому длинному слову, остаток пропорционально объёму текста; очень длинные слова допускается переносить."""
    minimum, preferred = [], []
    for cells in columns:
        longest = max((len(word) for text in cells for word in text.split()), default=1)
        widest = max((len(text) for text in cells), default=1)
        low = min(longest, BREAKABLE_WORD_CHARS) * CHAR_WIDTH_CM + CELL_PADDING_CM
        minimum.append(low)
        preferred.append(max(low, widest * CHAR_WIDTH_CM + CELL_PADDING_CM))
    if sum(preferred) <= total:
        spare = total - sum(preferred)
        return [width + spare * width / sum(preferred) for width in preferred]
    if sum(minimum) >= total:
        return [width * total / sum(minimum) for width in minimum]
    room = total - sum(minimum)
    extra = [high - low for high, low in zip(preferred, minimum, strict=True)]
    return [low + room * share / sum(extra) for low, share in zip(minimum, extra, strict=True)]


def _make_columns_fit_content(table: Table) -> None:
    if _has_merged_cells(table):
        table.autofit = True
        return
    widths = column_widths_cm(_column_texts(table))
    table.autofit = False
    properties = table._tbl.tblPr
    total = properties.find(qn("w:tblW"))
    if total is None:
        total = OxmlElement("w:tblW")
        properties.append(total)
    total.set(qn("w:type"), "dxa")
    total.set(qn("w:w"), str(int(sum(widths) * 567)))
    for column, width in zip(table.columns, widths, strict=True):
        column.width = Cm(width)
        for cell in column.cells:
            cell.width = Cm(width)


def _mark_header_and_keep_rows(table: Table) -> None:
    rows = table.rows
    for index, row in enumerate(rows):
        properties = row._tr.get_or_add_trPr()
        if properties.find(qn("w:cantSplit")) is None:
            properties.append(OxmlElement("w:cantSplit"))
        if index == 0 and properties.find(qn("w:tblHeader")) is None:
            properties.append(OxmlElement("w:tblHeader"))
    if len(rows) <= KEEP_TOGETHER_MAX_ROWS:
        for row in rows[:-1]:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.keep_with_next = True


def fix_objects(document) -> int:
    """Пустые строки и интервалы вокруг рисунков и таблиц, вид таблиц."""
    fixed = 0
    items = list(_paragraphs_and_tables(document))
    for index, item in enumerate(items):
        following = items[index + 1] if index + 1 < len(items) else None
        if isinstance(item, Table):
            _fix_table_cell_paragraphs(item)
            _make_columns_fit_content(item)
            _mark_header_and_keep_rows(item)
            if isinstance(following, Paragraph) and following.text.strip() and not TABLE_CAPTION_RE.match(following.text.strip()):
                _space_before(following, BLANK_LINE)
            fixed += 1
        elif TABLE_CAPTION_RE.match(item.text.strip()):
            fmt = item.paragraph_format
            fmt.space_before = BLANK_LINE
            fmt.space_after = Pt(0)
            fmt.keep_with_next = True
            fixed += 1
        elif _has_picture(item) and len(item.text.strip()) < 3:
            caption = following if isinstance(following, Paragraph) and FIGURE_CAPTION_RE.match(following.text.strip()) else None
            _fix_figure(item, caption)
            fixed += 1
    return fixed


def _find_sources_heading(paragraphs: list[Paragraph]) -> int | None:
    return next((i for i, p in enumerate(paragraphs) if _is_heading(p) and p.text.strip().lower() == SOURCES_TITLE), None)


def fix_sources_list(document) -> int:
    """Источники: без вводной фразы, тире и курсива, с номерами по порядку."""
    paragraphs = list(document.paragraphs)
    start = _find_sources_heading(paragraphs)
    if start is None:
        return 0
    entries = []
    for paragraph in paragraphs[start + 1 :]:
        if _is_heading(paragraph):
            break
        if paragraph.text.strip():
            entries.append(paragraph)
    if entries and entries[0].text.strip().endswith(":"):
        entries[0]._p.getparent().remove(entries[0]._p)
        entries = entries[1:]
    for number, paragraph in enumerate(entries, 1):
        _set_text(paragraph, f"{number} {LEADING_MARK_RE.sub('', paragraph.text).strip()}")
        for run in paragraph.runs:
            run.italic = False
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.first_line_indent = Cm(standard.PARAGRAPH_INDENT_CM)
    return len(entries)


def fix_all_objects(document) -> int:
    return (
        fix_title_date(document)
        + fix_section_headings(document)
        + fix_subsection_spacing(document)
        + fix_objects(document)
        + fix_sources_list(document)
    )
