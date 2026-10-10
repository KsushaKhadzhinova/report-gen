from __future__ import annotations

import re
from dataclasses import dataclass

from reportgen.domain import enterprise_standard as standard
from reportgen.domain.blocks import Block, Kind
from reportgen.domain.reviewer_rules import STRAIGHT_QUOTES_RE, has_filler_words, has_parenthesis_reference, has_small_digit_numerals

FIRST_PERSON_RE = re.compile(r"(?<![а-яё])(я|мы|наш\w*|мой|моя)(?![а-яё])", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"TODO|\[нет файла|\[УТОЧНИТЬ|\?\?|lorem ipsum", re.IGNORECASE)
EXCERPT_LENGTH = 60
WORDS_PER_PAGE = 300
INTRODUCTION_MAX_WORDS = 2 * WORDS_PER_PAGE
CONCLUSION_MAX_WORDS = 2 * WORDS_PER_PAGE + WORDS_PER_PAGE // 4
CITATION_RE = re.compile(r"\[(\d+)\]")
PERIOD_BEFORE_CITATION_RE = re.compile(r"\.\s*\[\d+\]")
PREPOSITION_BEFORE_UNIT_RE = re.compile(r"\bв\s+\d+(?:,\d+)?\s*(?:Вт|кВт|В|А|Гц|кг|мм|см|км|м|с|мс|%)(?![а-яёА-ЯЁ])")
LONG_DASH = "\u2014"
WIKIPEDIA_RE = re.compile(r"wikipedia|википеди", re.IGNORECASE)


@dataclass(frozen=True)
class Issue:
    level: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"

    @property
    def is_error(self) -> bool:
        return self.level == "error"


def _error(where: str, message: str) -> Issue:
    return Issue("error", where, message)


def _warning(where: str, message: str) -> Issue:
    return Issue("warning", where, message)


def _excerpt(text: str) -> str:
    return f"«{text[:EXCERPT_LENGTH]}…»"


def _body_text(blocks: list[Block]) -> str:
    return " ".join(b.text for b in blocks if b.kind is Kind.PARAGRAPH).lower()


def _is_referenced(body: str, noun_stem: str, number: str) -> bool:
    return re.search(rf"{noun_stem}\w*\s+{re.escape(number)}", body) is not None


def _check_heading(block: Block, previous_level: int) -> list[Issue]:
    issues = []
    if previous_level and block.level > previous_level + 1:
        issues.append(_error(block.source, f"Пропущен уровень заголовка перед «{block.text}»"))
    if block.level == 1 and block.text.strip().lower() == "выводы":
        issues.append(_warning(block.source, "Раздел «Выводы» называется «Заключение»"))
    if block.level == 1 and not block.numbered and block.text.strip().lower().startswith("цель работы"):
        issues.append(_warning(block.source, "Заголовок «Цель работы» нумеруется: «1 Цель работы»"))
    if block.level == 1 and block.numbered and not block.appendix and block.text.upper() in standard.UNNUMBERED_HEADINGS:
        issues.append(_error(block.source, f"Заголовок «{block.text}» не нумеруется: добавьте {{-}}"))
    return issues


def _check_paragraph(block: Block) -> list[Issue]:
    issues = []
    if FIRST_PERSON_RE.search(block.text):
        issues.append(_warning(block.source, f"Личные местоимения: {_excerpt(block.text)}"))
    if "  " in block.text or "---" in block.text:
        issues.append(_warning(block.source, f"Двойной пробел или «---»: {_excerpt(block.text)}"))
    if PLACEHOLDER_RE.search(block.text):
        issues.append(_error(block.source, f"Заглушка в тексте: {_excerpt(block.text)}"))
    if PREPOSITION_BEFORE_UNIT_RE.search(block.text):
        issues.append(_warning(block.source, f"Перед числом с единицей не ставят «в»: {_excerpt(block.text)}"))
    if PERIOD_BEFORE_CITATION_RE.search(block.text):
        issues.append(_warning(block.source, f"Точку ставят после скобки со ссылкой: {_excerpt(block.text)}"))
    if STRAIGHT_QUOTES_RE.search(block.text):
        issues.append(_warning(block.source, f"Прямые кавычки заменяют на «…»: {_excerpt(block.text)}"))
    if has_parenthesis_reference(block.text):
        issues.append(_warning(block.source, f"Ссылку на рисунок или таблицу пишут словами, без «см.» и скобок: {_excerpt(block.text)}"))
    if has_small_digit_numerals(block.text):
        issues.append(_warning(block.source, f"Числа от одного до девяти без единиц измерения пишутся словами: {_excerpt(block.text)}"))
    if has_filler_words(block.text):
        issues.append(_warning(block.source, f"Слова-паразиты («также», «были»): {_excerpt(block.text)}"))
    if LONG_DASH in block.text:
        issues.append(_warning(block.source, f"Длинное тире «—», в тексте используется короткое «–»: {_excerpt(block.text)}"))
    return issues


def _check_figure(block: Block, body: str) -> list[Issue]:
    issues = []
    if not block.caption:
        issues.append(_error(block.source, f"Рисунок {block.number} без подписи"))
    if not _is_referenced(body, "рисунк", block.number):
        issues.append(_warning(block.source, f"Нет ссылки на рисунок {block.number}"))
    return issues


def _check_table(block: Block, body: str) -> list[Issue]:
    issues = []
    if not block.caption:
        issues.append(_error(block.source, "Таблица без заголовка"))
    elif not _is_referenced(body, "таблиц", block.number):
        issues.append(_warning(block.source, f"Нет ссылки на таблицу {block.number}"))
    if len(block.rows) < 2:
        issues.append(_warning(block.source, f"Таблица {block.number} без строк данных"))
    return issues


def _sections(blocks: list[Block]) -> list[tuple[Block, list[Block]]]:
    """Заголовки первого уровня вместе с блоками, которые им принадлежат."""
    sections: list[tuple[Block, list[Block]]] = []
    for block in blocks:
        if block.kind is Kind.HEADING and block.level == 1:
            sections.append((block, []))
        elif sections:
            sections[-1][1].append(block)
    return sections


def _word_count(blocks: list[Block]) -> int:
    return sum(len(b.text.split()) for b in blocks if b.kind is Kind.PARAGRAPH)


def _check_length(heading: Block, content: list[Block]) -> list[Issue]:
    words = _word_count(content)
    title = heading.text.upper()
    if title == "ВВЕДЕНИЕ" and words > INTRODUCTION_MAX_WORDS:
        return [_warning(heading.source, f"Введение около {words} слов: по стандарту не более двух страниц (около {INTRODUCTION_MAX_WORDS} слов)")]
    if title == "ЗАКЛЮЧЕНИЕ" and words > CONCLUSION_MAX_WORDS:
        return [_warning(heading.source, f"Заключение около {words} слов: по стандарту не более двух страниц (около {CONCLUSION_MAX_WORDS} слов)")]
    return []


def _reference_entries(content: list[Block]) -> list[str]:
    return [b.text for b in content if b.kind is Kind.PARAGRAPH]


def _check_references(blocks: list[Block], sections: list[tuple[Block, list[Block]]]) -> list[Issue]:
    issues: list[Issue] = []
    listing = next(((h, c) for h, c in sections if h.text.upper() == "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"), None)
    cited = [int(n) for b in blocks if b.kind is Kind.PARAGRAPH and not (listing and b in listing[1]) for n in CITATION_RE.findall(b.text)]
    first_seen = list(dict.fromkeys(cited))
    if first_seen != sorted(first_seen) or (first_seen and first_seen[0] != 1):
        issues.append(_warning("документ", "Номера источников должны идти в порядке первых ссылок в тексте: [1], [2], [3]…"))
    if listing is None:
        return issues
    heading, content = listing
    entries = _reference_entries(content)
    if any(WIKIPEDIA_RE.search(entry) for entry in entries):
        issues.append(_error(heading.source, "Википедию и подобные открытые ресурсы нельзя использовать как источники"))
    missing = sorted({n for n in cited if n > len(entries)})
    if missing:
        issues.append(_error(heading.source, f"В тексте есть ссылки на источники, которых нет в списке: {missing}"))
    unused = [n for n in range(1, len(entries) + 1) if n not in cited]
    if unused and cited:
        issues.append(_warning(heading.source, f"Источники без ссылок в тексте: {unused}"))
    return issues


def _check_appendices(blocks: list[Block]) -> list[Issue]:
    body = _body_text(blocks)
    return [
        _warning(block.source, f"Нет ссылки на приложение {block.number}")
        for block in blocks
        if block.kind is Kind.HEADING and block.appendix and not re.search(rf"приложени\w*\s+{re.escape(block.number)}", body, re.IGNORECASE)
    ]


def _check_document(blocks: list[Block]) -> list[Issue]:
    sections = _sections(blocks)
    issues: list[Issue] = []
    for heading, content in sections:
        issues += _check_length(heading, content)
    return issues + _check_references(blocks, sections) + _check_appendices(blocks)


def check_blocks(blocks: list[Block]) -> list[Issue]:
    if not blocks:
        return [_error("документ", "В работе нет разделов: сначала выполните write или добавьте файлы в content/")]
    body = _body_text(blocks)
    issues: list[Issue] = []
    previous_level = 0
    for block in blocks:
        if block.kind is Kind.HEADING:
            issues += _check_heading(block, previous_level)
            previous_level = block.level
        elif block.kind is Kind.PARAGRAPH:
            issues += _check_paragraph(block)
        elif block.kind is Kind.FIGURE:
            issues += _check_figure(block, body)
        elif block.kind is Kind.TABLE:
            issues += _check_table(block, body)
    return issues + _check_document(blocks)
