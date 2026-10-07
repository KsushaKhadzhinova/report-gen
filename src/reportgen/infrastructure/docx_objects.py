from __future__ import annotations

import copy
import re
from dataclasses import replace

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.table import Table
from docx.text.paragraph import Paragraph

from reportgen.domain import enterprise_standard as standard
from reportgen.domain.citations import CITATION_RE, parse_numbers, renumber
from reportgen.domain.fix_options import FixOptions
from reportgen.domain.object_sentences import figure_sentence, table_sentence
from reportgen.domain.sources import vak_entries

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
FILLER_PHRASES = ("В данном подразделе рассматриваются ключевые аспекты",)
HEADING_ENDS = ("Heading",)
SOURCES_TITLE = "список использованных источников"
APPENDIX_RE = re.compile(r"^ПРИЛОЖЕНИЕ\s+[А-ЯA-Z]\.?$", re.IGNORECASE)
APPENDIX_STATUS_RE = re.compile(r"^\((обязательное|справочное|рекомендуемое)\)$", re.IGNORECASE)
APPENDIX_TITLE_MAX_CHARS = 160


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


def fix_section_headings(document) -> int:
    """Заголовки разделов набираются прописными буквами и в тексте, и в содержании."""
    fixed = 0
    for paragraph in document.paragraphs:
        if paragraph.style.name != "Heading 1" or not paragraph.text.strip():
            continue
        if paragraph.text != paragraph.text.upper():
            _set_text(paragraph, paragraph.text.upper())
            fixed += 1
    return fixed


def remove_filler_paragraphs(document) -> int:
    """Убирает шаблонные фразы-заглушки, не несущие смысла."""
    removed = 0
    for paragraph in list(document.paragraphs):
        if paragraph.text.strip().startswith(FILLER_PHRASES):
            paragraph._p.getparent().remove(paragraph._p)
            removed += 1
    return removed


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


def _is_blank(item) -> bool:
    return isinstance(item, Paragraph) and not item.text.strip() and not _has_picture(item)


def _is_caption(item) -> bool:
    return isinstance(item, Paragraph) and bool(TABLE_CAPTION_RE.match(item.text.strip()) or FIGURE_CAPTION_RE.match(item.text.strip()))


def _lacks_text_after(items: list, index: int) -> bool:
    """После таблицы или рисунка должен идти текст, а не заголовок, подпись другого объекта, таблица или конец документа."""
    for item in items[index + 1 :]:
        if _is_blank(item):
            continue
        return isinstance(item, Table) or _is_heading(item) or _is_caption(item) or _has_picture(item)
    return True


def _object_caption(items: list, index: int) -> str | None:
    item = items[index]
    if isinstance(item, Paragraph):
        return item.text
    for earlier in reversed(items[:index]):
        if _is_blank(earlier):
            continue
        return earlier.text if isinstance(earlier, Paragraph) and TABLE_CAPTION_RE.match(earlier.text.strip()) else None
    return None


def _objects_needing_text(items: list) -> list[tuple[int, str]]:
    found = []
    for index, item in enumerate(items):
        is_table = isinstance(item, Table)
        is_figure_caption = isinstance(item, Paragraph) and bool(FIGURE_CAPTION_RE.match(item.text.strip()))
        if not (is_table or is_figure_caption) or not _lacks_text_after(items, index):
            continue
        caption = _object_caption(items, index)
        sentence = (table_sentence if is_table else figure_sentence)(caption or "")
        if sentence:
            found.append((index, sentence))
    return found


def count_objects_without_text(document) -> int:
    return len(_objects_needing_text(list(_paragraphs_and_tables(document))))


def _reference_paragraph(items: list, index: int) -> Paragraph | None:
    for earlier in reversed(items[:index]):
        if isinstance(earlier, Paragraph) and len(earlier.text) > 60 and not _is_heading(earlier) and not _is_caption(earlier):
            if earlier.alignment != WD_ALIGN_PARAGRAPH.CENTER:
                return earlier
    return None


def _sentence_paragraph(reference: Paragraph, text: str) -> Paragraph:
    clone = copy.deepcopy(reference._p)
    for child in list(clone):
        if child.tag != qn("w:pPr"):
            clone.remove(child)
    paragraph = Paragraph(clone, reference._parent)
    run = paragraph.add_run(text)
    template = reference.runs[0]._r.find(qn("w:rPr")) if reference.runs else None
    if template is not None:
        run._r.insert(0, copy.deepcopy(template))
    paragraph.paragraph_format.space_before = BLANK_LINE
    return paragraph


def fix_text_after_objects(document) -> int:
    """Добавляет предложение-ссылку на таблицу или рисунок там, где сразу после них стоит заголовок, подпись или конец документа."""
    items = list(_paragraphs_and_tables(document))
    added = 0
    for index, sentence in reversed(_objects_needing_text(items)):
        reference = _reference_paragraph(items, index)
        if reference is None:
            continue
        element = items[index]._tbl if isinstance(items[index], Table) else items[index]._p
        element.addnext(_sentence_paragraph(reference, sentence)._p)
        added += 1
    return added


def _center(paragraph, bold_title: bool = False) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.left_indent = Cm(0)
    paragraph.paragraph_format.keep_with_next = True
    if bold_title:
        for run in paragraph.runs:
            run.bold = True


def fix_appendix_headings(document) -> int:
    """Приложение: «ПРИЛОЖЕНИЕ А», ниже по центру статус в скобках, ещё ниже заголовок приложения по центру полужирным."""
    paragraphs = [p for p in document.paragraphs if p.text.strip()]
    fixed = 0
    for index, paragraph in enumerate(paragraphs):
        if not APPENDIX_RE.match(paragraph.text.strip()):
            continue
        _center(paragraph)
        fixed += 1
        following = paragraphs[index + 1 : index + 3]
        if following and APPENDIX_STATUS_RE.match(following[0].text.strip()):
            _center(following[0])
            following = following[1:]
        if following and len(following[0].text) <= APPENDIX_TITLE_MAX_CHARS and not _is_caption(following[0]):
            _center(following[0], bold_title=True)
    return fixed


def _find_sources_heading(paragraphs: list[Paragraph]) -> int | None:
    return next((i for i, p in enumerate(paragraphs) if _is_heading(p) and p.text.strip().lower() == SOURCES_TITLE), None)


def _entry_paragraphs(paragraphs: list[Paragraph], heading_index: int) -> list[Paragraph]:
    entries = []
    for paragraph in paragraphs[heading_index + 1 :]:
        if _is_heading(paragraph):
            break
        if paragraph.text.strip():
            entries.append(paragraph)
    if entries and entries[0].text.strip().endswith(":"):
        entries[0]._p.getparent().remove(entries[0]._p)
        entries = entries[1:]
    return entries


def _insert_copy_after(paragraph: Paragraph) -> Paragraph:
    clone = copy.deepcopy(paragraph._p)
    paragraph._p.addnext(clone)
    return Paragraph(clone, paragraph._parent)


def _style_entry(paragraph: Paragraph) -> None:
    for run in paragraph.runs:
        run.italic = False
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    paragraph.paragraph_format.first_line_indent = Cm(standard.PARAGRAPH_INDENT_CM)


def _rebuild_entries(entries: list[Paragraph], options: FixOptions) -> dict[int, tuple[int, ...]]:
    """Приводит записи к виду ВАК, нумерует по порядку и возвращает соответствие старых номеров в тексте новым."""
    unwanted = [re.compile(pattern, re.IGNORECASE) for pattern in options.drop_sources]
    mapping: dict[int, tuple[int, ...]] = {number: () for number in options.drop_citations}
    next_number = 1
    for position, paragraph in enumerate(entries, 1):
        text_number = position + options.citation_offset
        if any(pattern.search(paragraph.text) for pattern in unwanted):
            paragraph._p.getparent().remove(paragraph._p)
            mapping[text_number] = ()
            continue
        produced = vak_entries(LEADING_MARK_RE.sub("", paragraph.text).strip())
        current = paragraph
        for index, text in enumerate(produced):
            if index:
                current = _insert_copy_after(current)
            _set_text(current, f"{next_number + index} {text}")
            _style_entry(current)
        mapping[text_number] = tuple(range(next_number, next_number + len(produced)))
        next_number += len(produced)
    return mapping


def _all_paragraphs(document) -> list[Paragraph]:
    return [Paragraph(element, document) for element in document.element.body.iter(qn("w:p"))]


def _trim_space_before_punctuation(paragraph: Paragraph) -> None:
    runs = [run for run in paragraph.runs if run.text]
    for current, following in zip(runs, runs[1:], strict=False):
        if current.text.endswith(" ") and following.text[:1] in ",.;:)":
            current.text = current.text.rstrip(" ")


def renumber_citations(paragraphs: list[Paragraph], mapping: dict[int, tuple[int, ...]]) -> int:
    """Перенумеровывает ссылки на источники в переданных абзацах, сохраняя оформление фрагментов."""
    changed = 0
    for paragraph in paragraphs:
        if "[" not in paragraph.text:
            continue
        before = paragraph.text
        for run in paragraph.runs:
            if "[" in run.text:
                run.text = renumber(run.text, mapping)
        if paragraph.text == before and renumber(before, mapping) != before:
            _set_text(paragraph, renumber(before, mapping))
        if paragraph.text != before:
            _trim_space_before_punctuation(paragraph)
            changed += 1
    return changed


def _highest_citation(paragraphs: list[Paragraph]) -> int:
    numbers = [n for paragraph in paragraphs for match in CITATION_RE.finditer(paragraph.text) for n in parse_numbers(match.group("numbers"))]
    return max(numbers, default=0)


def _options_for_list(options: FixOptions, entry_count: int, scope: list[Paragraph], several_lists: bool) -> FixOptions:
    """В документе с несколькими списками сдвиг номеров в тексте определяется по каждому списку отдельно."""
    if not several_lists or options.citation_offset or options.drop_citations:
        return options
    offset = max(0, _highest_citation(scope) - entry_count)
    return replace(options, citation_offset=offset, drop_citations=tuple(range(1, offset + 1)))


def fix_sources_list(document, options: FixOptions = FixOptions()) -> int:
    """Источники: без вводной фразы, тире и курсива; сайты по ВАК РБ; ненужные записи удалены; ссылки в тексте каждого раздела согласованы с номерами его списка."""
    paragraphs = _all_paragraphs(document)
    headings = [i for i, p in enumerate(paragraphs) if _is_heading(p) and p.text.strip().lower() == SOURCES_TITLE]
    total = 0
    scope_start = 0
    skip: set = set()
    for heading in headings:
        entries = _entry_paragraphs(paragraphs, heading)
        scope = [p for p in paragraphs[scope_start:heading] if p._p not in skip]
        skip |= {entry._p for entry in entries}
        list_options = _options_for_list(options, len(entries), scope, len(headings) > 1)
        mapping = _rebuild_entries(entries, list_options)
        renumber_citations(scope, mapping)
        total += sum(len(numbers) for numbers in mapping.values())
        scope_start = heading + 1
    return total


def fix_all_objects(document, options: FixOptions = FixOptions()) -> int:
    return (
        fix_title_date(document)
        + remove_filler_paragraphs(document)
        + fix_section_headings(document)
        + fix_subsection_spacing(document)
        + fix_objects(document)
        + fix_text_after_objects(document)
        + fix_appendix_headings(document)
        + fix_sources_list(document, options)
    )
