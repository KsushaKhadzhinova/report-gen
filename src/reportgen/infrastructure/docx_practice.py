from __future__ import annotations

import copy
import io
import re

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

from reportgen.domain import enterprise_standard as standard

LISTING_CAPTION_RE = re.compile(r"^Листинг\s+(?P<number>\d+)\s*[–-]\s*(?P<title>.+?)\s*$")
FIGURE_CAPTION_RE = re.compile(r"^Рисунок\s+[\dА-Я]+(?:\.\d+)?\s*[–-]")
CITY_RE = re.compile(r"^Минск\s+\d{4}$")
CONCLUSION_RE = re.compile(r"^\d+\s+выводы$", re.IGNORECASE)
HEADING_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\s+")
APPENDIX_LETTERS = "АБВГДЕЖИКЛМНПРСТУФХЦШЩЭЮЯ"
DARK_IMAGE_MAX_MEAN = 60
CODE_FONT_PT = 12
FRAME_WIDTH_EMU = 12700
FRAME_COLOR = "000000"
CONTENTS_TITLE = "СОДЕРЖАНИЕ"
TOC_FIELD = 'TOC \\o "1-2" \\h \\z \\u'
PICTURE_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
DRAWING_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def _is_heading(paragraph, level: int | None = None) -> bool:
    wanted = f"Heading {level}" if level else "Heading"
    return paragraph.style.name.startswith(wanted) and bool(paragraph.text.strip())


def _body_paragraphs(document) -> list[Paragraph]:
    return [Paragraph(element, document) for element in document.element.body.iterchildren() if element.tag == qn("w:p")]


def _set_text(paragraph: Paragraph, text: str) -> None:
    for run in paragraph.runs[1:]:
        run._r.getparent().remove(run._r)
    if paragraph.runs:
        paragraph.runs[0].text = text
    else:
        paragraph.add_run(text)


def _blank_copy(source: Paragraph) -> Paragraph:
    """Пустой абзац с теми же свойствами абзаца, что у образца."""
    element = copy.deepcopy(source._p)
    for child in list(element):
        if child.tag != qn("w:pPr"):
            element.remove(child)
    return Paragraph(element, source._parent)


def start_sections_on_new_page(document) -> int:
    """Каждый раздел первого уровня начинается с новой страницы."""
    changed = 0
    for paragraph in document.paragraphs:
        if _is_heading(paragraph, 1):
            paragraph.paragraph_format.page_break_before = True
            changed += 1
    return changed


def rename_conclusion(document) -> int:
    """«5 Выводы» становится «ЗАКЛЮЧЕНИЕ» без номера, по центру."""
    changed = 0
    for paragraph in document.paragraphs:
        if _is_heading(paragraph, 1) and CONCLUSION_RE.match(paragraph.text.strip()):
            _set_text(paragraph, "ЗАКЛЮЧЕНИЕ")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            changed += 1
    return changed


def left_align_headings(document) -> int:
    """Заголовки и вопросы полужирным выравниваются влево: при выравнивании по ширине между числом и названием появляются большие пробелы."""
    changed = 0
    for paragraph in document.paragraphs:
        is_bold_question = paragraph.text.strip().endswith("?") and bool(paragraph.runs) and all(run.bold for run in paragraph.runs if run.text.strip())
        justified_heading = paragraph.style.name.startswith("Heading") and paragraph.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
        if justified_heading or is_bold_question:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            changed += 1
    return changed


def _append_ending(paragraph: Paragraph, ending: str) -> None:
    runs = [run for run in paragraph.runs if run.text]
    runs[-1].text = runs[-1].text.rstrip(" ;.,")
    tail = paragraph.add_run(ending)
    tail.italic = False
    tail.bold = False


def _bullet_groups(document) -> list[list[Paragraph]]:
    groups: list[list[Paragraph]] = []
    previous = None
    for paragraph in _body_paragraphs(document):
        is_item = paragraph.style.name.startswith("List Bullet") and bool(paragraph.text.strip())
        if is_item and groups and previous is not None and previous._p.getnext() is paragraph._p:
            groups[-1].append(paragraph)
        elif is_item:
            groups.append([paragraph])
        previous = paragraph
    return groups


def dash_lists(document) -> int:
    """Маркированные списки: «– текст;», после последнего пункта точка; пункт начинается с абзацного отступа, без висячего отступа."""
    changed = 0
    for group in _bullet_groups(document):
        for position, paragraph in enumerate(group):
            runs = [run for run in paragraph.runs if run.text]
            if not runs:
                continue
            runs[0].text = "– " + runs[0].text.lstrip("•–-\t ")
            _append_ending(paragraph, "." if position == len(group) - 1 else ";")
            paragraph.style = document.styles["Normal"]
            properties = paragraph._p.get_or_add_pPr()
            for numbering in properties.findall(qn("w:numPr")):
                properties.remove(numbering)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.left_indent = Cm(0)
            paragraph.paragraph_format.first_line_indent = Cm(standard.PARAGRAPH_INDENT_CM)
            changed += 1
    return changed


def _has_contents(document) -> bool:
    return any("TOC" in (text.text or "") for text in document.element.body.iter(qn("w:instrText")))


def _toc_field_paragraph() -> OxmlElement:
    paragraph = OxmlElement("w:p")
    parts = (("begin", None), ("instr", TOC_FIELD), ("separate", None), ("text", "Обновите поле, чтобы увидеть содержание"), ("end", None))
    for kind, content in parts:
        run = OxmlElement("w:r")
        if kind == "instr":
            element = OxmlElement("w:instrText")
            element.set(qn("xml:space"), "preserve")
            element.text = content
        elif kind == "text":
            element = OxmlElement("w:t")
            element.text = content
        else:
            element = OxmlElement("w:fldChar")
            element.set(qn("w:fldCharType"), kind)
        run.append(element)
        paragraph.append(run)
    return paragraph


def insert_contents(document) -> int:
    """Содержание: заголовок «СОДЕРЖАНИЕ» и поле оглавления перед первым разделом; номера страниц обновляет Word."""
    if _has_contents(document):
        return 0
    first = next((p for p in document.paragraphs if _is_heading(p, 1)), None)
    if first is None:
        return 0
    title = _blank_copy(first)
    first._p.addprevious(title._p)
    title.style = document.styles["Normal"]
    title.add_run(CONTENTS_TITLE).bold = True
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.first_line_indent = Cm(0)
    title.paragraph_format.page_break_before = True
    title.paragraph_format.space_after = Pt(standard.LINE_SPACING_PT)
    title._p.addnext(_toc_field_paragraph())
    return 1


def city_at_page_bottom(document) -> int:
    """«Минск 2026» на последней строке титульного листа: абзац привязан к нижнему полю."""
    for paragraph in document.paragraphs[:40]:
        if not CITY_RE.match(paragraph.text.strip()):
            continue
        properties = paragraph._p.get_or_add_pPr()
        for frame in properties.findall(qn("w:framePr")):
            properties.remove(frame)
        frame = OxmlElement("w:framePr")
        for name, value in (("w", "3000"), ("hSpace", "0"), ("wrap", "around"), ("vAnchor", "margin"), ("hAnchor", "margin"), ("xAlign", "center"), ("yAlign", "bottom")):
            frame.set(qn(f"w:{name}"), value)
        properties.insert(0, frame)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        return 1
    return 0


def _listing_blocks(document) -> list[tuple[Paragraph, list]]:
    """Подписи листингов и элементы кода под ними (до следующего заголовка или подписи листинга)."""
    found = []
    for paragraph in _body_paragraphs(document):
        if not LISTING_CAPTION_RE.match(paragraph.text.strip()):
            continue
        code = []
        element = paragraph._p.getnext()
        while element is not None and element.tag == qn("w:p"):
            following = Paragraph(element, paragraph._parent)
            if following.style.name.startswith("Heading") or LISTING_CAPTION_RE.match(following.text.strip()):
                break
            code.append(element)
            element = element.getnext()
        found.append((paragraph, code))
    return found


def _owner_subsection(paragraph: Paragraph) -> str:
    element = paragraph._p.getprevious()
    while element is not None:
        if element.tag == qn("w:p"):
            candidate = Paragraph(element, paragraph._parent)
            if candidate.style.name.startswith("Heading 2"):
                return HEADING_NUMBER_RE.sub("", candidate.text.strip())
        element = element.getprevious()
    return "общий"


def _format_code(paragraph: Paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Cm(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    for run in paragraph.runs:
        run.italic = True
        run.bold = False
        run.font.name = standard.FONT
        run.font.size = Pt(CODE_FONT_PT)


def _centered_line(source: Paragraph, text: str, as_heading: bool, page_break: bool = False) -> Paragraph:
    paragraph = _blank_copy(source)
    if not as_heading:
        paragraph.style = source.part.document.styles["Normal"]
    paragraph.add_run(text).bold = True
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.left_indent = Cm(0)
    paragraph.paragraph_format.page_break_before = page_break
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def listings_to_appendices(document) -> int:
    """Листинги переносятся в приложения (по одному на подраздел), подписи получают номера вида «Листинг А.1», код набирается курсивом."""
    blocks = _listing_blocks(document)
    if not blocks:
        return 0
    groups: dict[str, list[tuple[Paragraph, list]]] = {}
    for caption, code in blocks:
        groups.setdefault(_owner_subsection(caption), []).append((caption, code))
    source = next(p for p in document.paragraphs if _is_heading(p, 1))
    section_properties = document.element.body.find(qn("w:sectPr"))
    anchor = section_properties.getprevious() if section_properties is not None else document.element.body[-1]
    for index, (subsection, listings) in enumerate(groups.items()):
        letter = APPENDIX_LETTERS[index]
        title = f"Исходный код: {subsection[:1].lower()}{subsection[1:]}"
        heading = _centered_line(source, f"ПРИЛОЖЕНИЕ {letter}", as_heading=True, page_break=True)
        status = _centered_line(source, "(обязательное)", as_heading=False)
        name = _centered_line(source, title, as_heading=False)
        name.paragraph_format.space_after = Pt(standard.LINE_SPACING_PT)
        for line in (heading, status, name):
            anchor.addnext(line._p)
            anchor = line._p
        for position, (caption, code) in enumerate(listings, 1):
            match = LISTING_CAPTION_RE.match(caption.text.strip())
            _set_text(caption, f"Листинг {letter}.{position} – {match['title']}")
            caption.alignment = WD_ALIGN_PARAGRAPH.LEFT
            caption.paragraph_format.first_line_indent = Cm(0)
            caption.paragraph_format.keep_with_next = True
            caption.paragraph_format.space_before = Pt(standard.LINE_SPACING_PT)
            for run in caption.runs:
                run.italic = False
            for element in [caption._p, *code]:
                anchor.addnext(element)
                anchor = element
            for element in code:
                _format_code(Paragraph(element, caption._parent))
    return len(blocks)


def frame_screenshots(document) -> int:
    """У экранных форм (скриншотов) тонкая рамка; схемы и диаграммы без рамки."""
    changed = 0
    for properties in document.element.body.iter(f"{{{PICTURE_NS}}}spPr"):
        if properties.find("a:ln", DRAWING_NS) is not None:
            continue
        line = OxmlElement("a:ln")
        line.set("w", str(FRAME_WIDTH_EMU))
        fill = OxmlElement("a:solidFill")
        color = OxmlElement("a:srgbClr")
        color.set("val", FRAME_COLOR)
        fill.append(color)
        line.append(fill)
        properties.append(line)
        changed += 1
    return changed


def lighten_dark_screenshots(document) -> int:
    """Снимки терминала на чёрном фоне переводятся в светлый вариант: чёрное пятно на странице не нужно."""
    from PIL import Image, ImageOps, ImageStat

    changed = 0
    for relationship in list(document.part.rels.values()):
        if "image" not in relationship.reltype:
            continue
        part = relationship.target_part
        try:
            image = Image.open(io.BytesIO(part.blob)).convert("RGB")
        except OSError:
            continue
        if ImageStat.Stat(image.convert("L")).mean[0] >= DARK_IMAGE_MAX_MEAN:
            continue
        buffer = io.BytesIO()
        ImageOps.invert(image).save(buffer, format="PNG")
        part._blob = buffer.getvalue()
        changed += 1
    return changed


def keep_figures_with_text(document) -> int:
    """Рисунок не остаётся последним на странице: подпись держится со следующим абзацем."""
    changed = 0
    paragraphs = _body_paragraphs(document)
    for paragraph, following in zip(paragraphs, paragraphs[1:], strict=False):
        if FIGURE_CAPTION_RE.match(paragraph.text.strip()) and following.text.strip():
            paragraph.paragraph_format.keep_with_next = True
            changed += 1
    return changed


def apply_practice_layout(document) -> int:
    return (
        rename_conclusion(document)
        + listings_to_appendices(document)
        + dash_lists(document)
        + start_sections_on_new_page(document)
        + left_align_headings(document)
        + insert_contents(document)
        + city_at_page_bottom(document)
        + frame_screenshots(document)
        + lighten_dark_screenshots(document)
        + keep_figures_with_text(document)
    )
