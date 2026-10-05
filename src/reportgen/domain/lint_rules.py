from __future__ import annotations

import re
from dataclasses import dataclass

from reportgen.domain import enterprise_standard as standard
from reportgen.domain.blocks import Block, Kind

FIRST_PERSON_RE = re.compile(r"(?<![а-яё])(я|мы|наш\w*|мой|моя)(?![а-яё])", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"TODO|\[нет файла|\[УТОЧНИТЬ|\?\?|lorem ipsum", re.IGNORECASE)
EXCERPT_LENGTH = 60


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


def check_blocks(blocks: list[Block]) -> list[Issue]:
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
    return issues
