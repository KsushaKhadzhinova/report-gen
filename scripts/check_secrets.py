"""Блокирует коммит, если в него попали файлы .env или фрагменты, похожие на ключи доступа."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reportgen.domain.redaction import find_tokens  # noqa: E402

ALLOWED_ENV_FILES = {".env.example"}
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")


def staged(*args: str) -> str:
    return subprocess.run(["git", "diff", "--cached", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def forbidden_files(names: list[str]) -> list[str]:
    return [n for n in names if Path(n).name.startswith(".env") and Path(n).name not in ALLOWED_ENV_FILES]


def leaked_locations(diff: str) -> list[str]:
    """Места вида «файл:строка», где добавлен фрагмент, похожий на токен. Сами значения не выводятся."""
    locations: list[str] = []
    path, line_no = "", 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif (hunk := HUNK_RE.match(line)):
            line_no = int(hunk.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            if find_tokens(line[1:]):
                locations.append(f"{path}:{line_no}")
            line_no += 1
    return locations


def main() -> int:
    problems = []
    files = forbidden_files(staged("--name-only").splitlines())
    if files:
        problems.append("Файлы с секретами нельзя коммитить: " + ", ".join(files))
    locations = leaked_locations(staged("-U0"))
    if locations:
        problems.append("Фрагмент, похожий на ключ доступа, найден здесь: " + ", ".join(locations))
    for problem in problems:
        print(f"Коммит остановлен. {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
