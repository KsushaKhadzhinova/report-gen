from __future__ import annotations

FONT = "Times New Roman"
FONT_SIZE_PT = 14
LINE_SPACING_PT = 18
PARAGRAPH_INDENT_CM = 1.25
LISTING_STYLE = "Listing"
LISTING_FONT_SIZE_PT = 12

MARGIN_LEFT_MM = 30
MARGIN_RIGHT_MM = 15
MARGIN_TOP_MM = 20
MARGIN_BOTTOM_MM = 20

UNNUMBERED_HEADINGS = {
    "СОДЕРЖАНИЕ",
    "РЕФЕРАТ",
    "ВВЕДЕНИЕ",
    "ЗАКЛЮЧЕНИЕ",
    "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
}

DASH = "–"


def figure_caption(number: str, caption: str) -> str:
    return f"Рисунок {number} {DASH} {caption}"


def table_caption(number: str, caption: str) -> str:
    return f"Таблица {number} {DASH} {caption}"


def listing_caption(number: str, caption: str) -> str:
    return f"Листинг {number} {DASH} {caption}"


def appendix_title(letter: str, title: str) -> tuple[str, str]:
    return f"ПРИЛОЖЕНИЕ {letter}", title


def list_items(items: list[str]) -> list[str]:
    """Простое перечисление: тире, пункты оканчиваются «;», последний — «.»."""
    result = []
    for index, item in enumerate(items):
        body = item.rstrip(";.")
        result.append(f"{DASH} {body}{'.' if index == len(items) - 1 else ';'}")
    return result
