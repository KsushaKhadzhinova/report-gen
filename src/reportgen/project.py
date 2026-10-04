from __future__ import annotations

from pathlib import Path

import yaml

META_TEMPLATE = {
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

BRIEF_TEMPLATE = """# Сведения о работе

Опишите здесь своими словами всё, что должно попасть в текст: тему, цель, предметную область,
пользователей и роли, основные возможности, использованные технологии, замечания руководителя.
Чем подробнее этот файл, тем точнее получится текст.
"""

SCREENS_TEMPLATE = """# Скриншоты и диаграммы для записки. Запуск: report-gen shots <проект>
# start: python app.py        # команда запуска приложения (необязательно)
# start_wait: 8
items: []
# Примеры:
#  - {kind: web, name: screen_main, url: "http://localhost:8000", caption: "Главная страница"}
#  - {kind: console, name: step1, command: "python main.py --demo", caption: "Результат запуска"}
#  - {kind: desktop, name: screen_work, window: "Название окна", caption: "Главное окно"}
#  - {kind: diagram, name: er, source: diagrams/er.dot, caption: "ER-диаграмма"}
"""


def init(directory: Path, work_type: str = "coursework", title: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    meta = dict(META_TEMPLATE)
    meta["title"] = title
    if work_type == "lab":
        meta.update({"work_type": "ОТЧЁТ ПО ЛАБОРАТОРНОЙ РАБОТЕ", "toc": False})
    files = {
        "meta.yaml": yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        "brief.md": BRIEF_TEMPLATE,
        "sources.txt": "",
        "screens.yaml": SCREENS_TEMPLATE,
    }
    for name, content in files.items():
        path = directory / name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    for sub in ("content", "screenshots", "diagrams", "output"):
        (directory / sub).mkdir(exist_ok=True)
    return directory
