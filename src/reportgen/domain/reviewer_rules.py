from __future__ import annotations

import re

NBSP = " "
CODE_LIKE = re.compile(r"[()/={}]")
STRAIGHT_QUOTES_RE = re.compile(r'"([^"\n]{1,200})"')
REFERENCE_NUMBER_RE = re.compile(r"(?<![а-яёА-ЯЁ])((?:[Рр]исун\w*|[Тт]аблиц\w*|[Рр]ис\.|[Тт]абл\.))\s(?=\d)")
PARENTHESIS_REFERENCE_RE = re.compile(r"\((?:см\.?|рис\.?|рисунок|табл\.?|таблица)\s", re.IGNORECASE)
FILLER_WORD_RE = re.compile(r"(?<![а-яё])(также|были|было|была)(?![а-яё])", re.IGNORECASE)
MIN_PAGE_LINES = 11


def guillemets(text: str) -> str:
    """Прямые кавычки заменяются на «ёлочки»; фрагменты, похожие на код, остаются как есть."""

    def replace(match: re.Match) -> str:
        inner = match.group(1)
        return match.group(0) if CODE_LIKE.search(inner) else f"«{inner}»"

    return STRAIGHT_QUOTES_RE.sub(replace, text)


def glue_reference_numbers(text: str) -> str:
    """Слово «рисунок», «таблица» и номер не разрываются переносом строки (неразрывный пробел)."""
    return REFERENCE_NUMBER_RE.sub(lambda match: match.group(1) + NBSP, text)


def has_parenthesis_reference(text: str) -> bool:
    return PARENTHESIS_REFERENCE_RE.search(text) is not None


def has_filler_words(text: str) -> bool:
    return FILLER_WORD_RE.search(text) is not None
