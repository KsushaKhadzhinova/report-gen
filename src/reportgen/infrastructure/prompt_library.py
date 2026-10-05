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


def _prompts() -> dict:
    """Встроенные шаблоны; шаблоны пользователя заменяют только те ключи, которые он указал."""
    builtin = yaml.safe_load(read_data(f"{GUIDELINES}/prompts.yaml"))
    custom_file = home() / USER_OVERRIDES / "prompts.yaml"
    if not custom_file.is_file():
        return builtin
    custom = yaml.safe_load(custom_file.read_text(encoding="utf-8")) or {}
    merged = {**builtin, **custom}
    merged["section_rules"] = {**builtin.get("section_rules", {}), **custom.get("section_rules", {})}
    return merged


def load_prompt_catalog() -> PromptCatalog:
    prompts = _prompts()
    return PromptCatalog(
        system=prompts["system"],
        section=prompts["section"],
        rewrite=prompts["rewrite"],
        revise=prompts["revise"],
        review=prompts["review"],
        gap_fill=prompts["gap_fill"],
        standard_rules=_read("enterprise_standard_rules.md"),
        writing_rules=_read("writing_rules.md"),
        section_rules=prompts["section_rules"],
    )
