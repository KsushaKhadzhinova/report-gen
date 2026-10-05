from pathlib import Path

from reportgen.application.write_report import ReportWriter, WritingContext
from reportgen.domain.markup import parse
from reportgen.domain.numbering import assign_numbers, resolve_figure_references
from reportgen.domain.structure import Section, Structure
from reportgen.infrastructure.prompt_library import load_prompt_catalog


class FakeModel:
    identity = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, role, system, user, temperature=0.6, max_tokens=None):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class NoStyle:
    def load(self):
        return None


class MemoryRepository:
    def __init__(self, sections):
        self.sections = dict(sections)
        self.root = Path(".")

    def read_section(self, section_id):
        return self.sections[section_id]

    def save_section(self, section_id, markdown):
        self.sections[section_id] = markdown

    def load_blocks(self):
        blocks = []
        for section_id in sorted(self.sections):
            blocks += parse(self.sections[section_id], f"{section_id}.md")
        assign_numbers(blocks)
        resolve_figure_references(blocks)
        return blocks


STRUCTURE = Structure("t", (Section("01_theory", "Теория", numbered=False, words=100),))
BROKEN = "# Теория {-}\n\nФормулы [УТОЧНИТЬ: какие формулы] приведены ниже.\n"
CONTEXT = WritingContext(facts="Проект использует Express.")


def make_writer(model):
    return ReportWriter(model, NoStyle(), load_prompt_catalog())


def quiet(_message):
    return None


def test_placeholder_is_removed_in_one_round():
    repository = MemoryRepository({"01_theory": BROKEN})
    model = FakeModel(["Теория строится на описании маршрутов Express."])
    remaining = make_writer(model).refine(STRUCTURE, repository, CONTEXT, progress=quiet)
    assert remaining == []
    assert "УТОЧНИТЬ" not in repository.sections["01_theory"]
    assert repository.sections["01_theory"].startswith("# Теория {-}")
    assert "УТОЧНИТЬ" in model.prompts[0]


def test_nothing_is_sent_to_the_model_when_text_is_clean():
    repository = MemoryRepository({"01_theory": "# Теория {-}\n\nЧистый текст без замечаний.\n"})
    model = FakeModel([])
    assert make_writer(model).refine(STRUCTURE, repository, CONTEXT, progress=quiet) == []
    assert model.prompts == []


def test_rounds_are_limited():
    repository = MemoryRepository({"01_theory": BROKEN})
    model = FakeModel(["Снова [УТОЧНИТЬ: что-то].", "И опять [УТОЧНИТЬ: другое]."])
    remaining = make_writer(model).refine(STRUCTURE, repository, CONTEXT, rounds=2, progress=quiet)
    assert len(model.prompts) == 2
    assert remaining and "Заглушка" in str(remaining[0])


def test_unavailable_model_keeps_the_previous_text():
    repository = MemoryRepository({"01_theory": BROKEN})
    model = FakeModel([RuntimeError("лимит"), RuntimeError("лимит")])
    remaining = make_writer(model).refine(STRUCTURE, repository, CONTEXT, progress=quiet)
    assert repository.sections["01_theory"] == BROKEN
    assert remaining


def test_figures_and_their_references_survive_a_revision():
    source = "# Теория {-}\n\nСхема на рисунке {fig:er} и пропуск [УТОЧНИТЬ: что].\n\n![ER-диаграмма](screenshots/er.png)\n"
    repository = MemoryRepository({"01_theory": source})
    model = FakeModel(["Схема приведена отдельно."])
    make_writer(model).refine(STRUCTURE, repository, CONTEXT, rounds=1, progress=quiet)
    saved = repository.sections["01_theory"]
    assert "![ER-диаграмма](screenshots/er.png)" in saved
    assert "{fig:er}" in saved


def test_reference_section_is_never_rewritten_by_the_model():
    structure = Structure("t", (Section("02_refs", "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", numbered=False, kind="references"),))
    repository = MemoryRepository({"02_refs": "# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ {-}\n\n[УТОЧНИТЬ: добавьте источники]\n"})
    model = FakeModel([])
    make_writer(model).refine(structure, repository, CONTEXT, progress=quiet)
    assert model.prompts == []
