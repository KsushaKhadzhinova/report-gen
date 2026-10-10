from __future__ import annotations

from pathlib import Path

from reportgen.domain.lint_rules import Issue
from reportgen.domain.reviewer_rules import MIN_PAGE_LINES

FOOTER_START = 0.93
SKIPPED_FIRST_PAGES = 2


def _text_lines(page) -> int:
    limit = page.rect.height * FOOTER_START
    lines = 0
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            if line["bbox"][3] < limit and "".join(span["text"] for span in line["spans"]).strip():
                lines += 1
    return lines


def _has_picture(page) -> bool:
    return bool(page.get_images())


def page_fill_issues(path: Path) -> list[Issue]:
    """Страницы, где меньше 11 строк текста (около четверти страницы). Страницы с рисунками, титул и последняя страница не проверяются."""
    import pymupdf

    issues: list[Issue] = []
    with pymupdf.open(str(path)) as pdf:
        for number, page in enumerate(pdf, 1):
            if number <= SKIPPED_FIRST_PAGES or number == len(pdf) or _has_picture(page):
                continue
            lines = _text_lines(page)
            if lines < MIN_PAGE_LINES:
                issues.append(Issue("warning", f"{path.name}, страница {number}", f"{lines} строк на странице, нужно не менее {MIN_PAGE_LINES}: дописать текст или сократить предыдущую страницу"))
    return issues
