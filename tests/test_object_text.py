from pathlib import Path

from docx import Document

from reportgen.domain.object_sentences import figure_sentence, table_sentence
from reportgen.infrastructure.docx_format import DocxFormatService
from reportgen.infrastructure.docx_objects import count_objects_without_text

BODY = "Это обычный абзац основного текста отчёта, достаточно длинный, чтобы считаться текстом раздела."


def build(tmp_path: Path, with_text_after: bool) -> Path:
    document = Document()
    document.add_heading("Раздел", level=1)
    document.add_paragraph(BODY)
    document.add_paragraph("Таблица 1 – Рабочая таблица ядра")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "А"
    table.rows[0].cells[1].text = "Б"
    if with_text_after:
        document.add_paragraph(BODY)
    document.add_heading("Следующий раздел", level=1)
    document.add_paragraph(BODY)
    path = tmp_path / "objects.docx"
    document.save(path)
    return path


def test_table_followed_by_a_heading_gets_a_reference_sentence(tmp_path: Path):
    output = tmp_path / "fixed.docx"
    DocxFormatService().fix(build(tmp_path, with_text_after=False), output)
    texts = [p.text for p in Document(output).paragraphs]
    assert "Данные по теме «рабочая таблица ядра» приведены в таблице 1." in texts
    assert count_objects_without_text(Document(output)) == 0


def test_table_followed_by_text_is_left_alone(tmp_path: Path):
    output = tmp_path / "fixed.docx"
    DocxFormatService().fix(build(tmp_path, with_text_after=True), output)
    assert not [p.text for p in Document(output).paragraphs if p.text.startswith("Данные по теме")]


def test_audit_warns_about_missing_text(tmp_path: Path):
    messages = [i.message for i in DocxFormatService().audit(build(tmp_path, with_text_after=False))]
    assert any("без текста после таблицы или рисунка: 1" in m for m in messages)


def test_sentences_keep_abbreviations_and_ignore_other_captions():
    assert table_sentence("Таблица 2.1 – UML-диаграммы") == "Данные по теме «UML-диаграммы» приведены в таблице 2.1."
    assert figure_sentence("Рисунок 3 – Схема данных") == "Рисунок 3 иллюстрирует тему «схема данных»."
    assert table_sentence("Просто текст") is None


def test_appendix_status_and_title_are_centered(tmp_path: Path):
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    document = Document()
    document.add_paragraph("ПРИЛОЖЕНИЕ Б")
    document.add_paragraph("(обязательное)")
    document.add_paragraph("Контрольная выгрузка Вордстата")
    document.add_paragraph(BODY)
    path = tmp_path / "appendix.docx"
    document.save(path)
    output = tmp_path / "appendix_fixed.docx"
    DocxFormatService().fix(path, output)
    paragraphs = Document(output).paragraphs
    assert [p.alignment for p in paragraphs[:3]] == [WD_ALIGN_PARAGRAPH.CENTER] * 3
    assert all(run.bold for run in paragraphs[2].runs)
    assert paragraphs[3].alignment != WD_ALIGN_PARAGRAPH.CENTER
