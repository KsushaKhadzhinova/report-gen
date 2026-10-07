from __future__ import annotations

import re

TABLE_RE = re.compile(r"^Таблица\s+(?P<number>[\dА-Я]+(?:\.\d+)?)\s*[–-]\s*(?P<topic>.+?)\.?\s*$")
FIGURE_RE = re.compile(r"^Рисунок\s+(?P<number>[\dА-Я]+(?:\.\d+)?)\s*[–-]\s*(?P<topic>.+?)\.?\s*$")


def _lower_first(topic: str) -> str:
    """Первая буква строчная, кроме аббревиатур и имён с заглавной второй буквой."""
    if len(topic) > 1 and topic[1].isupper():
        return topic
    return topic[:1].lower() + topic[1:]


def table_sentence(caption: str) -> str | None:
    match = TABLE_RE.match(caption.strip())
    return f"Данные по теме «{_lower_first(match['topic'])}» приведены в таблице {match['number']}." if match else None


def figure_sentence(caption: str) -> str | None:
    match = FIGURE_RE.match(caption.strip())
    return f"Рисунок {match['number']} иллюстрирует тему «{_lower_first(match['topic'])}»." if match else None
