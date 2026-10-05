from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FixOptions:
    """Параметры исправления готового документа, которые зависят от конкретного отчёта."""

    drop_sources: tuple[str, ...] = ()
    citation_offset: int = 0
    drop_citations: tuple[int, ...] = ()
