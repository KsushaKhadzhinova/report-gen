from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import asdict, dataclass

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«\"])")
WORD_RE = re.compile(r"[а-яёa-z\-]+", re.IGNORECASE)
STOP_WORDS = frozenset({"в", "на", "и", "с", "по", "для", "от", "из", "к", "о", "не", "что", "как", "а", "то", "же"})
MIN_SENTENCE_CHARS = 20
MIN_PHRASE_COUNT = 4
EXEMPLAR_LENGTH = (250, 900)

BASE_INSTRUCTION = (
    "Пиши на русском языке в научно-техническом стиле для пояснительной записки по СТП БГУИР. "
    "Без личных местоимений («я», «мы»), без разговорных оборотов, без списков с жирным шрифтом. "
    "Числа до десяти пиши словами. Не выдумывай факты, источники и цифры: опирайся только на предоставленные сведения."
)


@dataclass(frozen=True)
class StyleProfile:
    documents: list[str]
    paragraphs: int
    sentences: int
    avg_sentence_words: float
    avg_paragraph_chars: int
    sentence_openers: list[str]
    signature_phrases: list[str]
    exemplars: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "StyleProfile":
        return StyleProfile(**data)


def _split_sentences(paragraphs: list[str]) -> list[str]:
    sentences = []
    for paragraph in paragraphs:
        sentences += [s for s in SENTENCE_RE.split(paragraph) if len(s) > MIN_SENTENCE_CHARS]
    return sentences


def _openers(sentences: list[str], limit: int = 15) -> list[str]:
    counts = Counter(" ".join(WORD_RE.findall(s)[:2]).lower() for s in sentences if len(WORD_RE.findall(s)) > 3)
    return [phrase for phrase, _ in counts.most_common(limit)]


def _signature_phrases(sentences: list[str], limit: int = 25) -> list[str]:
    words = [w.lower() for s in sentences for w in WORD_RE.findall(s)]
    bigrams = Counter(zip(words, words[1:]))
    content = {" ".join(pair): n for pair, n in bigrams.items() if not (set(pair) & STOP_WORDS) and n >= MIN_PHRASE_COUNT}
    return [phrase for phrase, _ in Counter(content).most_common(limit)]


def _pick_exemplars(paragraphs: list[str], count: int, seed: int) -> list[str]:
    low, high = EXEMPLAR_LENGTH
    pool = [p for p in paragraphs if low <= len(p) <= high]
    random.Random(seed).shuffle(pool)
    return pool[:count]


def build_profile(documents: list[tuple[str, str]], exemplar_count: int = 6, seed: int = 7) -> StyleProfile:
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
        exemplars=_pick_exemplars(paragraphs, exemplar_count, seed),
    )


def style_instruction(profile: StyleProfile | None) -> str:
    if profile is None:
        return BASE_INSTRUCTION
    parts = [
        BASE_INSTRUCTION,
        f"Средняя длина предложения автора — около {profile.avg_sentence_words} слов, "
        f"абзаца — около {profile.avg_paragraph_chars} символов.",
    ]
    if profile.sentence_openers:
        parts.append("Типичные начала предложений автора: " + "; ".join(profile.sentence_openers[:10]) + ".")
    if profile.signature_phrases:
        parts.append("Характерные обороты автора: " + "; ".join(profile.signature_phrases[:12]) + ".")
    if profile.exemplars:
        samples = "\n\n".join(f"Образец {i}:\n{text}" for i, text in enumerate(profile.exemplars[:3], 1))
        parts.append("Перенимай манеру изложения, но не копируй формулировки из образцов.\n\n" + samples)
    return "\n\n".join(parts)
