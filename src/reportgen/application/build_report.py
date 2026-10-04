from __future__ import annotations

from pathlib import Path
from typing import Mapping

from reportgen.application.ports import DocumentRenderer, PdfCompiler, ProjectRepository
from reportgen.domain.personal import PersonalProfile, with_personal_data

ALL_FORMATS = ("docx", "tex", "pdf")
OUTPUT_DIR = "output"


class EmptyReportError(RuntimeError):
    pass


def build_report(
    repository: ProjectRepository,
    renderers: Mapping[str, DocumentRenderer],
    pdf_compiler: PdfCompiler,
    formats: tuple[str, ...] = ALL_FORMATS,
    profile: PersonalProfile | None = None,
) -> dict[str, Path]:
    blocks = repository.load_blocks()
    if not blocks:
        raise EmptyReportError("В работе нет разделов: сначала выполните «write» или добавьте файлы в content/")
    meta = with_personal_data(repository.read_meta(), profile)
    output_dir = repository.root / OUTPUT_DIR
    results: dict[str, Path] = {}

    if "docx" in formats:
        results["docx"] = renderers["docx"].render(blocks, meta, repository.root, output_dir / "note.docx")
    if "tex" in formats or "pdf" in formats:
        tex_file = renderers["tex"].render(blocks, meta, repository.root, output_dir / "tex" / "note.tex")
        if "tex" in formats:
            results["tex"] = tex_file
        if "pdf" in formats:
            results["pdf"] = pdf_compiler.compile(tex_file, output_dir / "note.pdf")
    return results
