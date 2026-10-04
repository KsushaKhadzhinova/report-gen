from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

DOCKER_IMAGE = "report-gen:latest"
LOG_TAIL_LINES = 25
PASSES = 2


class LatexError(RuntimeError):
    pass


class XelatexCompiler:
    """Собирает PDF локальным xelatex, а при его отсутствии — через образ Docker."""

    def compile(self, tex_file: Path, destination: Path) -> Path:
        command = self._command(tex_file)
        for _ in range(PASSES):
            result = subprocess.run(command, cwd=tex_file.parent, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0:
                raise LatexError("Ошибка компиляции LaTeX:\n" + self._log_tail(tex_file, result.stdout))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tex_file.with_suffix(".pdf"), destination)
        return destination

    @staticmethod
    def _command(tex_file: Path) -> list[str]:
        arguments = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
        if shutil.which("xelatex"):
            return arguments
        if shutil.which("docker"):
            return ["docker", "run", "--rm", "-v", f"{tex_file.parent.resolve()}:/work", "-w", "/work", "--entrypoint", arguments[0], DOCKER_IMAGE, *arguments[1:]]
        raise LatexError("Не найден xelatex и Docker: PDF собрать нельзя. Запустите через Docker (см. README).")

    @staticmethod
    def _log_tail(tex_file: Path, fallback: str) -> str:
        log = tex_file.with_suffix(".log")
        text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else fallback
        return "\n".join(text.splitlines()[-LOG_TAIL_LINES:])
