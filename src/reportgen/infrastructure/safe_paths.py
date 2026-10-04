from __future__ import annotations

from pathlib import Path


def resolve_inside(base_dir: Path, relative: str) -> Path | None:
    """Путь внутри base_dir или None, если он выходит за пределы каталога работы."""
    root = base_dir.resolve()
    candidate = (root / relative).resolve()
    return candidate if candidate.is_relative_to(root) and candidate.is_file() else None
