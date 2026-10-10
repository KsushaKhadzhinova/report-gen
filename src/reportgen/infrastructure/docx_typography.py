from __future__ import annotations

from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from reportgen.domain.reviewer_rules import NBSP, REFERENCE_NUMBER_RE, glue_reference_numbers, guillemets

HYPERLINK_STYLE = "Hyperlink"


def _all_paragraphs(document) -> list[Paragraph]:
    return [Paragraph(element, document) for element in document.element.body.iter(qn("w:p"))]


def _fix_run_texts(paragraph: Paragraph) -> int:
    changed = 0
    for run in paragraph.runs:
        text = run.text
        if not text:
            continue
        fixed = glue_reference_numbers(guillemets(text))
        if fixed != text:
            run.text = fixed
            changed += 1
    return changed


def _glue_across_runs(paragraph: Paragraph) -> int:
    """«рисунок » в одном фрагменте и номер в следующем: пробел между ними становится неразрывным."""
    changed = 0
    runs = [run for run in paragraph.runs if run.text]
    for current, following in zip(runs, runs[1:], strict=False):
        if current.text.endswith(" ") and following.text[:1].isdigit() and REFERENCE_NUMBER_RE.search(current.text[-12:] + "0"):
            current.text = current.text[:-1] + NBSP
            changed += 1
    return changed


def fix_quotes_and_reference_spaces(document) -> int:
    """Кавычки «…» вместо "…", неразрывный пробел между словами «рисунок», «таблица» и номером."""
    return sum(_fix_run_texts(p) + _glue_across_runs(p) for p in _all_paragraphs(document))


def _plain_run_properties(run_element) -> None:
    properties = run_element.get_or_add_rPr()
    for tag in ("w:color", "w:u", "w:rStyle"):
        for found in properties.findall(qn(tag)):
            properties.remove(found)
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "auto")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "none")
    properties.append(color)
    properties.append(underline)


def fix_hyperlink_look(document) -> int:
    """Гиперссылки набираются обычным цветом и без подчёркивания."""
    fixed = 0
    if HYPERLINK_STYLE in [style.name for style in document.styles]:
        font = document.styles[HYPERLINK_STYLE].font
        font.underline = False
        font.color.rgb = None
    body = document.element.body
    for element in body.iter(qn("w:hyperlink")):
        for run in element.iter(qn("w:r")):
            _plain_run_properties(run)
            fixed += 1
    for run in body.iter(qn("w:r")):
        style = run.find(qn("w:rPr") + "/" + qn("w:rStyle")) if run.find(qn("w:rPr")) is not None else None
        if style is not None and style.get(qn("w:val")) == HYPERLINK_STYLE:
            _plain_run_properties(run)
            fixed += 1
    return fixed
