from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode", "target", "bin", "obj"}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
    ".java": "Java", ".kt": "Kotlin", ".cs": "C#", ".cpp": "C++", ".c": "C", ".h": "C/C++", ".go": "Go",
    ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".vue": "Vue",
}
MANIFESTS = {
    "requirements.txt": "pip", "pyproject.toml": "Python project", "package.json": "npm", "pom.xml": "Maven",
    "build.gradle": "Gradle", "Cargo.toml": "Cargo", "go.mod": "Go modules", "composer.json": "Composer",
    "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose",
}
ENTRY_HINTS = ("main.", "app.", "index.", "manage.py", "server.", "program.")
SQL_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"\[]?(\w+)", re.IGNORECASE)
ROUTE_RE = re.compile(r"""@\w+\.(get|post|put|delete|patch|route)\(\s*['"]([^'"]+)""", re.IGNORECASE)


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and not any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            yield path


def analyze(root: Path, max_listing_files: int = 12) -> dict:
    """Собирает сведения о проекте: языки, зависимости, модули, таблицы БД, маршруты."""
    languages: Counter = Counter()
    manifests: list[str] = []
    tables: set[str] = set()
    routes: list[str] = []
    entry_points: list[str] = []
    modules: Counter = Counter()
    dependencies: list[str] = []
    largest: list[tuple[int, str]] = []

    for path in iter_files(root):
        relative = path.relative_to(root).as_posix()
        if path.name in MANIFESTS:
            manifests.append(f"{relative} ({MANIFESTS[path.name]})")
            if path.name == "requirements.txt":
                dependencies += [l.split("==")[0].split(">=")[0].strip() for l in path.read_text(errors="ignore").splitlines() if l.strip() and not l.startswith("#")]
            elif path.name == "package.json":
                try:
                    data = json.loads(path.read_text(errors="ignore"))
                    dependencies += list(data.get("dependencies", {}))
                except json.JSONDecodeError:
                    pass
        language = LANGUAGES.get(path.suffix.lower())
        if not language:
            continue
        languages[language] += 1
        modules[path.parent.relative_to(root).as_posix() or "."] += 1
        if path.name.lower().startswith(ENTRY_HINTS):
            entry_points.append(relative)
        text = path.read_text(errors="ignore")
        largest.append((len(text), relative))
        tables.update(SQL_TABLE_RE.findall(text))
        routes += [f"{m.upper()} {p}" for m, p in ROUTE_RE.findall(text)]

    largest.sort(reverse=True)
    return {
        "name": root.name,
        "languages": dict(languages.most_common()),
        "manifests": manifests,
        "dependencies": sorted(set(dependencies)),
        "modules": dict(modules.most_common(15)),
        "entry_points": entry_points[:10],
        "database_tables": sorted(tables),
        "routes": routes[:30],
        "key_files": [name for _, name in largest[:max_listing_files]],
    }


def summary_text(info: dict) -> str:
    lines = [f"Проект: {info['name']}"]
    if info["languages"]:
        lines.append("Языки: " + ", ".join(f"{k} ({v} файл.)" for k, v in info["languages"].items()))
    if info["dependencies"]:
        lines.append("Зависимости: " + ", ".join(info["dependencies"][:25]))
    if info["manifests"]:
        lines.append("Конфигурация сборки: " + ", ".join(info["manifests"]))
    if info["modules"]:
        lines.append("Каталоги с кодом: " + ", ".join(f"{k} ({v})" for k, v in info["modules"].items()))
    if info["entry_points"]:
        lines.append("Точки входа: " + ", ".join(info["entry_points"]))
    if info["database_tables"]:
        lines.append("Таблицы БД: " + ", ".join(info["database_tables"]))
    if info["routes"]:
        lines.append("Маршруты API: " + ", ".join(info["routes"]))
    return "\n".join(lines)


class ProjectCodeInspector:
    """Реализация порта CodeInspector: краткое описание проекта по его файлам."""

    def summarize(self, code_dir: Path) -> str:
        return summary_text(analyze(code_dir))
