from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*?)(?:\s+\{(-|app)\})?\s*$")
FIGURE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
TABLE_CAPTION_RE = re.compile(r"^Таблица:\s*(.+)$")
LIST_RE = re.compile(r"^(\s*)([-*]|\d+[.)])\s+(.*)$")


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    number: str = ""
    numbered: bool = True
    appendix: bool = False
    path: str = ""
    caption: str = ""
    rows: list[list[str]] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    ordered: bool = False
    source: str = ""


def parse(markdown: str, source: str = "") -> list[Block]:
    lines = markdown.splitlines()
    blocks: list[Block] = []
    paragraph: list[str] = []
    pending_caption = ""
    i = 0

    def flush() -> None:
        if paragraph:
            blocks.append(Block("paragraph", text=" ".join(s.strip() for s in paragraph), source=source))
            paragraph.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush()
            i += 1
            continue

        if stripped.startswith("```"):
            flush()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(Block("code", text="\n".join(code), caption=pending_caption, source=source))
            pending_caption = ""
            i += 1
            continue

        match = HEADING_RE.match(stripped)
        if match:
            flush()
            marks, title, flag = match.groups()
            blocks.append(
                Block(
                    "heading",
                    text=title,
                    level=len(marks),
                    numbered=flag is None,
                    appendix=flag == "app",
                    source=source,
                )
            )
            i += 1
            continue

        match = FIGURE_RE.match(stripped)
        if match:
            flush()
            blocks.append(Block("figure", caption=match.group(1), path=match.group(2), source=source))
            i += 1
            continue

        match = TABLE_CAPTION_RE.match(stripped)
        if match:
            flush()
            pending_caption = match.group(1)
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            blocks.append(Block("table", caption=pending_caption, rows=rows, source=source))
            pending_caption = ""
            continue

        match = LIST_RE.match(line)
        if match:
            flush()
            ordered = match.group(2)[0].isdigit()
            items: list[str] = []
            while i < len(lines) and LIST_RE.match(lines[i]):
                items.append(LIST_RE.match(lines[i]).group(3).strip())
                i += 1
            blocks.append(Block("list", items=items, ordered=ordered, source=source))
            continue

        paragraph.append(line)
        i += 1

    flush()
    return blocks


def assign_numbers(blocks: list[Block]) -> None:
    """Расставляет номера разделов, рисунков и таблиц по правилам СТП."""
    chapter = section = subsection = 0
    figure = table = listing = 0
    appendix_letters = "АБВДЕЖИКЛМНПРСТУФХЦШЩЭЮЯ"
    appendix_index = -1
    in_appendix = False

    for block in blocks:
        if block.kind == "heading":
            if block.appendix:
                appendix_index += 1
                in_appendix = True
                chapter, section, subsection = 0, 0, 0
                figure = table = listing = 0
                block.number = appendix_letters[appendix_index]
                continue
            if not block.numbered:
                continue
            if block.level == 1:
                chapter += 1
                section = subsection = 0
                figure = table = listing = 0
                block.number = str(chapter)
            elif block.level == 2:
                section += 1
                subsection = 0
                block.number = f"{chapter}.{section}"
            else:
                subsection += 1
                block.number = f"{chapter}.{section}.{subsection}"
        elif block.kind == "figure":
            figure += 1
            prefix = appendix_letters[appendix_index] if in_appendix else str(chapter)
            block.number = f"{prefix}.{figure}"
        elif block.kind == "table" and block.caption:
            table += 1
            prefix = appendix_letters[appendix_index] if in_appendix else str(chapter)
            block.number = f"{prefix}.{table}"
        elif block.kind == "code" and block.caption:
            listing += 1
            prefix = appendix_letters[appendix_index] if in_appendix else str(chapter)
            block.number = f"{prefix}.{listing}"


FIG_REF_RE = re.compile(r"\{fig:([\w\-]+)\}")


def resolve_references(blocks: list[Block]) -> None:
    """Заменяет метки {fig:имя} номерами рисунков."""
    numbers = {Path(b.path).stem: b.number for b in blocks if b.kind == "figure"}
    for block in blocks:
        if block.kind in {"paragraph", "list"}:
            replace = lambda m: numbers.get(m.group(1), "??")
            if block.kind == "paragraph":
                block.text = FIG_REF_RE.sub(replace, block.text)
            else:
                block.items = [FIG_REF_RE.sub(replace, item) for item in block.items]


def load_sections(directory: Path) -> list[Block]:
    blocks: list[Block] = []
    for path in sorted(directory.glob("*.md")):
        blocks.extend(parse(path.read_text(encoding="utf-8"), source=path.name))
    assign_numbers(blocks)
    resolve_references(blocks)
    return blocks
