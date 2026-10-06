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
    assert "В таблице 1 приведено: рабочая таблица ядра." in texts
    assert count_objects_without_text(Document(output)) == 0


def test_table_followed_by_text_is_left_alone(tmp_path: Path):
    output = tmp_path / "fixed.docx"
    DocxFormatService().fix(build(tmp_path, with_text_after=True), output)
    assert not [p.text for p in Document(output).paragraphs if p.text.startswith("В таблице")]


def test_audit_warns_about_missing_text(tmp_path: Path):
    messages = [i.message for i in DocxFormatService().audit(build(tmp_path, with_text_after=False))]
    assert any("без текста после таблицы или рисунка: 1" in m for m in messages)


def test_sentences_keep_abbreviations_and_ignore_other_captions():
    assert table_sentence("Таблица 2.1 – UML-диаграммы") == "В таблице 2.1 приведено: UML-диаграммы."
    assert figure_sentence("Рисунок 3 – Схема данных") == "На рисунке 3 показано: схема данных."
    assert table_sentence("Просто текст") is None
