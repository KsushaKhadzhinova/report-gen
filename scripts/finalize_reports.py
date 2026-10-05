"""Пакетная подготовка отчётов: исправление оформления, вёрстка в Word, проверка.

Запуск: python scripts/finalize_reports.py <папка с исходными DOCX> <папка результата>
Исходные файлы не изменяются; для каждого отчёта создаётся подпапка с DOCX и PDF.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "word_finalize.ps1"
DROP_SOURCE = "Отчеты по лабораторным работам"


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return (result.stdout + result.stderr).strip()


def finalize(source: Path, target_dir: Path) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)
    fixed = target_dir / "fixed.docx"
    final_docx = target_dir / f"{target_dir.name}.docx"
    final_pdf = target_dir / f"{target_dir.name}.pdf"
    env_run = ["report-gen", "fix", str(source), "--output", str(fixed), "--drop-source", DROP_SOURCE]
    run(env_run)
    word_report = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), str(fixed), str(final_docx), str(final_pdf)])
    audit = run(["report-gen", "lint", "--docx", str(final_docx)]).splitlines()[-1]
    return f"{source.name}: {word_report.splitlines()[-1] if word_report else 'нет ответа Word'} | аудит: {audit}"


def main() -> int:
    sources = sorted(Path(sys.argv[1]).rglob("*.docx"), key=lambda p: p.stat().st_size)
    destination = Path(sys.argv[2])
    for source in sources:
        started = time.time()
        line = finalize(source, destination / source.stem.replace("ОТЧЕТ_", "").replace("_NotaCode", ""))
        print(f"{line} | {time.time() - started:.0f} с", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
