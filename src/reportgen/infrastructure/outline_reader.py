from __future__ import annotations

import re
from pathlib import Path

from docx import Document

from reportgen.domain.outline import UNNUMBERED_TITLES, OutlineEntry
from reportgen.infrastructure.readers import read_paragraphs

NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,2})\.?\s+(\S.{2,120})$")
MAX_HEADING_CHARS = 140


def read_outline(sample: Path) -> list[OutlineEntry]:
    """Заголовки образца и приблизительный объём текста под каждым."""
    return _from_docx(sample) if sample.suffix.lower() == ".docx" else _from_text(sample)


def _heading_level(style_name: str) -> int:
    last = style_name.split()[-1]
    return int(last) if last.isdigit() else 1


def _from_docx(sample: Path) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []
    for paragraph in Document(str(sample)).paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style.name.startswith("Heading"):
            entries.append(OutlineEntry(text, _heading_level(paragraph.style.name)))
        elif entries:
            entries[-1].words += len(text.split())
    return entries


def _from_text(sample: Path) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []
    for line in read_paragraphs(sample):
        numbered = NUMBERED_HEADING_RE.match(line)
        if numbered and len(line) < MAX_HEADING_CHARS:
            entries.append(OutlineEntry(numbered.group(2), numbered.group(1).count(".") + 1))
        elif line.upper() in UNNUMBERED_TITLES:
            entries.append(OutlineEntry(line.upper(), 1))
        elif entries:
            entries[-1].words += len(line.split())
    return entries
