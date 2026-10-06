from __future__ import annotations

import re
from dataclasses import dataclass

from reportgen.domain.blocks import Block, Kind

MARK_RE = re.compile(r"\[УТОЧНИТЬ:?\s*([^\]]*)\]", re.IGNORECASE)
NO_TOPIC = "без раздела"


@dataclass(frozen=True)
class Question:
    section: str
    text: str

    def __str__(self) -> str:
        return f"{self.section}: {self.text}"


def open_questions(blocks: list[Block]) -> list[Question]:
    """Вопросы автору: по одной записи на каждую метку «[УТОЧНИТЬ: …]» с названием раздела, где она стоит."""
    section = NO_TOPIC
    questions: list[Question] = []
    for block in blocks:
        if block.kind == Kind.HEADING:
            section = block.text.strip() or NO_TOPIC
            continue
        for text in _texts(block):
            questions += [Question(section, _question_text(match)) for match in MARK_RE.findall(text)]
    return questions


def _texts(block: Block) -> list[str]:
    return [block.text, block.caption, *block.items, *(cell for row in block.rows for cell in row)]


def _question_text(label: str) -> str:
    label = label.strip().rstrip(".")
    return label[:1].upper() + label[1:] + "?" if label else "Нужны сведения для этого места?"
