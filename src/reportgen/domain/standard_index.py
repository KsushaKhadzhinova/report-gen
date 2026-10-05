from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass

CLAUSE_START_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,4})\s+(?=[А-ЯЁA-Zа-яё«\"(])")
LEADER_RE = re.compile(r"\.{4,}|…{2,}")
WORD_RE = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
STEM_LENGTH = 5
MIN_CLAUSE_CHARS = 40
MAX_EXCERPT_CHARS = 700
NORMATIVE_CHAPTERS = 3
BM25_K1 = 1.5
BM25_B = 0.75
STOP_STEMS = frozenset({"и", "в", "на", "по", "для", "что", "как", "это", "или", "при", "от", "из", "не", "с", "к", "а", "о"})


@dataclass(frozen=True)
class Clause:
    number: str
    text: str


@dataclass(frozen=True)
class StandardIndex:
    clauses: tuple[Clause, ...]

    def to_dict(self) -> dict:
        return {"clauses": [asdict(c) for c in self.clauses]}

    @staticmethod
    def from_dict(data: dict) -> "StandardIndex":
        return StandardIndex(tuple(Clause(**item) for item in data["clauses"]))

    def search(self, query: str, limit: int = 4) -> list[Clause]:
        """Пункты, наиболее подходящие к запросу (BM25 по основам слов: редкие слова весят больше, длинные пункты не перевешивают)."""
        wanted = set(_stems(query))
        if not wanted or not self.clauses:
            return []
        stems_per_clause = [Counter(_stems(clause.text)) for clause in self.clauses]
        total = len(self.clauses)
        average_length = sum(sum(counts.values()) for counts in stems_per_clause) / total
        frequency = Counter(stem for counts in stems_per_clause for stem in counts)
        scored = []
        for clause, counts in zip(self.clauses, stems_per_clause, strict=True):
            length = sum(counts.values())
            score = 0.0
            for stem in wanted & counts.keys():
                idf = math.log(1 + (total - frequency[stem] + 0.5) / (frequency[stem] + 0.5))
                tf = counts[stem]
                score += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * length / average_length))
            if score > 0:
                scored.append((score, clause))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [clause for _, clause in scored[:limit]]


def _stems(text: str) -> list[str]:
    stems = (word.lower().replace("ё", "е")[:STEM_LENGTH] for word in WORD_RE.findall(text))
    return [stem for stem in stems if stem not in STOP_STEMS and len(stem) > 1]


def _is_contents_line(line: str) -> bool:
    return LEADER_RE.search(line) is not None


def parse_clauses(pages: list[str]) -> StandardIndex:
    """Разбивает текст стандарта на пункты по номерам вида 2.3.12; строки оглавления пропускает."""
    clauses: list[Clause] = []
    number, buffer = "", []

    def flush() -> None:
        text = re.sub(r"\s+", " ", " ".join(buffer)).strip()
        if number and len(text) >= MIN_CLAUSE_CHARS:
            clauses.append(Clause(number, text))

    for page in pages:
        for raw in page.splitlines():
            line = raw.strip()
            if not line or _is_contents_line(line) or line.isdigit():
                continue
            match = CLAUSE_START_RE.match(line)
            if match:
                flush()
                number, buffer = match.group(1), [line[match.end():]]
                if int(number.split(".")[0]) > NORMATIVE_CHAPTERS:
                    number = ""
            elif number:
                buffer.append(line)
    flush()
    return StandardIndex(tuple(clauses))


def excerpt(clause: Clause) -> str:
    text = clause.text if len(clause.text) <= MAX_EXCERPT_CHARS else clause.text[:MAX_EXCERPT_CHARS].rsplit(" ", 1)[0] + "…"
    return f"п. {clause.number}: {text}"
