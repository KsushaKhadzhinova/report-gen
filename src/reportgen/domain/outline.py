from __future__ import annotations

import re
from dataclasses import dataclass

from reportgen.domain.structure import Section, Structure

MIN_WORDS, MAX_WORDS = 80, 900
UNNUMBERED_TITLES = ("ВВЕДЕНИЕ", "ЗАКЛЮЧЕНИЕ", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", "ЦЕЛЬ РАБОТЫ", "ВЫВОДЫ")
LEADING_NUMBER_RE = re.compile(r"^\d+(\.\d+)*\.?\s+")
REFERENCES_TITLE = "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"
APPENDIX_PREFIX = "ПРИЛОЖЕНИЕ"
RULES_BY_TITLE = {"ВВЕДЕНИЕ": "introduction", "ЗАКЛЮЧЕНИЕ": "conclusion", "РУКОВОДСТВО ПОЛЬЗОВАТЕЛЯ": "manual"}
RULES_BY_KEYWORD = (("анализ", "analysis"), ("проектирование", "design"), ("разработка", "development"), ("реализация", "development"), ("средств", "development"))


@dataclass
class OutlineEntry:
    title: str
    level: int
    words: int = 0


def _slug(index: int, title: str) -> str:
    latin = re.sub(r"[^a-z0-9]+", "_", title.lower())[:20].strip("_")
    return f"{index:02d}_{latin or 'section'}"


def _rules_for(title: str) -> str:
    upper = title.upper()
    if upper in RULES_BY_TITLE:
        return RULES_BY_TITLE[upper]
    lowered = title.lower()
    return next((rule for keyword, rule in RULES_BY_KEYWORD if keyword in lowered), "")


def structure_from_outline(entries: list[OutlineEntry], name: str = "Структура по образцу") -> Structure:
    """Строит структуру по заголовкам образца; текст образца не используется, только объёмы разделов.

    Список источников заполняется только из файла автора, приложения модель не пишет.
    """
    if not entries:
        raise ValueError("В образце не найдено заголовков")
    sections = []
    for index, entry in enumerate(entries, 1):
        title = LEADING_NUMBER_RE.sub("", entry.title)
        upper = title.upper()
        if upper.startswith(APPENDIX_PREFIX):
            continue
        is_references = upper == REFERENCES_TITLE
        words = max(MIN_WORDS, min(MAX_WORDS, entry.words)) if entry.words > 0 and not is_references else 0
        sections.append(
            Section(
                id=_slug(index, title),
                title=title,
                level=entry.level,
                numbered=upper not in UNNUMBERED_TITLES,
                words=words,
                guide=f"Раскрой тему «{title}» применительно к проекту.",
                kind="references" if is_references else "",
                rules=_rules_for(title),
            )
        )
    return Structure(name, tuple(sections))
