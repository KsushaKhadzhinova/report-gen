from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«\"])")
WORD_RE = re.compile(r"[а-яёa-z\-]+", re.IGNORECASE)
STOP_WORDS = frozenset({"в", "на", "и", "с", "по", "для", "от", "из", "к", "о", "не", "что", "как", "а", "то", "же"})
MIN_SENTENCE_CHARS = 20
MIN_PHRASE_COUNT = 4
MIN_OPENER_WORDS = 3


@dataclass(frozen=True)
class StyleProfile:
    """Числовые признаки авторского стиля. Сами тексты автора в профиле не хранятся."""

    documents: list[str]
    paragraphs: int
    sentences: int
    avg_sentence_words: float
    avg_paragraph_chars: int
    sentence_openers: list[str]
    signature_phrases: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "StyleProfile":
        known = StyleProfile.__dataclass_fields__
        return StyleProfile(**{key: value for key, value in data.items() if key in known})


def _split_sentences(paragraphs: list[str]) -> list[str]:
    sentences = []
    for paragraph in paragraphs:
        sentences += [s for s in SENTENCE_RE.split(paragraph) if len(s) > MIN_SENTENCE_CHARS]
    return sentences


def _openers(sentences: list[str], limit: int = 15) -> list[str]:
    counts = Counter(" ".join(WORD_RE.findall(s)[:2]).lower() for s in sentences if len(WORD_RE.findall(s)) > MIN_OPENER_WORDS)
    return [phrase for phrase, _ in counts.most_common(limit)]


def _signature_phrases(sentences: list[str], limit: int = 25) -> list[str]:
    words = [w.lower() for s in sentences for w in WORD_RE.findall(s)]
    bigrams = Counter(zip(words, words[1:], strict=False))
    content = {" ".join(pair): n for pair, n in bigrams.items() if not (set(pair) & STOP_WORDS) and n >= MIN_PHRASE_COUNT}
    return [phrase for phrase, _ in Counter(content).most_common(limit)]


def build_profile(documents: list[tuple[str, str]]) -> StyleProfile:
    """Строит профиль по парам (имя документа, абзац)."""
    if not documents:
        raise ValueError("Нет связного текста для анализа стиля")
    paragraphs = [text for _, text in documents]
    sentences = _split_sentences(paragraphs)
    lengths = [len(WORD_RE.findall(s)) for s in sentences]
    return StyleProfile(
        documents=sorted({name for name, _ in documents}),
        paragraphs=len(paragraphs),
        sentences=len(sentences),
        avg_sentence_words=round(sum(lengths) / len(lengths), 1),
        avg_paragraph_chars=round(sum(len(p) for p in paragraphs) / len(paragraphs)),
        sentence_openers=_openers(sentences),
        signature_phrases=_signature_phrases(sentences),
    )


def style_hints(profile: StyleProfile | None) -> str:
    """Подсказки о манере автора для запроса к модели; пустая строка, если профиля нет."""
    if profile is None:
        return ""
    parts = [
        f"Манера автора: предложение около {profile.avg_sentence_words} слов, абзац около {profile.avg_paragraph_chars} символов.",
    ]
    if profile.sentence_openers:
        parts.append("Типичные начала предложений: " + "; ".join(profile.sentence_openers[:10]) + ".")
    if profile.signature_phrases:
        parts.append("Характерные обороты: " + "; ".join(profile.signature_phrases[:12]) + ".")
    return " ".join(parts)
