from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Callable

from reportgen.application.ports import LanguageModel, ProjectRepository, ReferenceLibrary, StyleStore
from reportgen.domain import overlap
from reportgen.domain.prompts import PromptCatalog
from reportgen.domain.structure import Section, Structure
from reportgen.domain.style_profile import style_hints

MAX_REWRITE_PASSES = 2
SECTION_MAX_TOKENS = 6000
REWRITE_TEMPERATURE = 0.9
MARKUP_RE = re.compile(r"^(#+\s*|>\s*)|(\*\*|__)", re.MULTILINE)
LEADING_NUMBER_RE = re.compile(r"^\d+[.)]?\s*")

Progress = Callable[[str], None]


@dataclass(frozen=True)
class WritingContext:
    """Сведения, на которых модель строит текст."""

    facts: str = ""
    task: str = ""


def figure_token(name: str) -> str:
    return "{fig:%s}" % name


def clean_model_output(text: str) -> str:
    without_markup = MARKUP_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", without_markup).strip()


def heading_line(section: Section) -> str:
    suffix = "" if section.numbered else " {-}"
    return f"{'#' * section.level} {section.title}{suffix}"


class ReportWriter:
    def __init__(
        self,
        model: LanguageModel,
        style_store: StyleStore,
        prompts: PromptCatalog,
        references: ReferenceLibrary | None = None,
    ) -> None:
        self.model = model
        self.style_store = style_store
        self.prompts = prompts
        self.references = references

    def write(
        self,
        structure: Structure,
        repository: ProjectRepository,
        context: WritingContext,
        only: str | None = None,
        force: bool = False,
        progress: Progress = print,
    ) -> dict[str, str]:
        figures = repository.figure_captions()
        status: dict[str, str] = {}
        for section in structure.sections:
            if only and only != section.id:
                continue
            status[section.id] = self._write_one(section, repository, context, figures, force)
            progress(f"  {section.id}: {status[section.id]}")
        return status

    def _system_prompt(self) -> str:
        return self.prompts.system_prompt(style_hints(self.style_store.load()))

    def _write_one(
        self,
        section: Section,
        repository: ProjectRepository,
        context: WritingContext,
        figures: dict[str, str],
        force: bool,
    ) -> str:
        fingerprint = self._fingerprint(section, context, figures)
        if not force and repository.section_exists(section.id) and repository.cached_fingerprint(section.id) == fingerprint:
            return "без изменений"
        markdown, rewritten = self._compose(section, repository, context, figures)
        repository.save_section(section.id, markdown)
        repository.store_fingerprint(section.id, fingerprint)
        return "готово" + (f", переписано абзацев: {rewritten}" if rewritten else "")

    def _compose(
        self,
        section: Section,
        repository: ProjectRepository,
        context: WritingContext,
        figures: dict[str, str],
    ) -> tuple[str, int]:
        if section.is_references:
            return self._references_markdown(section, repository.read_sources()), 0
        if section.is_container:
            return heading_line(section) + "\n", 0

        available = [name for name in section.figures if name in figures]
        body = clean_model_output(self._ask_for_body(section, context, figures, available))
        body, rewritten = self._remove_overlaps(body)
        body = self._ensure_figure_references(body, available)
        figure_lines = [f"![{figures[name]}](screenshots/{name}.png)" for name in available]
        parts = [heading_line(section), "", body] + ([""] + ["\n\n".join(figure_lines)] if figure_lines else [])
        return "\n".join(parts) + "\n", rewritten

    def _ask_for_body(self, section: Section, context: WritingContext, figures: dict[str, str], available: list[str]) -> str:
        prompt = self.prompts.section_prompt(section, context.facts, context.task, self._figure_rule(figures, available))
        return self.model.complete("writer", self._system_prompt(), prompt, max_tokens=SECTION_MAX_TOKENS)

    @staticmethod
    def _figure_rule(figures: dict[str, str], available: list[str]) -> str:
        if not available:
            return ""
        listing = "; ".join(f"{figure_token(name)} — {figures[name]}" for name in available)
        return (
            "В тексте обязательно сошлись на каждый рисунок оборотом вида «на рисунке {fig:имя} показано…», "
            f"сохраняя метки в фигурных скобках без изменений. Рисунки: {listing}."
        )

    def _remove_overlaps(self, body: str) -> tuple[str, int]:
        if self.references is None:
            return body, 0
        index = self.references.documents()
        paragraphs = [p for p in body.split("\n\n") if p.strip()]
        rewritten = 0
        for _ in range(MAX_REWRITE_PASSES):
            flagged = {m.text for m in overlap.find_matches(paragraphs, index)}
            if not flagged:
                break
            paragraphs = [self._rephrase(p) if p in flagged else p for p in paragraphs]
            rewritten += len(flagged)
        return "\n\n".join(paragraphs), rewritten

    def _rephrase(self, paragraph: str) -> str:
        reply = self.model.complete(
            "rewriter",
            self._system_prompt(),
            self.prompts.rewrite_prompt(paragraph),
            temperature=REWRITE_TEMPERATURE,
        )
        return clean_model_output(reply)

    @staticmethod
    def _ensure_figure_references(body: str, available: list[str]) -> str:
        for name in available:
            if figure_token(name) not in body:
                body += f"\n\nВнешний вид показан на рисунке {figure_token(name)}."
        return body

    @staticmethod
    def _references_markdown(section: Section, sources: list[str] | None) -> str:
        lines = [heading_line(section), ""]
        if not sources:
            return "\n".join(lines + ["[УТОЧНИТЬ: добавьте источники в файл sources.txt, по одному в строке]", ""])
        for number, entry in enumerate(sources, 1):
            lines += [f"{number} {LEADING_NUMBER_RE.sub('', entry)}", ""]
        return "\n".join(lines)

    def _fingerprint(self, section: Section, context: WritingContext, figures: dict[str, str]) -> str:
        payload = json.dumps(
            {
                "section": section.__dict__,
                "facts": context.facts,
                "task": context.task,
                "figures": figures,
                "prompt": self._system_prompt(),
                "template": self.prompts.section,
                "model": self.model.identity,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=list,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
