"""Проверка абзацев после таблиц и рисунков, которые написаны автором по данным объектов.

Запуск: python scripts/check_notes.py <готовые абзацы.json> <данные объектов.json>
Проверяет: все ключи на месте, длина, нет «ё» и длинного тире, нет формальных фраз,
числа и названия в «» взяты из данных объекта.
"""

from __future__ import annotations

import json
import re
import sys

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
FORMAL = ("Данные по теме", "приведены в таблице", "иллюстрирует тему", "Сведения по теме", "систематизирован")
MAX_CHARS = 420
MAX_FREE_COUNT = 10


def object_data(entry: dict) -> str:
    cells = [cell for row in entry.get("rows", []) for cell in row]
    parts = [entry["caption"], entry.get("section", ""), entry.get("text_before", ""), entry.get("reference_sentence", ""), str(entry.get("total_rows", ""))]
    return " ".join(parts + cells)


def problems(entry: dict, text: str) -> list[str]:
    caption = entry["caption"][:40]
    found = []
    if not text:
        return [f"{caption}: пустой текст"]
    if len(text) > MAX_CHARS:
        found.append(f"{caption}: длиннее {MAX_CHARS} знаков")
    if re.search("[ёЁ—]", text):
        found.append(f"{caption}: есть «ё» или длинное тире")
    if "\n" in text or "**" in text:
        found.append(f"{caption}: разметка или перенос строки")
    if any(phrase in text for phrase in FORMAL):
        found.append(f"{caption}: формальная фраза, повторяющая ссылку")
    if re.match(r"^(Таблица|Рисунок)\s", text):
        found.append(f"{caption}: начинается с «Таблица» или «Рисунок»")
    data = object_data(entry)
    for quoted in re.findall(r"«([^»]+)»", text):
        if quoted.lower() not in data.lower():
            found.append(f"{caption}: названия «{quoted}» нет в данных")
    if entry["kind"] == "table":
        rows = entry.get("rows", [])
        counts = {str(entry.get("total_rows", "")), str(max(entry.get("total_rows", 1) - 1, 0)), str(len(rows)), str(max(len(rows) - 1, 0))}
        for number in NUMBER.findall(text):
            normalized = number.replace(",", ".")
            if normalized not in data.replace(",", ".") and normalized not in counts and not (normalized.isdigit() and int(normalized) <= MAX_FREE_COUNT):
                found.append(f"{caption}: число {number} не найдено в данных таблицы")
    return found


def main(notes_path: str, todo_path: str) -> int:
    todo = {entry["key"]: entry for entry in json.load(open(todo_path, encoding="utf-8"))}
    notes = json.load(open(notes_path, encoding="utf-8"))
    errors, seen = [], set()
    for item in notes:
        key, text = item.get("key"), (item.get("text") or "").strip()
        if key not in todo:
            errors.append(f"лишний или искаженный ключ: {str(key)[:60]}")
            continue
        seen.add(key)
        errors += problems(todo[key], text)
    if set(todo) - seen:
        errors.append(f"нет текста для {len(set(todo) - seen)} объектов")
    print("ОК" if not errors else "ОШИБКИ:")
    for error in errors:
        print(" -", error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
