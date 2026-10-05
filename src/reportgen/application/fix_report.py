from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportgen.application.ports import FormatService, LanguageModel, ReferenceLibrary, StyleStore
from reportgen.domain import overlap
from reportgen.domain.fix_options import FixOptions
from reportgen.domain.prompts import PromptCatalog
from reportgen.domain.style_profile import style_hints

MIN_REVIEWED_PARAGRAPH = 120
REVIEW_TEXT_LIMIT = 9000
REWRITE_TEMPERATURE = 0.9
REVIEW_TEMPERATURE = 0.3


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
        prompts: PromptCatalog,
        model: LanguageModel | None = None,
        style_store: StyleStore | None = None,
        references: ReferenceLibrary | None = None,
    ) -> None:
        self.formatter = formatter
        self.prompts = prompts
        self.model = model
        self.style_store = style_store
        self.references = references

    def fix(self, source: Path, output: Path, remarks: str = "", options: FixOptions = FixOptions()) -> FixResult:
        result = FixResult([str(issue) for issue in self.formatter.audit(source)])
        result.paragraphs_formatted = self.formatter.fix(source, output, options)
        if self.model and self.references:
            result.paragraphs_rewritten = self._rewrite_overlaps(output)
        if self.model and remarks:
            result.review = self._review(output, remarks)
        result.issues_after = [str(issue) for issue in self.formatter.audit(output)]
        return result

    def _system_prompt(self) -> str:
        profile = self.style_store.load() if self.style_store else None
        return self.prompts.system_prompt(style_hints(profile))

    def _rewrite_overlaps(self, document_path: Path) -> int:
        text = self.formatter.open_text(document_path)
        long_paragraphs = [p for p in text.paragraphs() if len(p) > MIN_REVIEWED_PARAGRAPH]
        flagged = [m.text for m in overlap.find_matches(long_paragraphs, self.references.documents())]
        for paragraph in flagged:
            text.replace(paragraph, self._rephrase(paragraph))
        text.save()
        return len(flagged)

    def _rephrase(self, paragraph: str) -> str:
        return self.model.complete("rewriter", self._system_prompt(), self.prompts.rewrite_prompt(paragraph), temperature=REWRITE_TEMPERATURE)

    def _review(self, document_path: Path, remarks: str) -> str:
        body = "\n".join(self.formatter.open_text(document_path).paragraphs())[:REVIEW_TEXT_LIMIT]
        return self.model.complete("reviewer", self._system_prompt(), self.prompts.review_prompt(remarks, body), temperature=REVIEW_TEMPERATURE)
