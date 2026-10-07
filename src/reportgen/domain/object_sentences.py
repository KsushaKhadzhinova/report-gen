from __future__ import annotations

import re

TABLE_RE = re.compile(r"^Таблица\s+(?P<number>[\dА-Я]+(?:\.\d+)?)\s*[–-]\s*(?P<topic>.+?)\.?\s*$")
FIGURE_RE = re.compile(r"^Рисунок\s+(?P<number>[\dА-Я]+(?:\.\d+)?)\s*[–-]\s*(?P<topic>.+?)\.?\s*$")

TABLE_REFERENCES = (
    "Данные по теме «{topic}» приведены в таблице {number}.",
    "Сведения по теме «{topic}» сведены в таблицу {number}.",
    "В таблице {number} представлены данные по теме «{topic}».",
    "Материал по теме «{topic}» систематизирован в таблице {number}.",
)
FIGURE_REFERENCES = (
    "Тема «{topic}» показана на рисунке {number}.",
    "На рисунке {number} наглядно представлена тема «{topic}».",
    "Наглядно тема «{topic}» отражена на рисунке {number}.",
)


PARENTHESIS_TAIL_RE = re.compile(r"\s*\([^()]*\)\s*$")
MIN_TOPIC_CHARS = 8


def clean_topic(topic: str) -> str:
    """Тема для предложения со ссылкой: без пояснения в скобках в конце подписи, если без него тема остаётся осмысленной."""
    shortened = PARENTHESIS_TAIL_RE.sub("", topic)
    return shortened if len(shortened) >= MIN_TOPIC_CHARS else topic


def _lower_first(topic: str) -> str:
    """Первая буква строчная, кроме аббревиатур и имён с заглавной второй буквой."""
    topic = clean_topic(topic)
    if len(topic) > 1 and topic[1].isupper():
        return topic
    return topic[:1].lower() + topic[1:]


def reference_number_pattern(number: str, words: str) -> re.Pattern[str]:
    """Упоминание объекта в тексте: слово («таблица», «рисунок») и рядом его номер, в том числе в перечне «таблицы 3 и 4»."""
    return re.compile(rf"(?:{words})[^.\n]{{0,40}}?(?<![\d.]){re.escape(number)}(?!\d|\.\d)", re.IGNORECASE)


TABLE_WORDS = r"таблиц\w*|табл\."
FIGURE_WORDS = r"рисун\w*|рис\."


def table_reference_sentence(caption: str, variant: int = 0) -> str | None:
    """Предложение со ссылкой на таблицу, которое ставится перед ней; формулировка меняется по номеру объекта."""
    match = TABLE_RE.match(caption.strip())
    if not match:
        return None
    return TABLE_REFERENCES[variant % len(TABLE_REFERENCES)].format(topic=_lower_first(match["topic"]), number=match["number"])


def figure_reference_sentence(caption: str, variant: int = 0) -> str | None:
    match = FIGURE_RE.match(caption.strip())
    if not match:
        return None
    return FIGURE_REFERENCES[variant % len(FIGURE_REFERENCES)].format(topic=_lower_first(match["topic"]), number=match["number"])
