from __future__ import annotations

from pathlib import Path
from typing import Protocol

from reportgen.domain.blocks import Block
from reportgen.domain.lint_rules import Issue
from reportgen.domain.overlap import ReferenceDocument
from reportgen.domain.style_profile import StyleProfile


class LanguageModel(Protocol):
    @property
    def identity(self) -> str:
        """Строка, меняющаяся при смене провайдера или моделей; входит в отпечаток кеша."""

    def complete(self, role: str, system: str, user: str, temperature: float = 0.6, max_tokens: int | None = None) -> str: ...


class DocumentRenderer(Protocol):
    def render(self, blocks: list[Block], meta: dict, base_dir: Path, output: Path) -> Path: ...


class PdfCompiler(Protocol):
    def compile(self, tex_file: Path, destination: Path) -> Path: ...


class StyleStore(Protocol):
    def load(self) -> StyleProfile | None: ...

    def save(self, profile: StyleProfile) -> None: ...


class ProseSource(Protocol):
    def paragraphs(self, location: Path) -> list[tuple[str, str]]:
        """Связные абзацы документов по пути: пары (имя документа, текст)."""


class CodeInspector(Protocol):
    def summarize(self, code_dir: Path) -> str: ...


class ProjectRepository(Protocol):
    """Папка одной работы: сведения, разделы, скриншоты, кеш генерации."""

    @property
    def root(self) -> Path: ...

    def read_meta(self) -> dict: ...

    def read_brief(self) -> str: ...

    def read_sources(self) -> list[str] | None: ...

    def figure_captions(self) -> dict[str, str]: ...

    def read_section(self, section_id: str) -> str: ...

    def save_section(self, section_id: str, markdown: str) -> None: ...

    def section_exists(self, section_id: str) -> bool: ...

    def cached_fingerprint(self, section_id: str) -> str | None: ...

    def store_fingerprint(self, section_id: str, fingerprint: str) -> None: ...

    def load_blocks(self) -> list[Block]: ...


class ScreenshotTaker(Protocol):
    def take(self, item: dict, target: Path, project_root: Path) -> None: ...


class ReferenceLibrary(Protocol):
    def documents(self) -> list[ReferenceDocument]: ...


class EditableText(Protocol):
    def paragraphs(self) -> list[str]: ...

    def replace(self, old: str, new: str) -> None: ...

    def save(self) -> None: ...


class FormatService(Protocol):
    def audit(self, path: Path) -> list[Issue]: ...

    def fix(self, source: Path, output: Path, drop_sources: tuple[str, ...] = ()) -> int: ...

    def open_text(self, path: Path) -> EditableText: ...


class StandardSource(Protocol):
    def excerpts(self, query: str, limit: int = 4) -> list[str]:
        """Выдержки из пунктов стандарта, наиболее подходящие к запросу."""
