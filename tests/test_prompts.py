from reportgen.domain.lint_rules import check_blocks
from reportgen.domain.markup import parse
from reportgen.domain.numbering import APPENDIX_LETTERS, assign_numbers
from reportgen.domain.structure import Section
from reportgen.infrastructure.prompt_library import load_prompt_catalog


def test_system_prompt_carries_the_standard_and_writing_rules():
    prompt = load_prompt_catalog().system_prompt("Манера автора: предложение около 20 слов.")
    for expected in ("Times New Roman", "30 мм", "Википедию", "[УТОЧНИТЬ", "Манера автора"):
        assert expected in prompt


def test_section_prompt_includes_requirements_of_that_section():
    catalog = load_prompt_catalog()
    section = Section("00_introduction", "ВВЕДЕНИЕ", numbered=False, words=300, guide="Актуальность", rules="introduction")
    prompt = catalog.section_prompt(section, facts="Факты проекта", task="", figure_rule="")
    assert "не больше двух страниц" in prompt
    assert "Факты проекта" in prompt
    assert "{" not in prompt.replace("{fig:", "")


def test_every_rules_key_used_by_structures_exists():
    import yaml

    from reportgen.infrastructure.settings import read_data

    catalog = load_prompt_catalog()
    for name in ("coursework", "lab"):
        for section in yaml.safe_load(read_data(f"{name}.yaml"))["sections"]:
            assert section.get("rules", "") in catalog.section_rules or not section.get("rules")


def test_appendix_letters_follow_the_standard():
    assert APPENDIX_LETTERS[:5] == "АБВГД"
    assert not set("ЁЗЙОЧЪЫЬ") & set(APPENDIX_LETTERS)


def test_unresolved_gap_marker_is_an_error():
    blocks = parse("# ВВЕДЕНИЕ {-}\n\nЗдесь пропуск [УТОЧНИТЬ: версия сервера].\n", "x.md")
    assign_numbers(blocks)
    assert any(issue.is_error for issue in check_blocks(blocks))
