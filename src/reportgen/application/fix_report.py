from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportgen.application.ports import FormatService, LanguageModel, ReferenceLibrary, StyleStore
from reportgen.domain import overlap
from reportgen.domain.style_profile import style_instruction

MIN_REVIEWED_PARAGRAPH = 120
REVIEW_TEXT_LIMIT = 9000
REVIEWER_ROLE_PROMPT = "Ты редактор пояснительных записок по СТП БГУИР. Отвечай по-русски, конкретно, списком правок."


@dataclass
class FixResult:
    issues_before: list[str]
    issues_after: list[str] = field(default_factory=list)
    paragraphs_formatted: int = 0
    paragraphs_rewritten: int = 0
    review: str = ""


class ReportFixer:
    def __init__(
        self,
        formatter: FormatService,
        model: LanguageModel | None = None,
        style_store: StyleStore | None = None,
        references: ReferenceLibrary | None = None,
    ) -> None:
        self.formatter = formatter
        self.model = model
        self.style_store = style_store
        self.references = references

    def fix(self, source: Path, output: Path, remarks: str = "") -> FixResult:
        result = FixResult([str(issue) for issue in self.formatter.audit(source)])
        result.paragraphs_formatted = self.formatter.fix(source, output)
        if self.model and self.references:
            result.paragraphs_rewritten = self._rewrite_overlaps(output)
        if self.model and remarks:
            result.review = self._review(output, remarks)
        result.issues_after = [str(issue) for issue in self.formatter.audit(output)]
        return result

    def _rewrite_overlaps(self, document_path: Path) -> int:
        text = self.formatter.open_text(document_path)
        long_paragraphs = [p for p in text.paragraphs() if len(p) > MIN_REVIEWED_PARAGRAPH]
        flagged = [m.text for m in overlap.find_matches(long_paragraphs, self.references.documents())]
        for paragraph in flagged:
            text.replace(paragraph, self._rephrase(paragraph))
        text.save()
        return len(flagged)

    def _rephrase(self, paragraph: str) -> str:
        profile = self.style_store.load() if self.style_store else None
        return self.model.complete(
            "rewriter",
            style_instruction(profile),
            "Перепиши абзац другими словами, сохранив смысл и факты. Верни только абзац.\n\n" + paragraph,
            temperature=0.9,
        )

    def _review(self, document_path: Path, remarks: str) -> str:
        body = "\n".join(self.formatter.open_text(document_path).paragraphs())[:REVIEW_TEXT_LIMIT]
        return self.model.complete(
            "reviewer",
            REVIEWER_ROLE_PROMPT,
            f"Замечания руководителя:\n{remarks}\n\nТекст записки:\n{body}\n\n"
            "Для каждого замечания укажи, в каком месте текста оно применимо и как именно исправить.",
            temperature=0.3,
        )
