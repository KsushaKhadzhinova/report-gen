from __future__ import annotations

import re
from pathlib import Path

from reportgen.domain.blocks import Block, Kind

APPENDIX_LETTERS = "АБВГДЕЖИКЛМНПРСТУФХЦШЩЭЮЯ"
FIGURE_REFERENCE_RE = re.compile(r"\{fig:([\w\-]+)\}")


class _Counters:
    def __init__(self) -> None:
        self.chapter = self.section = self.subsection = 0
        self.figure = self.table = self.listing = 0
        self.appendix = -1

    def start_chapter(self) -> None:
        self.chapter += 1
        self.section = self.subsection = 0
        self._reset_captions()

    def start_appendix(self) -> None:
        self.appendix += 1
        self.chapter = self.section = self.subsection = 0
        self._reset_captions()

    def _reset_captions(self) -> None:
        self.figure = self.table = self.listing = 0

    @property
    def prefix(self) -> str:
        return APPENDIX_LETTERS[self.appendix] if self.appendix >= 0 and self.chapter == 0 else str(self.chapter)


def _number_heading(block: Block, counters: _Counters) -> None:
    if block.appendix:
        counters.start_appendix()
        block.number = APPENDIX_LETTERS[counters.appendix]
    elif not block.numbered:
        return
    elif block.level == 1:
        counters.start_chapter()
        block.number = str(counters.chapter)
    elif block.level == 2:
        counters.section += 1
        counters.subsection = 0
        block.number = f"{counters.chapter}.{counters.section}"
    else:
        counters.subsection += 1
        block.number = f"{counters.chapter}.{counters.section}.{counters.subsection}"


def assign_numbers(blocks: list[Block]) -> None:
    """Расставляет номера разделов, рисунков, таблиц и листингов по правилам СТП."""
    counters = _Counters()
    for block in blocks:
        if block.kind is Kind.HEADING:
            _number_heading(block, counters)
        elif block.kind is Kind.FIGURE:
            counters.figure += 1
            block.number = f"{counters.prefix}.{counters.figure}"
        elif block.kind is Kind.TABLE and block.caption:
            counters.table += 1
            block.number = f"{counters.prefix}.{counters.table}"
        elif block.kind is Kind.CODE and block.caption:
            counters.listing += 1
            block.number = f"{counters.prefix}.{counters.listing}"


def resolve_figure_references(blocks: list[Block]) -> None:
    """Заменяет метки {fig:имя} номерами рисунков."""
    numbers = {Path(b.path).stem: b.number for b in blocks if b.kind is Kind.FIGURE}

    def replace(text: str) -> str:
        return FIGURE_REFERENCE_RE.sub(lambda m: numbers.get(m.group(1), "??"), text)

    for block in blocks:
        if block.kind is Kind.PARAGRAPH:
            block.text = replace(block.text)
        elif block.kind is Kind.LIST:
            block.items = [replace(item) for item in block.items]
