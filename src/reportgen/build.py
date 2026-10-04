from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from reportgen import render_docx, render_tex
from reportgen.document import load_sections

DOCKER_IMAGE = "report-gen:latest"


class BuildError(RuntimeError):
    pass


def load_meta(project: Path) -> dict:
    meta_file = project / "meta.yaml"
    if not meta_file.is_file():
        raise BuildError(f"Не найден {meta_file}. Выполните «report-gen init».")
    return yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}


def _latex_command(tex: Path) -> list[str]:
    args = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name]
    if shutil.which("xelatex"):
        return args
    if shutil.which("docker"):
        return ["docker", "run", "--rm", "-v", f"{tex.parent.resolve()}:/work", "-w", "/work", DOCKER_IMAGE, *args]
    raise BuildError("Не найден xelatex и Docker: PDF собрать нельзя. Запустите через Docker (см. README).")


def compile_pdf(tex: Path) -> Path:
    command = _latex_command(tex)
    for _ in range(2):
        result = subprocess.run(command, cwd=tex.parent, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            log = (tex.with_suffix(".log")).read_text(encoding="utf-8", errors="replace") if tex.with_suffix(".log").exists() else result.stdout
            tail = "\n".join(log.splitlines()[-25:])
            raise BuildError(f"Ошибка компиляции LaTeX:\n{tail}")
    return tex.with_suffix(".pdf")


def build(project: Path, formats: tuple[str, ...] = ("docx", "tex", "pdf")) -> dict[str, Path]:
    meta = load_meta(project)
    blocks = load_sections(project / "content")
    if not blocks:
        raise BuildError(f"В {project / 'content'} нет разделов (*.md)")
    out = project / "output"
    out.mkdir(exist_ok=True)
    results: dict[str, Path] = {}
    base = project

    if "docx" in formats:
        results["docx"] = render_docx.render(blocks, meta, base, out / "note.docx")
    if "tex" in formats or "pdf" in formats:
        tex = render_tex.render(blocks, meta, base, out / "tex")
        if "tex" in formats:
            results["tex"] = tex
        if "pdf" in formats:
            pdf = compile_pdf(tex)
            final = out / "note.pdf"
            shutil.copyfile(pdf, final)
            results["pdf"] = final
    return results
