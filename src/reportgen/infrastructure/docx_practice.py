from __future__ import annotations

import copy
import io
import re

from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

from reportgen.domain import enterprise_standard as standard

LISTING_CAPTION_RE = re.compile(r"^Листинг\s+(?P<number>\d+)\s*[–-]\s*(?P<title>.+?)\s*$")
OBJECT_CAPTION_RE = re.compile(r"^(?P<kind>Рисунок|Таблица)\s+(?P<number>\d+)(?P<rest>\s*[–-].*)$")
REFERENCE_RE = re.compile(r"(?P<noun>[Рр]исун\w*|[Тт]аблиц\w*)(?P<space>\s)(?P<first>\d+)(?:(?P<dash>[–-])(?P<second>\d+))?(?!\.\d)")
CITY_RE = re.compile(r"^Минск\s+\d{4}$")
CENTERED_HEADINGS = ('введение', 'заключение')
CONCLUSION_RE = re.compile(r"^\d+\s+выводы$", re.IGNORECASE)
HEADING_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+")
LATIN_RE = re.compile(r"([A-Za-z][A-Za-z0-9._/\-]*(?: [A-Za-z][A-Za-z0-9._/\-]*)*)")
FIGURE_CAPTION_RE = re.compile(r"^Рисунок\s+[\dА-Я]+(?:\.\d+)?\s*[–-]")
APPENDIX_LETTERS = "АБВГДЕЖИКЛМНПРСТУФХЦШЩЭЮЯ"
DARK_IMAGE_MAX_MEAN = 60
CODE_FONT_PT = 12
CODE_INDENT_CM = 1.25
MAX_PICTURE_WIDTH_CM = 8.5
TERMINAL_WIDTH_CM = 13.0
TERMINAL_MARGIN_PX = 12
TERMINAL_CONTENT_THRESHOLD = 40
FRAME_WIDTH_EMU = 6350
CODE_SPACE_CM = 0.2
QUESTION_GAP_PT = 18
FRAME_COLOR = "000000"
CONTENTS_TITLE = "Содержание"
TOC_FIELD = 'TOC \\o "1-1" \\h \\z \\u'
PICTURE_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
DRAWING_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
TEXT_WIDTH_CM = 21.0 - standard.MARGIN_LEFT_MM / 10 - standard.MARGIN_RIGHT_MM / 10


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


def _renumber_caption(paragraph: Paragraph, kind: str, number: str) -> None:
    """Номер в подписи меняется в первом фрагменте, остальные фрагменты (курсив латиницы) остаются нетронутыми."""
    for run in paragraph.runs:
        fixed, count = re.subn(rf"^{kind}\s+\d+", f"{kind} {number}", run.text, count=1)
        if count:
            run.text = fixed
            return


def number_objects_by_section(document) -> int:
    """Рисунки и таблицы нумеруются внутри раздела: «Рисунок 3.1», «Таблица 3.1»; ссылки в тексте обновляются."""
    section = ""
    counters: dict[tuple[str, str], int] = {}
    mapping: dict[tuple[str, str], str] = {}
    captions = []
    for paragraph in _body_paragraphs(document):
        text = paragraph.text.strip()
        if _is_heading(paragraph, 1):
            found = HEADING_NUMBER_RE.match(text)
            section = found.group(1) if found else ""
            continue
        caption = OBJECT_CAPTION_RE.match(text)
        if caption and section:
            kind = "рисун" if caption["kind"] == "Рисунок" else "таблиц"
            key = (section, kind)
            counters[key] = counters.get(key, 0) + 1
            new = f"{section}.{counters[key]}"
            mapping[(kind, caption["number"])] = new
            captions.append((paragraph, caption, new))
    if not mapping:
        return 0
    for paragraph, caption, new in captions:
        _renumber_caption(paragraph, caption["kind"], new)
    changed = len(captions)

    def replace(match: re.Match) -> str:
        kind = "рисун" if match["noun"].lower().startswith("рисун") else "таблиц"
        first = mapping.get((kind, match["first"]))
        if first is None:
            return match.group(0)
        second = match["second"]
        tail = f"{match['dash']}{mapping.get((kind, second), second)}" if second else ""
        return f"{match['noun']}{match['space']}{first}{tail}"

    for paragraph in _body_paragraphs(document):
        if OBJECT_CAPTION_RE.match(paragraph.text.strip()):
            continue
        for run in paragraph.runs:
            fixed = REFERENCE_RE.sub(replace, run.text)
            if fixed != run.text:
                run.text = fixed
                changed += 1
    return changed


def start_sections_on_new_page(document) -> int:
    """Каждый раздел первого уровня начинается с новой страницы."""
    changed = 0
    for paragraph in document.paragraphs:
        if _is_heading(paragraph, 1):
            paragraph.paragraph_format.page_break_before = True
            changed += 1
    return changed


def rename_conclusion(document) -> int:
    """«5 Выводы» становится «Заключение» без номера, по центру."""
    changed = 0
    for paragraph in document.paragraphs:
        if _is_heading(paragraph, 1) and CONCLUSION_RE.match(paragraph.text.strip()):
            _set_text(paragraph, "Заключение")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            changed += 1
    return changed


def capital_section_headings(document) -> int:
    """Заголовки разделов выглядят прописными, а в тексте остаются обычными: так содержание пишется строчными, как в образце."""
    document.styles["Heading 1"].font.all_caps = True
    return sum(1 for paragraph in document.paragraphs if _is_heading(paragraph, 1))


def align_headings(document) -> int:
    """Заголовки выравниваются влево с абзацным отступом (введение, заключение и приложения по центру); вопросы полужирным влево."""
    changed = 0
    for paragraph in document.paragraphs:
        is_bold_question = paragraph.text.strip().endswith("?") and bool(paragraph.runs) and all(run.bold for run in paragraph.runs if run.text.strip())
        if _is_heading(paragraph, 1) and paragraph.text.strip().lower() in CENTERED_HEADINGS:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.first_line_indent = Cm(0)
            changed += 1
        elif paragraph.style.name.startswith("Heading") and paragraph.alignment != WD_ALIGN_PARAGRAPH.CENTER:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.first_line_indent = Cm(standard.PARAGRAPH_INDENT_CM)
            changed += 1
        elif is_bold_question:
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


def _contents_style(document) -> None:
    """Строки содержания: Times New Roman 14, одинарный интервал, без отступов, как в образце."""
    names = [style.name for style in document.styles]
    style = document.styles["toc 1"] if "toc 1" in names else document.styles.add_style("toc 1", WD_STYLE_TYPE.PARAGRAPH)
    style.element.attrib.pop(qn("w:customStyle"), None)
    style.element.set(qn("w:styleId"), "TOC1")
    style.base_style = document.styles["Normal"]
    style.font.name = standard.FONT
    style.font.size = Pt(standard.FONT_SIZE_PT)
    style.font.bold = False
    fmt = style.paragraph_format
    fmt.first_line_indent = Cm(0)
    fmt.left_indent = Cm(0)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT


def insert_contents(document) -> int:
    """Содержание: заголовок «Содержание» и поле оглавления по разделам перед первым разделом; номера страниц обновляет Word."""
    if _has_contents(document):
        return 0
    first = next((p for p in document.paragraphs if _is_heading(p, 1)), None)
    if first is None:
        return 0
    _contents_style(document)
    title = _blank_copy(first)
    first._p.addprevious(title._p)
    title.style = document.styles["Normal"]
    run = title.add_run(CONTENTS_TITLE.upper())
    run.bold = True
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


def _ensure_listing_style(document):
    """Стиль «Listing» для программного кода: аудит не считает такие абзацы основным текстом."""
    if standard.LISTING_STYLE in [style.name for style in document.styles]:
        return document.styles[standard.LISTING_STYLE]
    style = document.styles.add_style(standard.LISTING_STYLE, WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = document.styles["Normal"]
    style.font.name = standard.FONT
    style.font.italic = True
    return style


def _strip_leading_spaces(paragraph: Paragraph) -> int:
    """Пробелы в начале строки кода превращаются в отступ абзаца, чтобы перенесённые строки выравнивались так же."""
    runs = [run for run in paragraph.runs if run.text]
    if not runs:
        return 0
    text = runs[0].text.expandtabs(4)
    stripped = text.lstrip(" ")
    runs[0].text = stripped
    return len(text) - len(stripped)


def _format_code(paragraph: Paragraph, style) -> None:
    paragraph.style = style
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fmt = paragraph.paragraph_format
    fmt.left_indent = Cm(CODE_INDENT_CM + _strip_leading_spaces(paragraph) * CODE_SPACE_CM)
    fmt.first_line_indent = Cm(0)
    fmt.line_spacing_rule = WD_LINE_SPACING.SINGLE
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    for run in paragraph.runs:
        run.italic = True
        run.bold = False
        run.font.name = standard.FONT
        run.font.size = Pt(CODE_FONT_PT)


def _add_runs(paragraph: Paragraph, text: str, capital: bool = True) -> None:
    """Текст полужирным; латиница курсивом, как в остальном документе; прописные буквы только у слова «Приложение»."""
    for index, piece in enumerate(LATIN_RE.split(text)):
        if piece:
            run = paragraph.add_run(piece)
            run.bold = True
            run.italic = index % 2 == 1
            run.font.all_caps = capital


def _appendix_heading(source: Paragraph, letter: str, title: str) -> Paragraph:
    """Приложение одним заголовком из трёх строк: «Приложение А», «(обязательное)», название; в содержание попадает целиком."""
    paragraph = _blank_copy(source)
    lines = (f"Приложение {letter}", "(обязательное)", title)
    for index, line in enumerate(lines):
        _add_runs(paragraph, line, capital=index == 0)
        if index < len(lines) - 1:
            paragraph.runs[-1].add_break()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Cm(0)
    paragraph.paragraph_format.left_indent = Cm(0)
    paragraph.paragraph_format.page_break_before = True
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_after = Pt(standard.LINE_SPACING_PT)
    return paragraph


def listings_to_appendices(document) -> int:
    """Каждый листинг переносится в своё приложение (название приложения берётся из подписи листинга); код набирается курсивом."""
    blocks = _listing_blocks(document)
    if not blocks:
        return 0
    source = next(p for p in document.paragraphs if _is_heading(p, 1))
    section_properties = document.element.body.find(qn("w:sectPr"))
    anchor = section_properties.getprevious() if section_properties is not None else document.element.body[-1]
    code_style = _ensure_listing_style(document)
    for letter, (caption, code) in zip(APPENDIX_LETTERS, blocks, strict=False):
        title = LISTING_CAPTION_RE.match(caption.text.strip())["title"]
        heading = _appendix_heading(source, letter, title)
        anchor.addnext(heading._p)
        anchor = heading._p
        for element in code:
            anchor.addnext(element)
            anchor = element
            _format_code(Paragraph(element, caption._parent), code_style)
        caption._p.getparent().remove(caption._p)
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


def _terminal_bounds(image):
    """Рамка содержимого на светлом снимке терминала: пустые поля вокруг текста отрезаются."""
    from PIL import Image, ImageChops

    background = image.getpixel((0, 0))
    difference = ImageChops.difference(image, Image.new("RGB", image.size, background)).convert("L")
    return difference.point(lambda value: 255 if value > TERMINAL_CONTENT_THRESHOLD else 0).getbbox()


def terminal_screenshots(document) -> int:
    """Снимки терминала на чёрном фоне переводятся в светлый вариант, обрезаются по тексту и показываются крупнее, чтобы строки читались."""
    from PIL import Image, ImageOps, ImageStat

    changed = 0
    for shape in document.inline_shapes:
        identifiers = shape._inline.xpath(".//a:blip/@r:embed")
        if not identifiers:
            continue
        part = document.part.related_parts[identifiers[0]]
        try:
            image = Image.open(io.BytesIO(part.blob)).convert("RGB")
        except OSError:
            continue
        if ImageStat.Stat(image.convert("L")).mean[0] >= DARK_IMAGE_MAX_MEAN:
            continue
        light = ImageOps.invert(image)
        bounds = _terminal_bounds(light)
        if bounds:
            left, top, right, bottom = bounds
            margin = TERMINAL_MARGIN_PX
            light = light.crop((max(0, left - margin), max(0, top - margin), min(light.width, right + margin), min(light.height, bottom + margin)))
        buffer = io.BytesIO()
        light.save(buffer, format="PNG")
        part._blob = buffer.getvalue()
        shape.height = int(Cm(TERMINAL_WIDTH_CM) * light.height / light.width)
        shape.width = Cm(TERMINAL_WIDTH_CM)
        changed += 1
    return changed


def flatten_subsections(document) -> int:
    """Подразделы убираются: в отчётах по лабораторным и практическим работам текст раздела идёт без подзаголовков."""
    removed = 0
    for paragraph in list(document.paragraphs):
        if paragraph.style.name.startswith("Heading") and not paragraph.style.name.endswith("1") and paragraph.text.strip():
            paragraph._p.getparent().remove(paragraph._p)
            removed += 1
    return removed


def page_numbers_right(document) -> int:
    """Номер страницы у правого края нижнего колонтитула."""
    changed = 0
    for section in document.sections:
        for paragraph in section.footer.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            changed += 1
    return changed


def blank_line_before_captions(document) -> int:
    """Между рисунком и его подписью пустая строка."""
    changed = 0
    for paragraph in _body_paragraphs(document):
        if FIGURE_CAPTION_RE.match(paragraph.text.strip()):
            paragraph.paragraph_format.space_before = Pt(standard.LINE_SPACING_PT)
            changed += 1
    return changed


def keep_objects_inside_text(document) -> int:
    """Страница не начинается и не заканчивается рисунком или таблицей: перед объектом и после него абзацы держатся на той же странице."""
    changed = 0
    paragraphs = _body_paragraphs(document)
    for index, paragraph in enumerate(paragraphs):
        is_picture = bool(paragraph._p.xpath(".//w:drawing"))
        is_table_caption = re.match(r"^Таблица\s+[\dА-Я]+(?:\.\d+)?\s*[–-]", paragraph.text.strip()) is not None
        if (is_picture or is_table_caption) and index:
            paragraphs[index - 1].paragraph_format.keep_with_next = True
            changed += 1
    for table in document.tables:
        for cell in table.rows[-1].cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.keep_with_next = True
        changed += 1
    return changed


def space_questions(document) -> int:
    """Контрольные вопросы разделяются пустой строкой."""
    changed = 0
    previous_is_heading = True
    for paragraph in document.paragraphs:
        is_question = paragraph.text.strip().endswith("?") and bool(paragraph.runs) and all(run.bold for run in paragraph.runs if run.text.strip())
        if is_question and not previous_is_heading:
            paragraph.paragraph_format.space_before = Pt(QUESTION_GAP_PT)
            changed += 1
        previous_is_heading = paragraph.style.name.startswith("Heading")
    return changed


def fit_pictures(document) -> int:
    """Рисунки не шире 12 см с сохранением пропорций: меньше пустых мест на страницах."""
    changed = 0
    limit = Cm(MAX_PICTURE_WIDTH_CM)
    for shape in document.inline_shapes:
        if shape.width > limit:
            ratio = limit / shape.width
            shape.height = int(shape.height * ratio)
            shape.width = int(limit)
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
        + number_objects_by_section(document)
        + listings_to_appendices(document)
        + flatten_subsections(document)
        + dash_lists(document)
        + start_sections_on_new_page(document)
        + capital_section_headings(document)
        + align_headings(document)
        + insert_contents(document)
        + city_at_page_bottom(document)
        + frame_screenshots(document)
        + fit_pictures(document)
        + terminal_screenshots(document)
        + keep_figures_with_text(document)
        + blank_line_before_captions(document)
        + keep_objects_inside_text(document)
        + space_questions(document)
        + page_numbers_right(document)
    )
