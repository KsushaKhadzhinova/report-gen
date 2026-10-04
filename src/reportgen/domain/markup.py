from __future__ import annotations

import re

from reportgen.domain.blocks import Block, Kind

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*?)(?:\s+\{(-|app)\})?\s*$")
FIGURE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
TABLE_CAPTION_RE = re.compile(r"^Таблица:\s*(.+)$")
TABLE_SEPARATOR_RE = re.compile(r":?-{2,}:?")
LIST_RE = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")
CODE_FENCE = "```"


class _Parser:
    def __init__(self, text: str, source: str) -> None:
        self.lines = text.splitlines()
        self.source = source
        self.position = 0
        self.blocks: list[Block] = []
        self.paragraph: list[str] = []
        self.pending_caption = ""

    def run(self) -> list[Block]:
        while self.position < len(self.lines):
            self._consume_line()
        self._flush_paragraph()
        return self.blocks

    def _consume_line(self) -> None:
        line = self.lines[self.position]
        stripped = line.strip()
        handlers = (
            (lambda: not stripped, self._blank),
            (lambda: stripped.startswith(CODE_FENCE), self._code),
            (lambda: HEADING_RE.match(stripped), self._heading),
            (lambda: FIGURE_RE.match(stripped), self._figure),
            (lambda: TABLE_CAPTION_RE.match(stripped), self._table_caption),
            (lambda: stripped.startswith("|"), self._table),
            (lambda: LIST_RE.match(line), self._list),
        )
        for matches, handle in handlers:
            if matches():
                handle()
                return
        self.paragraph.append(line)
        self.position += 1

    def _flush_paragraph(self) -> None:
        if self.paragraph:
            text = " ".join(part.strip() for part in self.paragraph)
            self.blocks.append(Block(Kind.PARAGRAPH, text=text, source=self.source))
            self.paragraph.clear()

    def _blank(self) -> None:
        self._flush_paragraph()
        self.position += 1

    def _heading(self) -> None:
        self._flush_paragraph()
        marks, title, flag = HEADING_RE.match(self.lines[self.position].strip()).groups()
        self.blocks.append(
            Block(Kind.HEADING, text=title, level=len(marks), numbered=flag is None, appendix=flag == "app", source=self.source)
        )
        self.position += 1

    def _figure(self) -> None:
        self._flush_paragraph()
        caption, path = FIGURE_RE.match(self.lines[self.position].strip()).groups()
        self.blocks.append(Block(Kind.FIGURE, caption=caption, path=path, source=self.source))
        self.position += 1

    def _table_caption(self) -> None:
        self._flush_paragraph()
        self.pending_caption = TABLE_CAPTION_RE.match(self.lines[self.position].strip()).group(1)
        self.position += 1

    def _take_caption(self) -> str:
        caption, self.pending_caption = self.pending_caption, ""
        return caption

    def _code(self) -> None:
        self._flush_paragraph()
        self.position += 1
        code: list[str] = []
        while self.position < len(self.lines) and not self.lines[self.position].strip().startswith(CODE_FENCE):
            code.append(self.lines[self.position])
            self.position += 1
        self.position += 1
        self.blocks.append(Block(Kind.CODE, text="\n".join(code), caption=self._take_caption(), source=self.source))

    def _table(self) -> None:
        self._flush_paragraph()
        rows: list[list[str]] = []
        while self.position < len(self.lines) and self.lines[self.position].strip().startswith("|"):
            cells = [cell.strip() for cell in self.lines[self.position].strip().strip("|").split("|")]
            if not all(TABLE_SEPARATOR_RE.fullmatch(cell) for cell in cells):
                rows.append(cells)
            self.position += 1
        self.blocks.append(Block(Kind.TABLE, caption=self._take_caption(), rows=rows, source=self.source))

    def _list(self) -> None:
        self._flush_paragraph()
        ordered = LIST_RE.match(self.lines[self.position]).group(2)[0].isdigit()
        items: list[str] = []
        while self.position < len(self.lines) and LIST_RE.match(self.lines[self.position]):
            items.append(LIST_RE.match(self.lines[self.position]).group(3).strip())
            self.position += 1
        self.blocks.append(Block(Kind.LIST, items=items, ordered=ordered, source=self.source))


def parse(markdown: str, source: str = "") -> list[Block]:
    return _Parser(markdown, source).run()
