from __future__ import annotations

from dataclasses import dataclass

from reportgen.domain.personal import PLACEHOLDERS

DEFAULT_MINISTRY = "Министерство образования Республики Беларусь"
DEFAULT_UNIVERSITY_LINES = (
    "БЕЛОРУССКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ",
    "ИНФОРМАТИКИ И РАДИОЭЛЕКТРОНИКИ",
)
DEFAULT_DOCUMENT_TYPE = "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА"
DEFAULT_WORK_KIND = "к курсовому проекту"
DEFAULT_CITY = "Минск"
BLANKS_BEFORE_SIGNATURES = 4
BLANKS_BEFORE_FOOTER = 8

CENTER, FIELD, SIGNATURE, BLANK = "center", "field", "signature", "blank"


@dataclass(frozen=True)
class TitleLine:
    """Строка титульного листа: kind задаёт расположение, label и text — содержимое."""

    kind: str
    text: str = ""
    label: str = ""
    bold: bool = False


def _blank(count: int = 1) -> list[TitleLine]:
    return [TitleLine(BLANK)] * count


def build_title_page(meta: dict) -> list[TitleLine]:
    """Состав титульного листа по образцу пояснительных записок БГУИР; личные поля при отсутствии данных заменяются заглушками."""
    value = {key: meta.get(key) or PLACEHOLDERS[key] for key in PLACEHOLDERS}
    lines = [TitleLine(CENTER, meta.get("ministry") or DEFAULT_MINISTRY), *_blank()]
    lines.append(TitleLine(CENTER, "Учреждение образования"))
    lines += [TitleLine(CENTER, line) for line in (meta.get("university_lines") or DEFAULT_UNIVERSITY_LINES)]
    lines += _blank(2)
    lines += [TitleLine(FIELD, value["faculty"], "Факультет"), *_blank()]
    lines += [TitleLine(FIELD, value["department"], "Кафедра"), *_blank()]
    discipline = meta.get("discipline")
    if discipline:
        lines.append(TitleLine(FIELD, discipline, "Дисциплина:"))
    lines += _blank(2)
    lines.append(TitleLine(CENTER, meta.get("document_type") or DEFAULT_DOCUMENT_TYPE))
    lines.append(TitleLine(CENTER, meta.get("work_kind") or DEFAULT_WORK_KIND))
    lines.append(TitleLine(CENTER, "на тему"))
    lines += [*_blank(), TitleLine(CENTER, (meta.get("title") or "<тема работы>").upper(), bold=True)]
    if meta.get("document_code"):
        lines += [*_blank(), TitleLine(CENTER, meta["document_code"])]
    lines += _blank(BLANKS_BEFORE_SIGNATURES)
    if meta.get("group"):
        lines += [TitleLine(SIGNATURE, meta["group"], "Группа:"), *_blank()]
    lines += [TitleLine(SIGNATURE, value["student"], "Студент:"), *_blank(2)]
    lines.append(TitleLine(SIGNATURE, value["supervisor"], "Руководитель:"))
    lines += _blank(BLANKS_BEFORE_FOOTER)
    lines.append(TitleLine(CENTER, f"{meta.get('city') or DEFAULT_CITY} {meta.get('year') or ''}".strip()))
    return lines
