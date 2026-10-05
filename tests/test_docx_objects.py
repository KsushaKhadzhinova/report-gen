from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Pt

from reportgen.infrastructure.docx_format import DocxFormatService
from reportgen.infrastructure.docx_objects import _sentence_case


def build_source(tmp_path: Path) -> Path:
    from PIL import Image

    picture_file = tmp_path / "picture.png"
    Image.new("RGB", (60, 40), "white").save(picture_file)
    document = Document()
    document.add_paragraph("Министерство образования Республики Беларусь")
    document.add_paragraph("Минск, октябрь 2026")
    document.add_heading("ЦЕЛЬ РАБОТЫ", level=1)
    document.add_paragraph("Текст перед таблицей, достаточно длинный, чтобы считаться основным абзацем документа по стандарту предприятия.")
    document.add_paragraph("Таблица 1 – Пример")
    table = document.add_table(rows=3, cols=2)
    for row in table.rows:
        for cell in row.cells:
            cell.text = "Ячейка"
    document.add_paragraph("Текст сразу после таблицы без пустой строки, достаточно длинный, чтобы считаться основным абзацем документа.")
    picture_paragraph = document.add_paragraph()
    picture_paragraph.add_run().add_picture(str(picture_file))
    picture_paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    picture_paragraph.paragraph_format.line_spacing = Pt(18)
    document.add_paragraph("Рисунок 1 – Пример рисунка")
    document.add_heading("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", level=1)
    document.add_paragraph("В качестве источников использованы следующие:")
    entry = document.add_paragraph()
    entry.add_run("– Иванов, И. И. ")
    entry.add_run("Основы анализа").italic = True
    document.add_paragraph("– Петров, П. П. Методика расчёта.")
    source = tmp_path / "source.docx"
    document.save(str(source))
    return source


def fixed(tmp_path: Path) -> Document:
    output = tmp_path / "fixed.docx"
    DocxFormatService().fix(build_source(tmp_path), output)
    return Document(str(output))


def find(document, fragment: str):
    return next(p for p in document.paragraphs if fragment in p.text)


def test_title_has_no_month(tmp_path: Path):
    assert find(fixed(tmp_path), "Минск").text == "Минск 2026"


def test_section_heading_is_typed_in_normal_case_and_shown_in_capitals_by_style(tmp_path: Path):
    document = fixed(tmp_path)
    assert find(document, "Цель").text == "Цель работы"
    assert document.styles["Heading 1"].font.all_caps is True


def test_sentence_case_keeps_abbreviations_and_numbers():
    assert _sentence_case("ИСПОЛЬЗОВАНИЕ СУБД ДЛЯ ЛР5") == "Использование СУБД для ЛР5"


def test_table_caption_has_a_blank_line_before_and_the_text_after_the_table_too(tmp_path: Path):
    document = fixed(tmp_path)
    assert find(document, "Таблица 1").paragraph_format.space_before == Pt(18)
    assert find(document, "Текст сразу после таблицы").paragraph_format.space_before == Pt(18)


def test_table_uses_standard_font_single_spacing_and_fits_content(tmp_path: Path):
    document = fixed(tmp_path)
    table = document.tables[0]
    paragraph = table.rows[0].cells[0].paragraphs[0]
    assert paragraph.runs[0].font.size == Pt(12)
    assert paragraph.paragraph_format.line_spacing_rule == WD_LINE_SPACING.SINGLE
    assert table.autofit is False
    assert table.rows[0]._tr.trPr.xpath("w:tblHeader")


def test_figure_is_not_clipped_and_is_framed_by_blank_lines(tmp_path: Path):
    document = fixed(tmp_path)
    picture = next(p for p in document.paragraphs if p._p.xpath(".//w:drawing"))
    assert picture.paragraph_format.line_spacing_rule == WD_LINE_SPACING.SINGLE
    assert picture.paragraph_format.space_before == Pt(18)
    assert find(document, "Рисунок 1").paragraph_format.space_after == Pt(18)


def test_sources_have_no_intro_dashes_or_italics_and_are_numbered(tmp_path: Path):
    document = fixed(tmp_path)
    texts = [p.text for p in document.paragraphs]
    start = texts.index("Список использованных источников") if "Список использованных источников" in texts else None
    assert start is not None
    assert not any("следующие" in text for text in texts)
    first = find(document, "Иванов")
    assert first.text.startswith("1 Иванов")
    assert all(run.italic is False for run in first.runs)
    assert find(document, "Петров").text.startswith("2 Петров")


def test_column_widths_keep_short_columns_readable_and_fill_the_text_width():
    from reportgen.infrastructure.docx_objects import TEXT_WIDTH_CM, column_widths_cm

    columns = [
        ["Часть", "A", "B"],
        ["Методика", "Классификация компаний по уровням конкуренции", "Анализ по сайтам"],
        ["Рабочая книга", "Excel/klassifikaciya_urovni_konkurencii_NotaCode.xlsx", "Excel/analiz_konkurentov_Levitt_Kano_NotaCode.xlsx"],
        ["Результат", "Реестр из 22 компаний, оценка по критериям, уровни, карта близости", "Выборка из 8 конкурентов, карта сайтов"],
    ]
    widths = column_widths_cm(columns)
    assert abs(sum(widths) - TEXT_WIDTH_CM) < 0.01
    assert widths[0] >= len("Часть") * 0.22
    assert widths[3] > widths[0] * 2


def test_preposition_po_is_not_treated_as_an_abbreviation():
    assert _sentence_case("ПРОВЕРКА ПО КРИТЕРИЯМ МЕТОДИКИ") == "Проверка по критериям методики"
