from __future__ import annotations

import re
from dataclasses import dataclass

from reportgen.domain.structure import Section, Structure

MIN_WORDS, MAX_WORDS = 80, 900
UNNUMBERED_TITLES = ("ВВЕДЕНИЕ", "ЗАКЛЮЧЕНИЕ", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", "ЦЕЛЬ РАБОТЫ", "ВЫВОДЫ")
LEADING_NUMBER_RE = re.compile(r"^\d+(\.\d+)*\.?\s+")


@dataclass
class OutlineEntry:
    title: str
    level: int
    words: int = 0


def _slug(index: int, title: str) -> str:
    latin = re.sub(r"[^a-z0-9]+", "_", title.lower())[:20].strip("_")
    return f"{index:02d}_{latin or 'section'}"


def structure_from_outline(entries: list[OutlineEntry], name: str = "Структура по образцу") -> Structure:
    """Строит структуру по заголовкам образца; текст образца не используется, только объёмы разделов."""
    if not entries:
        raise ValueError("В образце не найдено заголовков")
    sections = []
    for index, entry in enumerate(entries, 1):
        title = LEADING_NUMBER_RE.sub("", entry.title)
        words = max(MIN_WORDS, min(MAX_WORDS, entry.words)) if entry.words > 0 else 0
        sections.append(
            Section(
                id=_slug(index, title),
                title=title,
                level=entry.level,
                numbered=title.upper() not in UNNUMBERED_TITLES,
                words=words,
                guide=f"Раскрой тему «{title}» применительно к проекту.",
            )
        )
    return Structure(name, tuple(sections))
