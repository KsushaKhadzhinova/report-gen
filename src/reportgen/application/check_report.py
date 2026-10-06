from __future__ import annotations

from dataclasses import dataclass

from reportgen.application.ports import ProjectRepository, ReferenceLibrary
from reportgen.domain import overlap
from reportgen.domain.lint_rules import Issue, check_blocks
from reportgen.domain.open_questions import Question, open_questions


def lint_report(repository: ProjectRepository) -> list[Issue]:
    return check_blocks(repository.load_blocks())


def list_open_questions(repository: ProjectRepository) -> list[Question]:
    return open_questions(repository.load_blocks())


@dataclass(frozen=True)
class OverlapReport:
    matches: list[overlap.Match]
    share: float


def check_overlap(paragraphs: list[str], library: ReferenceLibrary, threshold: float = overlap.DEFAULT_THRESHOLD) -> OverlapReport:
    index = library.documents()
    return OverlapReport(overlap.find_matches(paragraphs, index, threshold), overlap.overall_share(paragraphs, index))
