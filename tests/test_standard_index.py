from pathlib import Path

from reportgen.domain.standard_index import excerpt, parse_clauses
from reportgen.infrastructure.standard_store import FileStandardStore, IndexedStandard

PAGES = [
    "СОДЕРЖАНИЕ\n2.3 Основные правила изложения текста .......... 21\n",
    "2.3.5 Если перечисление простое, то каждый элемент записывают с новой строки,\nначиная со знака тире, а в конце ставят точку с запятой.\n"
    "2.3.12 В тексте числа от одного до девяти без единиц измерений\nследует писать словами, свыше девяти цифрами.\n"
    "2.5.5 Каждый рисунок сопровождают подрисуночной подписью, которая содержит\nслово Рисунок без сокращения и номер.\n"
    "5.1 Пример расчёта входного фильтра для учебной задачи по радиотехнике.\n",
]


def test_clauses_are_split_by_number_and_contents_lines_skipped():
    index = parse_clauses(PAGES)
    assert [c.number for c in index.clauses] == ["2.3.5", "2.3.12", "2.5.5"]
    assert "точку с запятой" in index.clauses[0].text


def test_non_normative_chapters_are_excluded():
    assert all(not c.number.startswith("5.") for c in parse_clauses(PAGES).clauses)


def test_search_returns_the_relevant_clause_first():
    index = parse_clauses(PAGES)
    assert index.search("как писать простое перечисление", 1)[0].number == "2.3.5"
    assert index.search("подпись под рисунком", 1)[0].number == "2.5.5"
    assert index.search("числа словами до девяти", 1)[0].number == "2.3.12"
    assert index.search("совсем посторонний запрос про космос") == []


def test_excerpts_carry_the_clause_number():
    source = IndexedStandard(parse_clauses(PAGES))
    assert source.excerpts("рисунок подпись", 1)[0].startswith("п. 2.5.5:")


def test_index_round_trips_through_the_store(tmp_path: Path):
    store = FileStandardStore(tmp_path / "index.json")
    assert store.load() is None and store.source() is None
    index = parse_clauses(PAGES)
    store.path.write_text(__import__("json").dumps(index.to_dict(), ensure_ascii=False), encoding="utf-8")
    assert store.load() == index
    assert excerpt(index.clauses[0]).startswith("п. 2.3.5")
