"""Блокирует коммит, если в него попали файлы .env или фрагменты, похожие на ключи доступа.

Без аргументов проверяет добавленные в индекс изменения (pre-commit); с ключом --all проверяет все отслеживаемые файлы (CI).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reportgen.domain.redaction import find_tokens  # noqa: E402

ALLOWED_ENV_FILES = {".env.example"}
PERSONAL_FILES = {"profile.enc", "profile.yaml", "unlock.txt", "style_profile.json"}
HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
    return result.stdout


def forbidden_files(names: list[str]) -> list[str]:
    forbidden = []
    for name in names:
        base = Path(name).name
        if (base.startswith(".env") and base not in ALLOWED_ENV_FILES) or base in PERSONAL_FILES:
            forbidden.append(name)
    return forbidden


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


def tracked_locations() -> list[str]:
    locations: list[str] = []
    for name in git("ls-files").splitlines():
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        locations += [f"{name}:{number}" for number, line in enumerate(lines, 1) if find_tokens(line)]
    return locations


def main() -> int:
    scan_all = "--all" in sys.argv[1:]
    names = git("ls-files").splitlines() if scan_all else git("diff", "--cached", "--name-only").splitlines()
    locations = tracked_locations() if scan_all else leaked_locations(git("diff", "--cached", "-U0"))
    problems = []
    if forbidden_files(names):
        problems.append("Личные файлы и файлы с секретами нельзя коммитить: " + ", ".join(forbidden_files(names)))
    if locations:
        problems.append("Фрагмент, похожий на ключ доступа, найден здесь: " + ", ".join(locations))
    for problem in problems:
        print(f"Проверка не пройдена. {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
