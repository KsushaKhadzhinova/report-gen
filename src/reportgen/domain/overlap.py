from __future__ import annotations

import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
SHINGLE_SIZE = 5
DEFAULT_THRESHOLD = 0.25

Shingles = frozenset[tuple[str, ...]]


@dataclass(frozen=True)
class Match:
    text: str
    score: float
    source: str


@dataclass(frozen=True)
class ReferenceDocument:
    name: str
    shingles: Shingles


def shingles_of(text: str, size: int = SHINGLE_SIZE) -> Shingles:
    words = [w.lower().replace("ё", "е") for w in WORD_RE.findall(text)]
    return frozenset(tuple(words[i : i + size]) for i in range(len(words) - size + 1))


def index_references(documents: list[tuple[str, str]]) -> list[ReferenceDocument]:
    """Строит индекс шинглов по парам (имя источника, текст абзаца)."""
    return [ReferenceDocument(name, shingles_of(text)) for name, text in documents]


def _best_overlap(own: Shingles, references: list[ReferenceDocument]) -> tuple[float, str]:
    best_score, best_source = 0.0, ""
    for reference in references:
        score = len(own & reference.shingles) / len(own)
        if score > best_score:
            best_score, best_source = score, reference.name
    return best_score, best_source


def find_matches(paragraphs: list[str], references: list[ReferenceDocument], threshold: float = DEFAULT_THRESHOLD) -> list[Match]:
    """Находит абзацы, доля общих шинглов с эталонами которых не ниже порога."""
    matches = []
    for paragraph in paragraphs:
        own = shingles_of(paragraph)
        if not own:
            continue
        score, source = _best_overlap(own, references)
        if score >= threshold:
            matches.append(Match(paragraph, round(score, 2), source))
    return matches


def overall_share(paragraphs: list[str], references: list[ReferenceDocument]) -> float:
    known: set[tuple[str, ...]] = set()
    for reference in references:
        known |= reference.shingles
    total = shared = 0
    for paragraph in paragraphs:
        own = shingles_of(paragraph)
        total += len(own)
        shared += len(own & known)
    return round(shared / total, 3) if total else 0.0
