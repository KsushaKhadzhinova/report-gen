"""Пакетная подготовка отчётов: исправление оформления, вёрстка в Word, проверка.

Запуск: python scripts/finalize_reports.py <папка с исходными DOCX> <папка результата> [--force] [--only ЛР4,ЛР5]
Исходные файлы не изменяются; для каждого отчёта создаётся подпапка с DOCX и PDF.
Уже готовые отчёты пропускаются, если не указан --force; сбой одного отчёта не останавливает остальные.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "word_finalize.ps1"
DROP_SOURCE = "Отчеты по лабораторным работам"
EXTRA_OPTIONS = {"ЛР5": ["--citation-offset", "3", "--drop-citation", "1", "--drop-citation", "2", "--drop-citation", "3"]}


def run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return (result.stdout + result.stderr).strip()


def last_line(text: str, default: str) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else default


def finalize(source: Path, target_dir: Path) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)
    fixed = target_dir / "fixed.docx"
    final_docx = target_dir / f"{target_dir.name}.docx"
    final_pdf = target_dir / f"{target_dir.name}.pdf"
    run(["report-gen", "fix", str(source), "--output", str(fixed), "--drop-source", DROP_SOURCE, *EXTRA_OPTIONS.get(target_dir.name, [])])
    word_report = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), str(fixed), str(final_docx), str(final_pdf)])
    if not final_docx.is_file() or not final_pdf.is_file():
        return f"{source.name}: ОШИБКА Word | {last_line(word_report, 'нет ответа')[:300]}"
    audit = last_line(run(["report-gen", "lint", "--docx", str(final_docx)]), "аудит не выдал результата")
    return f"{source.name}: {last_line(word_report, 'нет ответа Word')} | аудит: {audit}"


def main() -> int:
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else []
    arguments = [a for a in sys.argv[1:] if not a.startswith("--") and a not in only]
    force = "--force" in sys.argv
    sources = sorted(Path(arguments[0]).rglob("*.docx"), key=lambda p: p.stat().st_size)
    if only:
        sources = [source for source in sources if any(token in source.stem for token in only)]
    destination = Path(arguments[1])
    for source in sources:
        name = source.stem.replace("ОТЧЕТ_", "").replace("_NotaCode", "")
        target = destination / name
        if not force and (target / f"{name}.docx").is_file() and (target / f"{name}.pdf").is_file():
            print(f"{source.name}: уже готов, пропущен", flush=True)
            continue
        started = time.time()
        print(f"{finalize(source, target)} | {time.time() - started:.0f} с", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
