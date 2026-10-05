from reportgen.domain.lint_rules import check_blocks
from reportgen.domain.markup import parse
from reportgen.domain.numbering import assign_numbers


def issues_for(markdown: str) -> list[str]:
    blocks = parse(markdown, "doc.md")
    assign_numbers(blocks)
    return [str(issue) for issue in check_blocks(blocks)]


def has(messages: list[str], fragment: str) -> bool:
    return any(fragment in message for message in messages)


def test_long_introduction_is_flagged():
    long_text = " ".join(["слово"] * 700)
    assert has(issues_for(f"# ВВЕДЕНИЕ {{-}}\n\n{long_text}\n"), "не более двух страниц")
    assert not has(issues_for("# ВВЕДЕНИЕ {-}\n\nКороткое введение по теме работы.\n"), "не более двух страниц")


def test_long_conclusion_is_flagged():
    long_text = " ".join(["слово"] * 800)
    assert has(issues_for(f"# ЗАКЛЮЧЕНИЕ {{-}}\n\n{long_text}\n"), "Заключение")


def test_wikipedia_is_not_an_allowed_source():
    doc = "# Раздел\n\nФакт из источника [1].\n\n# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ {-}\n\n1 Википедия. Статья про систему.\n"
    assert has(issues_for(doc), "Википедию")


def test_citations_must_follow_first_use_order():
    doc = "# Раздел\n\nСначала [2], потом [1].\n\n# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ {-}\n\n1 Первый.\n\n2 Второй.\n"
    assert has(issues_for(doc), "порядке первых ссылок")


def test_citation_to_missing_source_is_an_error():
    doc = "# Раздел\n\nСсылка [5].\n\n# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ {-}\n\n1 Единственный.\n"
    assert has(issues_for(doc), "которых нет в списке")


def test_correct_references_pass():
    doc = "# Раздел\n\nПервый [1] и второй [2] источники.\n\n# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ {-}\n\n1 Первый.\n\n2 Второй.\n"
    messages = issues_for(doc)
    assert not has(messages, "порядке")
    assert not has(messages, "нет в списке")
    assert not has(messages, "без ссылок")


def test_uncited_appendix_is_flagged_and_cited_one_is_not():
    assert has(issues_for("# Раздел\n\nТекст.\n\n# Листинг {app}\n\nКод.\n"), "Нет ссылки на приложение А")
    assert not has(issues_for("# Раздел\n\nКод приведён в приложении А.\n\n# Листинг {app}\n\nКод.\n"), "Нет ссылки на приложение")


def test_preposition_before_number_with_unit_is_flagged():
    assert has(issues_for("# Раздел\n\nДвигатель мощностью в 600 Вт установлен.\n"), "не ставят «в»")
    assert not has(issues_for("# Раздел\n\nДвигатель мощностью 600 Вт установлен.\n"), "не ставят «в»")


def test_period_belongs_after_the_citation_bracket():
    assert has(issues_for("# Раздел\n\nСистема описана подробно. [3]\n"), "после скобки")
    assert not has(issues_for("# Раздел\n\nСистема описана подробно [3].\n"), "после скобки")


def test_long_dash_is_flagged():
    assert has(issues_for("# Раздел\n\nСистема — это набор модулей.\n"), "короткое")
