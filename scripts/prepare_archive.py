"""Готовит папку archive/ к коммиту: скрывает фрагменты, похожие на ключи, и убирает пиратский патч.

Запуск из корня репозитория: python scripts/prepare_archive.py
Проверка pre-commit не отключается: скрипт делает файлы чистыми, а хук потом это подтверждает.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reportgen.domain.redaction import find_tokens, redact  # noqa: E402

ARCHIVE = ROOT / "archive"
CRACK_DIR = ARCHIVE / "provided" / "articles" / "MathType v7.4.4.516 Final Eng_Rus"
TEXT_SUFFIXES = {".jsonl", ".json", ".txt", ".md", ".py", ".yaml", ".yml", ".tex", ".csv", ".js", ".html", ".xml"}


def remove_crack() -> None:
    if CRACK_DIR.is_dir():
        shutil.rmtree(CRACK_DIR)
        print(f"Удалена папка с патчем: {CRACK_DIR.name}")


def redact_file(path: Path) -> int:
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except (UnicodeDecodeError, OSError):
        return 0
    cleaned = [redact(line) if find_tokens(line) else line for line in lines]
    changed = sum(1 for before, after in zip(lines, cleaned, strict=True) if before != after)
    if changed:
        path.write_text("\n".join(cleaned), encoding="utf-8", newline="")
    return changed


def remaining(path: Path) -> list[int]:
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except (UnicodeDecodeError, OSError):
        return []
    return [number for number, line in enumerate(lines, 1) if find_tokens(line)]


def main() -> int:
    remove_crack()
    files = [p for p in ARCHIVE.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES]
    hidden = 0
    for path in files:
        count = redact_file(path)
        if count:
            print(f"Скрыто строк: {count} в {path.relative_to(ARCHIVE)}")
            hidden += count
    leftovers = [(p, remaining(p)) for p in files]
    leftovers = [(p, numbers) for p, numbers in leftovers if numbers]
    for path, numbers in leftovers:
        print(f"ОСТАЛОСЬ: {path.relative_to(ARCHIVE)} строки {numbers[:10]}")
    print(f"Итого скрыто строк: {hidden}; осталось подозрительных файлов: {len(leftovers)}")
    return 1 if leftovers else 0


if __name__ == "__main__":
    raise SystemExit(main())
