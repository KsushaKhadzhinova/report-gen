from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from reportgen.readers import prose_paragraphs

WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
SHINGLE_SIZE = 5


@dataclass
class Match:
    text: str
    score: float
    source: str


def shingles(text: str, size: int = SHINGLE_SIZE) -> set[tuple[str, ...]]:
    words = [w.lower().replace("ё", "е") for w in WORD_RE.findall(text)]
    if len(words) < size:
        return set()
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def build_index(reference: Path) -> list[tuple[str, set[tuple[str, ...]]]]:
    return [(name, shingles(text)) for name, text in prose_paragraphs(reference, min_chars=60)]


def scan(paragraphs: list[str], reference: Path, threshold: float = 0.25) -> list[Match]:
    """Находит абзацы, доля общих шинглов с эталонными работами которых выше порога."""
    index = build_index(reference)
    matches: list[Match] = []
    for paragraph in paragraphs:
        own = shingles(paragraph)
        if not own:
            continue
        best_score, best_source = 0.0, ""
        for name, other in index:
            if not other:
                continue
            score = len(own & other) / len(own)
            if score > best_score:
                best_score, best_source = score, name
        if best_score >= threshold:
            matches.append(Match(paragraph, round(best_score, 2), best_source))
    return matches


def overall(paragraphs: list[str], reference: Path) -> float:
    index = build_index(reference)
    union: set[tuple[str, ...]] = set()
    for _, other in index:
        union |= other
    total = shared = 0
    for paragraph in paragraphs:
        own = shingles(paragraph)
        total += len(own)
        shared += len(own & union)
    return round(shared / total, 3) if total else 0.0
