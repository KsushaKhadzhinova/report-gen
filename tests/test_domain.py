from reportgen.domain import enterprise_standard as standard
from reportgen.domain import overlap
from reportgen.domain.blocks import Kind
from reportgen.domain.lint_rules import check_blocks
from reportgen.domain.markup import parse
from reportgen.domain.numbering import assign_numbers, resolve_figure_references
from reportgen.domain.outline import OutlineEntry, structure_from_outline
from reportgen.domain.style_profile import build_profile, style_instruction

SOURCE = """# ВВЕДЕНИЕ {-}

Первый абзац введения.

# АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ

## Описание предметной области

На рисунке {fig:er} показана схема, а в таблице 1.1 приведены данные.

![ER-диаграмма](screenshots/er.png)

Таблица: Основные сущности

| Сущность | Назначение |
|---|---|
| Пользователь | Хранит учётные данные |

- первый пункт
- второй пункт
"""


def numbered_blocks():
    blocks = parse(SOURCE, "test.md")
    assign_numbers(blocks)
    resolve_figure_references(blocks)
    return blocks


def test_headings_figures_and_tables_are_numbered_per_chapter():
    blocks = numbered_blocks()
    headings = [b.number for b in blocks if b.kind is Kind.HEADING]
    assert headings == ["", "1", "1.1"]
    assert next(b for b in blocks if b.kind is Kind.FIGURE).number == "1.1"
    assert next(b for b in blocks if b.kind is Kind.TABLE).number == "1.1"


def test_figure_reference_is_replaced_with_number():
    paragraph = next(b for b in numbered_blocks() if b.kind is Kind.PARAGRAPH and "схема" in b.text)
    assert "рисунке 1.1" in paragraph.text


def test_appendix_numbering_uses_letters():
    blocks = parse("# Приложение {app}\n\n![Схема](a.png)\n")
    assign_numbers(blocks)
    assert blocks[0].number == "А"
    assert blocks[1].number == "А.1"


def test_list_items_follow_standard_punctuation():
    assert standard.list_items(["один", "два"]) == ["– один;", "– два."]


def test_captions_use_dash():
    assert standard.figure_caption("2.1", "Схема") == "Рисунок 2.1 – Схема"
    assert standard.table_caption("2.1", "Данные") == "Таблица 2.1 – Данные"


def test_overlap_flags_only_copied_paragraph():
    original = "Система предназначена для автоматизации учёта заказов и позволяет формировать отчёты по продажам за выбранный период"
    other = "Совершенно иной текст про другую предметную область без пересечений с эталоном вообще никаких"
    index = overlap.index_references([("work.txt", original)])
    matches = overlap.find_matches([original, other], index)
    assert [m.source for m in matches] == ["work.txt"]
    assert overlap.overall_share([original, other], index) > 0.4


def test_lint_reports_first_person_and_missing_figure_reference():
    blocks = parse("# Раздел\n\nМы сделали систему.\n\n![Схема](a.png)\n", "x.md")
    assign_numbers(blocks)
    messages = [i.message for i in check_blocks(blocks)]
    assert any("Личные местоимения" in m for m in messages)
    assert any("Нет ссылки на рисунок" in m for m in messages)


def test_lint_flags_numbered_introduction():
    blocks = parse("# ВВЕДЕНИЕ\n\nТекст.\n", "x.md")
    assign_numbers(blocks)
    assert any(i.is_error for i in check_blocks(blocks))


def test_outline_becomes_structure_without_copying_text():
    entries = [OutlineEntry("ВВЕДЕНИЕ", 1, 400), OutlineEntry("1 Анализ", 1, 0), OutlineEntry("1.1 Предметная область", 2, 20)]
    structure = structure_from_outline(entries)
    titles = [(s.title, s.numbered, s.words) for s in structure.sections]
    assert titles == [("ВВЕДЕНИЕ", False, 400), ("Анализ", True, 0), ("Предметная область", True, 80)]


def test_style_profile_feeds_instruction():
    paragraphs = [("a.docx", "Система обеспечивает хранение данных. " * 12 + "Результат работы приведён далее.")] * 3
    profile = build_profile(paragraphs)
    assert profile.paragraphs == 3
    assert "около" in style_instruction(profile)
    assert style_instruction(None).startswith("Пиши на русском")
