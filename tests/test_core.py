from pathlib import Path

from docx import Document
from docx.shared import Mm

from reportgen import lint, overlap, render_docx, render_tex, stp
from reportgen.document import assign_numbers, parse, resolve_references

SOURCE = """# ВВЕДЕНИЕ {-}

Первый абзац введения достаточной длины для проверки разбора текста.

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


def blocks():
    result = parse(SOURCE, "test.md")
    assign_numbers(result)
    resolve_references(result)
    return result


def test_numbering_follows_stp():
    items = blocks()
    headings = [b for b in items if b.kind == "heading"]
    assert [h.number for h in headings] == ["", "1", "1.1"]
    figure = next(b for b in items if b.kind == "figure")
    table = next(b for b in items if b.kind == "table")
    assert figure.number == "1.1"
    assert table.number == "1.1"


def test_figure_reference_resolved():
    paragraph = next(b for b in blocks() if b.kind == "paragraph" and "схема" in b.text)
    assert "рисунке 1.1" in paragraph.text


def test_list_punctuation():
    assert stp.list_items(["один", "два"]) == ["– один;", "– два."]


def test_captions_use_dash():
    assert stp.figure_caption("2.1", "Схема") == "Рисунок 2.1 – Схема"
    assert stp.table_caption("2.1", "Данные") == "Таблица 2.1 – Данные"


def test_overlap_detects_copied_paragraph(tmp_path: Path):
    reference = tmp_path / "ref"
    reference.mkdir()
    original = "Система предназначена для автоматизации учёта заказов и позволяет формировать отчёты по продажам за выбранный период времени"
    (reference / "work.txt").write_text(original, encoding="utf-8")
    matches = overlap.scan([original, "Совершенно иной текст про другую предметную область без пересечений с эталоном вообще"], reference)
    assert len(matches) == 1 and matches[0].source == "work.txt"


def test_lint_flags_missing_reference_and_first_person():
    items = parse("# Раздел\n\nМы сделали систему.\n\n![Схема](a.png)\n", "x.md")
    assign_numbers(items)
    messages = [i.message for i in lint.check_blocks(items)]
    assert any("Личные местоимения" in m for m in messages)
    assert any("Нет ссылки на рисунок" in m for m in messages)


def test_docx_render_matches_stp_page_setup(tmp_path: Path):
    output = render_docx.render(blocks(), {"title": "Тест"}, tmp_path, tmp_path / "note.docx")
    section = Document(str(output)).sections[0]
    assert abs(section.left_margin - Mm(30)) < Mm(0.5)
    assert abs(section.right_margin - Mm(15)) < Mm(0.5)
    assert not [i for i in lint.audit_docx(output) if "поле" in i.message]


def test_tex_render_escapes_and_lists_figures(tmp_path: Path):
    tex = render_tex.render(blocks(), {"title": "Тест"}, tmp_path, tmp_path / "tex")
    text = tex.read_text(encoding="utf-8")
    assert r"\stpchapter{1}{АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ}" in text
    assert "нет файла" in text
