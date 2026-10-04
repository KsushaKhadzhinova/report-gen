from __future__ import annotations

from pathlib import Path

import yaml

WORK_FOLDERS = ("content", "screenshots", "diagrams", "output")

META_DEFAULTS = {
    "ministry": "Министерство образования Республики Беларусь",
    "university": "Учреждение образования «Белорусский государственный университет информатики и радиоэлектроники»",
    "faculty": "",
    "department": "",
    "work_type": "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА",
    "discipline": "",
    "title": "",
    "student": "",
    "group": "",
    "supervisor": "",
    "city": "Минск",
    "year": "",
    "title_page": True,
    "toc": True,
}
LAB_OVERRIDES = {"work_type": "ОТЧЁТ ПО ЛАБОРАТОРНОЙ РАБОТЕ", "toc": False}

BRIEF_TEMPLATE = """# Сведения о работе

Опишите здесь своими словами всё, что должно попасть в текст: тему, цель, предметную область,
пользователей и роли, основные возможности, использованные технологии, замечания руководителя.
Чем подробнее этот файл, тем точнее получится текст.
"""

SCREENS_TEMPLATE = """# План скриншотов и диаграмм. Запуск: report-gen shots <работа>
# start: python app.py        # команда запуска приложения (необязательно)
# start_wait: 8
items: []
# Примеры:
#  - {kind: web, name: screen_main, url: "http://localhost:8000", caption: "Главная страница"}
#  - {kind: console, name: step1, command: "python main.py --demo", caption: "Результат запуска"}
#  - {kind: desktop, name: screen_work, window: "Название окна", caption: "Главное окно"}
#  - {kind: diagram, name: er, source: diagrams/er.dot, caption: "ER-диаграмма"}
"""


def scaffold_project(directory: Path, lab: bool = False, title: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    meta = {**META_DEFAULTS, "title": title, **(LAB_OVERRIDES if lab else {})}
    files = {
        "meta.yaml": yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        "brief.md": BRIEF_TEMPLATE,
        "sources.txt": "",
        "screens.yaml": SCREENS_TEMPLATE,
    }
    for name, content in files.items():
        target = directory / name
        if not target.exists():
            target.write_text(content, encoding="utf-8")
    for folder in WORK_FOLDERS:
        (directory / folder).mkdir(exist_ok=True)
    return directory
