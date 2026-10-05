from __future__ import annotations

from dataclasses import dataclass, field

from reportgen.domain.structure import Section


@dataclass(frozen=True)
class PromptCatalog:
    """Шаблоны запросов и своды правил, по которым модель пишет и проверяет текст."""

    system: str
    section: str
    rewrite: str
    revise: str
    review: str
    gap_fill: str
    standard_rules: str
    writing_rules: str
    section_rules: dict[str, str] = field(default_factory=dict)

    def system_prompt(self, style_hints: str = "") -> str:
        parts = [self.system.strip(), self.standard_rules.strip(), self.writing_rules.strip()]
        if style_hints:
            parts.append(style_hints)
        return "\n\n".join(parts)

    def section_prompt(self, section: Section, facts: str, task: str, figure_rule: str, standard_excerpts: str = "") -> str:
        return self.section.format(
            title=section.title,
            guide=section.guide,
            words=section.words,
            section_rules=self.section_rules.get(section.rules, "").strip(),
            figure_rule=figure_rule,
            standard_excerpts=standard_excerpts or "(индекс стандарта не подключён)",
            task=f"\nЗадание:\n{task}\n" if task else "",
            facts=facts or "Сведений нет: пиши общим научно-техническим текстом без конкретных названий и ставь метки [УТОЧНИТЬ: …].",
        )

    def rewrite_prompt(self, paragraph: str) -> str:
        return self.rewrite.format(paragraph=paragraph)

    def revise_prompt(self, title: str, issues: list[str], body: str, facts: str) -> str:
        return self.revise.format(title=title, issues="\n".join(f"- {issue}" for issue in issues), body=body, facts=facts or "(сведений нет)")

    def review_prompt(self, remarks: str, document: str) -> str:
        return self.review.format(remarks=remarks, document=document)

    def gap_fill_prompt(self, document: str) -> str:
        return self.gap_fill.format(document=document)
