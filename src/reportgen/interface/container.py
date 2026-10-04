from __future__ import annotations

import os
from pathlib import Path

from reportgen.application.write_report import ReportWriter
from reportgen.infrastructure.docx_renderer import DocxRenderer
from reportgen.infrastructure.file_stores import FileStyleStore, FolderReferenceLibrary
from reportgen.infrastructure.llm_client import OpenAICompatibleModel
from reportgen.infrastructure.settings import home
from reportgen.infrastructure.tex_renderer import TexRenderer

REFERENCE_ENV = "REPORTGEN_REFERENCE"
DEFAULT_REFERENCE_DIR = "reference"


def reference_library(explicit: str | None = None) -> FolderReferenceLibrary | None:
    """Каталог эталонных работ: аргумент команды, переменная окружения или workspace/reference."""
    candidate = explicit or os.environ.get(REFERENCE_ENV)
    folder = Path(candidate) if candidate else home() / DEFAULT_REFERENCE_DIR
    return FolderReferenceLibrary(folder) if folder.exists() else None


def renderers() -> dict:
    return {"docx": DocxRenderer(), "tex": TexRenderer()}


def report_writer(explicit_reference: str | None = None) -> ReportWriter:
    return ReportWriter(OpenAICompatibleModel(), FileStyleStore(), reference_library(explicit_reference))
