from pathlib import Path

import pytest

from reportgen.application.build_report import EmptyReportError, build_report
from reportgen.application.capture_screens import capture_all
from reportgen.application.write_report import ReportWriter, WritingContext
from reportgen.domain.markup import parse
from reportgen.domain.overlap import index_references
from reportgen.domain.structure import Section, Structure
from reportgen.infrastructure.prompt_library import load_prompt_catalog


class FakeModel:
    identity = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, role, system, user, temperature=0.6, max_tokens=None):
        self.calls.append(role)
        return self.replies.pop(0)


class FakeStyleStore:
    def load(self):
        return None


class MemoryRepository:
    def __init__(self, figures=None):
        self.sections, self.fingerprints = {}, {}
        self.figures = figures or {}
        self.root = Path(".")

    def read_meta(self):
        return {}

    def read_brief(self):
        return ""

    def read_sources(self):
        return ["1. Источник один", "Источник два"]

    def figure_captions(self):
        return self.figures

    def save_section(self, section_id, markdown):
        self.sections[section_id] = markdown

    def section_exists(self, section_id):
        return section_id in self.sections

    def cached_fingerprint(self, section_id):
        return self.fingerprints.get(section_id)

    def store_fingerprint(self, section_id, fingerprint):
        self.fingerprints[section_id] = fingerprint

    def load_blocks(self):
        return parse("# ВВЕДЕНИЕ {-}\n\nТекст.\n")


def intro_and_references():
    return Structure(
        "t",
        (
            Section("01_intro", "ВВЕДЕНИЕ", numbered=False, words=100, guide="Актуальность"),
            Section("02_refs", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", numbered=False, kind="references"),
        ),
    )


def quiet(_message):
    return None


def test_writer_generates_sections_and_formats_references():
    repository = MemoryRepository()
    writer = ReportWriter(FakeModel(["## Заголовок\n\n**Текст** введения."]), FakeStyleStore(), load_prompt_catalog())
    writer.write(intro_and_references(), repository, WritingContext(), progress=quiet)
    assert repository.sections["01_intro"].startswith("# ВВЕДЕНИЕ {-}")
    assert "Текст введения." in repository.sections["01_intro"]
    assert "1 Источник один" in repository.sections["02_refs"]
    assert "2 Источник два" in repository.sections["02_refs"]


def test_writer_skips_unchanged_sections():
    repository = MemoryRepository()
    model = FakeModel(["Первый вариант текста."])
    writer = ReportWriter(model, FakeStyleStore(), load_prompt_catalog())
    writer.write(intro_and_references(), repository, WritingContext(), progress=quiet)
    status = writer.write(intro_and_references(), repository, WritingContext(), progress=quiet)
    assert status["01_intro"] == "без изменений"
    assert model.calls == ["writer"]


def test_writer_regenerates_when_context_changes():
    repository = MemoryRepository()
    model = FakeModel(["Первый.", "Второй."])
    writer = ReportWriter(model, FakeStyleStore(), load_prompt_catalog())
    writer.write(intro_and_references(), repository, WritingContext(facts="а"), progress=quiet)
    writer.write(intro_and_references(), repository, WritingContext(facts="б"), progress=quiet)
    assert model.calls == ["writer", "writer"]


def test_writer_adds_figures_and_references_to_them():
    repository = MemoryRepository(figures={"er": "ER-диаграмма"})
    section = Section("01", "Проектирование", level=2, words=100, figures=("er",))
    writer = ReportWriter(FakeModel(["Текст без ссылки."]), FakeStyleStore(), load_prompt_catalog())
    writer.write(Structure("t", (section,)), repository, WritingContext(), progress=quiet)
    text = repository.sections["01"]
    assert "{fig:er}" in text
    assert "![ER-диаграмма](screenshots/er.png)" in text


def test_writer_rewrites_paragraphs_that_overlap_references():
    copied = "Система предназначена для автоматизации учёта заказов и позволяет формировать отчёты по продажам за выбранный период"
    library = type("Library", (), {"documents": lambda self: index_references([("old.docx", copied)])})()
    model = FakeModel([copied, "Совсем иная формулировка про учёт заказов и подготовку сводных документов по итогам продаж."])
    repository = MemoryRepository()
    writer = ReportWriter(model, FakeStyleStore(), load_prompt_catalog(), library)
    section = Section("01", "ВВЕДЕНИЕ", numbered=False, words=50)
    writer.write(Structure("t", (section,)), repository, WritingContext(), progress=quiet)
    assert model.calls == ["writer", "rewriter"]
    assert copied not in repository.sections["01"]


class RecordingRenderer:
    def render(self, blocks, meta, base_dir, output):
        return output


class RecordingCompiler:
    def compile(self, tex_file, destination):
        return destination


def test_build_dispatches_formats():
    renderers = {"docx": RecordingRenderer(), "tex": RecordingRenderer()}
    results = build_report(MemoryRepository(), renderers, RecordingCompiler())
    assert set(results) == {"docx", "tex", "pdf"}


def test_build_refuses_empty_report():
    repository = MemoryRepository()
    repository.load_blocks = lambda: []
    with pytest.raises(EmptyReportError):
        build_report(repository, {}, RecordingCompiler())


class FailingTaker:
    def take(self, item, target, project_root):
        raise RuntimeError("нет сервера")


class WorkingTaker:
    def take(self, item, target, project_root):
        target.write_bytes(b"png")


def test_capture_continues_after_failure(tmp_path):
    items = [{"kind": "web", "name": "a"}, {"kind": "console", "name": "b"}, {"kind": "unknown", "name": "c"}]
    results = capture_all(items, {"web": FailingTaker(), "console": WorkingTaker()}, tmp_path, tmp_path)
    assert [r.ok for r in results] == [False, True, False]
    assert (tmp_path / "b.png").exists()
