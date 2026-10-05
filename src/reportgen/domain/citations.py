from __future__ import annotations

import re

CITATION_RE = re.compile(r"\[(?P<numbers>\d+(?:\s*[–-]\s*\d+)?(?:\s*,\s*\d+(?:\s*[–-]\s*\d+)?)*)(?P<tail>\s*,[^\]\[]*)?\]")
RANGE_RE = re.compile(r"^(\d+)\s*[–-]\s*(\d+)$")
MIN_RANGE_LENGTH = 3


def parse_numbers(text: str) -> list[int]:
    """«1–3, 7» превращается в [1, 2, 3, 7]."""
    numbers: list[int] = []
    for part in text.split(","):
        part = part.strip()
        span = RANGE_RE.match(part)
        numbers += list(range(int(span.group(1)), int(span.group(2)) + 1)) if span else [int(part)]
    return numbers


def format_numbers(numbers: list[int]) -> str:
    """[5, 6, 7, 9] превращается в «5–7, 9»; два подряд идущих номера пишутся через запятую."""
    unique = sorted(set(numbers))
    groups: list[list[int]] = []
    for number in unique:
        if groups and number == groups[-1][-1] + 1:
            groups[-1].append(number)
        else:
            groups.append([number])
    parts = []
    for group in groups:
        parts.append(f"{group[0]}–{group[-1]}" if len(group) >= MIN_RANGE_LENGTH else ", ".join(str(n) for n in group))
    return ", ".join(parts)


def renumber(text: str, mapping: dict[int, tuple[int, ...]]) -> str:
    """Заменяет номера источников в ссылках по таблице соответствия; ссылка без оставшихся источников удаляется."""

    def replace(match: re.Match) -> str:
        old = parse_numbers(match.group("numbers"))
        new = [n for number in old for n in mapping.get(number, (number,))]
        if not new:
            return ""
        tail = match.group("tail") or ""
        return f"[{format_numbers(new)}{tail if len(set(new)) == 1 else ''}]"

    result = CITATION_RE.sub(replace, text)
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"[ \t]{2,}", " ", result)) if result != text else text
