from __future__ import annotations

import yaml

from reportgen.domain.prompts import PromptCatalog
from reportgen.infrastructure.settings import home, read_data

GUIDELINES = "guidelines"
USER_OVERRIDES = "guidelines"


def _read(name: str) -> str:
    """Файл из рабочей папки пользователя, если он положил свою версию, иначе встроенный."""
    custom = home() / USER_OVERRIDES / name
    if custom.is_file():
        return custom.read_text(encoding="utf-8")
    return read_data(f"{GUIDELINES}/{name}")


def load_prompt_catalog() -> PromptCatalog:
    prompts = yaml.safe_load(_read("prompts.yaml"))
    return PromptCatalog(
        system=prompts["system"],
        section=prompts["section"],
        rewrite=prompts["rewrite"],
        review=prompts["review"],
        gap_fill=prompts["gap_fill"],
        standard_rules=_read("enterprise_standard_rules.md"),
        writing_rules=_read("writing_rules.md"),
        section_rules=prompts.get("section_rules", {}),
    )
