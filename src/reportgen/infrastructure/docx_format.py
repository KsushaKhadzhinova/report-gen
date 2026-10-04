from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt

from reportgen.domain import stp
from reportgen.domain.lint_rules import Issue

MIN_BODY_PARAGRAPH_CHARS = 80
MARGIN_TOLERANCE = Mm(1)
INDENT_TOLERANCE = Cm(0.1)


def _is_body(paragraph) -> bool:
    return len(paragraph.text) >= MIN_BODY_PARAGRAPH_CHARS and not paragraph.style.name.startswith("Heading")


def _has_foreign_font(paragraph) -> bool:
    return any(
        run.font.name not in (None, stp.FONT) or run.font.size not in (None, Pt(stp.FONT_SIZE_PT)) for run in paragraph.runs
    )


def _has_wrong_indent(paragraph) -> bool:
    indent = paragraph.paragraph_format.first_line_indent
    return indent is None or abs(indent - Cm(stp.PARAGRAPH_INDENT_CM)) > INDENT_TOLERANCE


def _margin_issues(document, name: str) -> list[Issue]:
    section = document.sections[0]
    expected = {
        "левое поле": (section.left_margin, stp.MARGIN_LEFT_MM),
        "правое поле": (section.right_margin, stp.MARGIN_RIGHT_MM),
        "верхнее поле": (section.top_margin, stp.MARGIN_TOP_MM),
        "нижнее поле": (section.bottom_margin, stp.MARGIN_BOTTOM_MM),
    }
    return [
        Issue("error", name, f"{label}: ожидается {wanted_mm} мм")
        for label, (actual, wanted_mm) in expected.items()
        if actual is None or abs(actual - Mm(wanted_mm)) > MARGIN_TOLERANCE
    ]


class _DocxText:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.document = Document(str(path))

    def paragraphs(self) -> list[str]:
        return [p.text for p in self.document.paragraphs if p.text.strip()]

    def replace(self, old: str, new: str) -> None:
        for paragraph in self.document.paragraphs:
            if paragraph.text == old:
                for run in paragraph.runs[1:]:
                    run._r.getparent().remove(run._r)
                if paragraph.runs:
                    paragraph.runs[0].text = new
                else:
                    paragraph.add_run(new)

    def save(self) -> None:
        self.document.save(str(self.path))


class DocxFormatService:
    def audit(self, path: Path) -> list[Issue]:
        document = Document(str(path))
        issues = _margin_issues(document, path.name)
        if document.styles["Normal"].font.name != stp.FONT:
            issues.append(Issue("error", path.name, f"Шрифт Normal не {stp.FONT}"))
        body = [p for p in document.paragraphs if _is_body(p)]
        counts = {
            "абзацев с другим шрифтом или размером": sum(_has_foreign_font(p) for p in body),
            "абзацев с абзацным отступом не 1,25 см": sum(_has_wrong_indent(p) for p in body),
            "абзацев не по ширине": sum(p.alignment not in (None, WD_ALIGN_PARAGRAPH.JUSTIFY) for p in body),
        }
        issues += [Issue("error", path.name, f"{count} {label}") for label, count in counts.items() if count]
        return issues

    def fix(self, source: Path, output: Path) -> int:
        document = Document(str(source))
        self._fix_page(document)
        self._fix_normal_style(document)
        fixed = sum(self._fix_paragraph(p) for p in document.paragraphs)
        output.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output))
        return fixed

    def open_text(self, path: Path) -> _DocxText:
        return _DocxText(path)

    @staticmethod
    def _fix_page(document) -> None:
        for section in document.sections:
            section.left_margin = Mm(stp.MARGIN_LEFT_MM)
            section.right_margin = Mm(stp.MARGIN_RIGHT_MM)
            section.top_margin = Mm(stp.MARGIN_TOP_MM)
            section.bottom_margin = Mm(stp.MARGIN_BOTTOM_MM)

    @staticmethod
    def _fix_normal_style(document) -> None:
        normal = document.styles["Normal"]
        normal.font.name = stp.FONT
        normal.font.size = Pt(stp.FONT_SIZE_PT)
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), stp.FONT)

    @staticmethod
    def _fix_paragraph(paragraph) -> int:
        if paragraph.style.name.startswith("Heading") or not paragraph.text.strip():
            return 0
        for run in paragraph.runs:
            run.font.name = stp.FONT
            run.font.size = Pt(stp.FONT_SIZE_PT)
        if len(paragraph.text) < MIN_BODY_PARAGRAPH_CHARS or paragraph.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            return 0
        fmt = paragraph.paragraph_format
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        fmt.first_line_indent = Cm(stp.PARAGRAPH_INDENT_CM)
        fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        fmt.line_spacing = Pt(stp.LINE_SPACING_PT)
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        return 1
