from __future__ import annotations

import json
from pathlib import Path

import yaml

from reportgen.domain.blocks import Block
from reportgen.domain.markup import parse
from reportgen.domain.numbering import assign_numbers, resolve_figure_references

STATE_DIR = ".reportgen"
CACHE_FILE = "cache.json"


class FileProjectRepository:
    """Папка одной работы на диске."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    @property
    def content_dir(self) -> Path:
        return self._root / "content"

    def read_meta(self) -> dict:
        meta_file = self._root / "meta.yaml"
        if not meta_file.is_file():
            raise FileNotFoundError(f"Не найден {meta_file}. Выполните «report-gen init».")
        return yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}

    def read_brief(self) -> str:
        return self._read_text("brief.md")

    def read_sources(self) -> list[str] | None:
        path = self._root / "sources.txt"
        if not path.is_file():
            return None
        entries = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return entries or None

    def figure_captions(self) -> dict[str, str]:
        index = self._root / "screenshots" / "index.yaml"
        if not index.is_file():
            return {}
        items = yaml.safe_load(index.read_text(encoding="utf-8")) or []
        return {Path(item["file"]).stem: item["caption"] for item in items if item.get("ok")}

    def section_exists(self, section_id: str) -> bool:
        return self._section_path(section_id).is_file()

    def save_section(self, section_id: str, markdown: str) -> None:
        self.content_dir.mkdir(exist_ok=True)
        self._section_path(section_id).write_text(markdown, encoding="utf-8")

    def cached_fingerprint(self, section_id: str) -> str | None:
        return self._read_cache().get(section_id)

    def store_fingerprint(self, section_id: str, fingerprint: str) -> None:
        cache = self._read_cache()
        cache[section_id] = fingerprint
        cache_path = self._cache_path()
        cache_path.parent.mkdir(exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_blocks(self) -> list[Block]:
        blocks: list[Block] = []
        for path in sorted(self.content_dir.glob("*.md")):
            blocks += parse(path.read_text(encoding="utf-8"), source=path.name)
        assign_numbers(blocks)
        resolve_figure_references(blocks)
        return blocks

    def custom_structure_path(self) -> Path:
        return self._root / "structure.yaml"

    def _section_path(self, section_id: str) -> Path:
        return self.content_dir / f"{section_id}.md"

    def _cache_path(self) -> Path:
        return self._root / STATE_DIR / CACHE_FILE

    def _read_cache(self) -> dict[str, str]:
        path = self._cache_path()
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    def _read_text(self, name: str, limit: int = 3500) -> str:
        path = self._root / name
        return path.read_text(encoding="utf-8")[:limit] if path.is_file() else ""
