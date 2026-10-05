from __future__ import annotations

import json
from pathlib import Path

from reportgen.domain.standard_index import StandardIndex, excerpt, parse_clauses
from reportgen.infrastructure.settings import home

INDEX_FILE = "standard_index.json"


def _pdf_pages(pdf: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(str(pdf)) as document:
        return [page.get_text() for page in document]


class FileStandardStore:
    """Локальный индекс текста стандарта автора. Лежит в рабочей папке и в git не попадает."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or home() / INDEX_FILE

    def ingest(self, pdf: Path) -> StandardIndex:
        index = parse_clauses(_pdf_pages(pdf))
        self.path.write_text(json.dumps(index.to_dict(), ensure_ascii=False), encoding="utf-8")
        return index

    def load(self) -> StandardIndex | None:
        if not self.path.is_file():
            return None
        return StandardIndex.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def source(self) -> "IndexedStandard | None":
        index = self.load()
        return IndexedStandard(index) if index else None


class IndexedStandard:
    """Реализация порта StandardSource поверх локального индекса."""

    def __init__(self, index: StandardIndex) -> None:
        self.index = index

    def excerpts(self, query: str, limit: int = 4) -> list[str]:
        return [excerpt(clause) for clause in self.index.search(query, limit)]
