from __future__ import annotations

import re

NBSP = " "
CODE_LIKE = re.compile(r"[()/={}]")
STRAIGHT_QUOTES_RE = re.compile(r'"([^"\n]{1,200})"')
REFERENCE_NUMBER_RE = re.compile(r"(?<![а-яёА-ЯЁ])((?:[Рр]исун\w*|[Тт]аблиц\w*|[Рр]ис\.|[Тт]абл\.))\s(?=\d)")
PARENTHESIS_REFERENCE_RE = re.compile(r"\((?:см\.?|рис\.?|рисунок|табл\.?|таблица)\s", re.IGNORECASE)
FILLER_WORD_RE = re.compile(r"(?<![а-яё])(также|были|было|была)(?![а-яё])", re.IGNORECASE)
MIN_PAGE_LINES = 11
SMALL_NUMBER_RE = re.compile(r"(?<![\w.,/№#+\-–−])([1-9])(?![\d.,:/%\-–)\]°])\s+([а-яё]{3,})")
NUMBER_CONTEXT_RE = re.compile(r"(рисун\w*|таблиц\w*|раздел\w*|пункт\w*|приложени\w*|страниц\w*|глав\w*|шаг\w*|этап\w*|верси\w*|листинг\w*|вариант\w*|гр\.|№|занятию|работе|работа|работ)\s*$")
UNIT_WORD_RE = re.compile(r"^(секунд\w*|минут\w*|час\w*|дн\w*|байт\w*|рубл\w*|руб|пиксел\w*|процент\w*|градус\w*|метр\w*|килограмм\w*|ватт\w*|герц\w*|кадр\w*)$")


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


def has_small_digit_numerals(text: str) -> bool:
    """Числа от одного до девяти без единиц измерения в тексте пишутся словами (СТП, п. 2.3.12)."""
    for match in SMALL_NUMBER_RE.finditer(text):
        before = text[max(0, match.start() - 20) : match.start()].lower()
        if NUMBER_CONTEXT_RE.search(before) or UNIT_WORD_RE.match(match.group(2)):
            continue
        return True
    return False
