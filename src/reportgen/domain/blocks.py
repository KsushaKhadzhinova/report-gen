from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    FIGURE = "figure"
    TABLE = "table"
    LIST = "list"
    CODE = "code"


@dataclass
class Block:
    kind: Kind
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

    @property
    def is_centered_heading(self) -> bool:
        return self.kind is Kind.HEADING and self.level == 1 and (self.appendix or not self.numbered)
