from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from reportgen.domain.fix_options import FixOptions
from reportgen.infrastructure.docx_format import DocxFormatService
from reportgen.infrastructure.docx_practice import (
    blank_line_before_captions,
    capital_section_headings,
    city_at_page_bottom,
    dash_lists,
    fit_pictures,
    flatten_subsections,
    frame_screenshots,
    insert_contents,
    keep_objects_inside_text,
    listings_to_appendices,
    number_objects_by_section,
    page_numbers_right,
    rename_conclusion,
    space_questions,
    start_sections_on_new_page,
    terminal_screenshots,
)

BODY = "Это обычный абзац основного текста отчёта, достаточно длинный, чтобы считаться текстом раздела."


def build(tmp_path: Path) -> Path:
    document = Document()
    document.add_paragraph("Минск 2026")
    document.add_heading("1 Цель работы", level=1)
    document.add_paragraph(BODY)
    document.add_heading("2 Задание", level=1)
    document.add_paragraph("создать приложение", style="List Bullet")
    document.add_paragraph("добавить обработку ошибок.", style="List Bullet")
    document.add_heading("3 Ход работы", level=1)
    document.add_heading("3.1 Настройка проекта", level=2)
    document.add_paragraph("Листинг 1 – Настройка приложения (app.js)")
    document.add_paragraph("const app = express();")
    document.add_paragraph("module.exports = app;")
    document.add_heading("3.2 Шаблоны", level=2)
    document.add_paragraph("Листинг 2 – Шаблон главной страницы")
    document.add_paragraph("<h1>Список</h1>")
    document.add_heading("5 Выводы", level=1)
    document.add_paragraph(BODY)
    path = tmp_path / "practice.docx"
    document.save(path)
    return path


def texts(document):
    return [p.text for p in document.paragraphs]


def test_every_first_level_heading_starts_a_new_page(tmp_path: Path):
    document = Document(build(tmp_path))
    assert start_sections_on_new_page(document) == 4
    headings = [p for p in document.paragraphs if p.style.name == "Heading 1"]
    assert all(p.paragraph_format.page_break_before for p in headings)


def test_conclusion_is_unnumbered_and_centered(tmp_path: Path):
    document = Document(build(tmp_path))
    assert rename_conclusion(document) == 1
    heading = next(p for p in document.paragraphs if p.text == "Заключение")
    assert heading.alignment == WD_ALIGN_PARAGRAPH.CENTER


def test_bullets_become_dash_items_with_semicolons_and_a_final_period(tmp_path: Path):
    document = Document(build(tmp_path))
    assert dash_lists(document) == 2
    items = [t for t in texts(document) if t.startswith("– ")]
    assert items == ["– создать приложение;", "– добавить обработку ошибок."]
    first = next(p for p in document.paragraphs if p.text.startswith("– создать"))
    assert first.style.name == "Normal"
    assert first.paragraph_format.left_indent.cm == 0


def test_contents_are_inserted_once_before_the_first_section(tmp_path: Path):
    document = Document(build(tmp_path))
    assert insert_contents(document) == 1
    assert insert_contents(document) == 0
    order = texts(document)
    assert order.index("СОДЕРЖАНИЕ") < order.index("1 Цель работы")
    assert 'o "1-1"' in " ".join(t.text for t in document.element.body.iter(qn("w:instrText")))
    instructions = [t.text for t in document.element.body.iter(qn("w:instrText"))]
    assert any("TOC" in text for text in instructions)


def test_city_is_anchored_to_the_bottom_margin(tmp_path: Path):
    document = Document(build(tmp_path))
    assert city_at_page_bottom(document) == 1
    frame = document.paragraphs[0]._p.pPr.find(qn("w:framePr"))
    assert frame.get(qn("w:yAlign")) == "bottom"


def test_each_listing_gets_its_own_appendix_with_italic_code(tmp_path: Path):
    document = Document(build(tmp_path))
    assert listings_to_appendices(document) == 2
    order = texts(document)
    assert "Приложение А\n(обязательное)\nНастройка приложения (app.js)" in order
    assert "Приложение Б\n(обязательное)\nШаблон главной страницы" in order
    assert not any(t.startswith("Листинг") for t in order)
    assert order.index("3.1 Настройка проекта") + 1 == order.index("3.2 Шаблоны")
    code = next(p for p in document.paragraphs if p.text == "const app = express();")
    assert all(run.italic for run in code.runs)
    assert round(code.paragraph_format.left_indent.cm, 2) == 1.25
    assert order.index("Приложение А\n(обязательное)\nНастройка приложения (app.js)") > order.index("5 Выводы")


def test_section_headings_look_capital_but_keep_their_text(tmp_path: Path):
    document = Document(build(tmp_path))
    assert capital_section_headings(document) == 4
    assert document.styles["Heading 1"].font.all_caps
    assert any(p.text == "1 Цель работы" for p in document.paragraphs)


def test_figures_and_tables_are_numbered_inside_the_section_and_references_follow(tmp_path: Path):
    document = Document()
    document.add_heading("3 Ход работы", level=1)
    document.add_paragraph("Главная страница показана на рисунке 1, форма на рисунках 1–2, данные в таблице 1.")
    document.add_paragraph("Рисунок 1 – Главная страница")
    document.add_paragraph("Рисунок 2 – Форма")
    document.add_paragraph("Таблица 1 – Результаты")
    assert number_objects_by_section(document) >= 4
    order = texts(document)
    assert "Рисунок 3.1 – Главная страница" in order
    assert "Рисунок 3.2 – Форма" in order
    assert "Таблица 3.1 – Результаты" in order
    assert "Главная страница показана на рисунке 3.1, форма на рисунках 3.1–3.2, данные в таблице 3.1." in order


def test_screenshots_get_a_frame_and_dark_terminal_becomes_light(tmp_path: Path):
    from PIL import Image

    dark = tmp_path / "dark.png"
    picture = Image.new("RGB", (400, 200), (12, 12, 12))
    for column in range(20, 120):
        picture.putpixel((column, 30), (255, 255, 255))
    picture.save(dark)
    document = Document()
    document.add_picture(str(dark))
    assert frame_screenshots(document) == 1
    assert frame_screenshots(document) == 0
    assert terminal_screenshots(document) == 1
    blob = next(r.target_part.blob for r in document.part.rels.values() if "image" in r.reltype)
    import io

    result = Image.open(io.BytesIO(blob))
    assert result.getpixel((1, 1))[0] > 200
    assert result.width < 200


def test_practice_option_runs_the_whole_layout(tmp_path: Path):
    output = tmp_path / "fixed.docx"
    DocxFormatService().fix(build(tmp_path), output, FixOptions(practice=True))
    order = texts(Document(output))
    assert "СОДЕРЖАНИЕ" in order and "Заключение" in order and any(t.startswith("Приложение А") for t in order)
    assert any(t.startswith("– ") for t in order)
    assert "1 Цель работы" in order


def test_wide_pictures_are_scaled_to_the_limit_keeping_proportions(tmp_path: Path):
    from docx.shared import Cm
    from PIL import Image

    image = tmp_path / "wide.png"
    Image.new("RGB", (1000, 600), (255, 255, 255)).save(image)
    document = Document()
    document.add_picture(str(image), width=Cm(16))
    assert fit_pictures(document) == 1
    shape = document.inline_shapes[0]
    assert round(shape.width.cm, 1) == 9.0
    assert round(shape.height.cm / shape.width.cm, 2) == 0.6


def test_subsections_are_removed_but_sections_stay(tmp_path: Path):
    document = Document(build(tmp_path))
    assert flatten_subsections(document) == 2
    order = texts(document)
    assert "3.1 Настройка проекта" not in order
    assert "3 Ход работы" in order


def test_page_numbers_are_aligned_right(tmp_path: Path):
    document = Document(build(tmp_path))
    document.sections[0].footer.paragraphs[0].text = "1"
    assert page_numbers_right(document) >= 1
    assert document.sections[0].footer.paragraphs[0].alignment == WD_ALIGN_PARAGRAPH.RIGHT


def test_figure_gets_a_blank_line_before_its_caption_and_text_stays_around_it(tmp_path: Path):
    from PIL import Image

    image = tmp_path / "shot.png"
    Image.new("RGB", (100, 60), (255, 255, 255)).save(image)
    document = Document()
    document.add_paragraph(BODY)
    document.add_picture(str(image))
    document.add_paragraph("Рисунок 3.1 – Главная страница")
    document.add_paragraph(BODY)
    assert blank_line_before_captions(document) == 1
    assert keep_objects_inside_text(document) >= 1
    caption = document.paragraphs[2]
    assert caption.paragraph_format.space_before.pt == 18
    assert document.paragraphs[0].paragraph_format.keep_with_next


def test_questions_are_separated_by_blank_lines(tmp_path: Path):
    document = Document()
    document.add_heading("4 Ответы", level=1)
    for number in (25, 26):
        document.add_paragraph().add_run(f"{number}. Как это работает?").bold = True
        document.add_paragraph(BODY)
    assert space_questions(document) == 1
    second = [p for p in document.paragraphs if p.text.startswith("26.")][0]
    assert second.paragraph_format.space_before.pt == 18


def test_code_nesting_becomes_paragraph_indent_and_appendix_title_is_not_all_capitals(tmp_path: Path):
    document = Document(build(tmp_path))
    from docx.shared import Cm  # noqa: F401

    assert listings_to_appendices(document) == 2
    nested = next(p for p in document.paragraphs if p.text == "const app = express();")
    assert round(nested.paragraph_format.left_indent.cm, 2) == 1.25
    heading = next(p for p in document.paragraphs if p.text.startswith("Приложение А"))
    assert [run.font.all_caps for run in heading.runs if run.text.strip()][0] is True
    assert all(not run.font.all_caps for run in heading.runs[1:] if run.text.strip())


def test_text_after_a_listing_stays_in_the_body_when_subsections_are_removed(tmp_path: Path):
    document = Document()
    document.add_heading("3 Ход работы", level=1)
    document.add_heading("3.1 Настройка", level=2)
    document.add_paragraph("Листинг 1 – Настройка приложения")
    document.add_paragraph("const app = express();")
    document.add_heading("3.2 Результаты", level=2)
    document.add_paragraph("Результаты работы описаны в этом абзаце основного текста отчёта, он не относится к коду.")
    document.add_heading("Выводы", level=1)
    path = tmp_path / "order.docx"
    document.save(path)
    output = tmp_path / "order_fixed.docx"
    DocxFormatService().fix(path, output, FixOptions(practice=True))
    order = texts(Document(output))
    appendix = next(i for i, t in enumerate(order) if t.startswith("Приложение А"))
    assert order.index("Результаты работы описаны в этом абзаце основного текста отчёта, он не относится к коду.") < appendix
