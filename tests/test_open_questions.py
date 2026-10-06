from reportgen.domain.blocks import Block, Kind
from reportgen.domain.open_questions import open_questions


def test_each_mark_becomes_a_question_with_its_section():
    blocks = [
        Block(Kind.HEADING, text="Введение", level=1),
        Block(Kind.PARAGRAPH, text="Система работает [УТОЧНИТЬ: количество пользователей]."),
        Block(Kind.HEADING, text="Результаты", level=1),
        Block(Kind.LIST, items=["Скорость [УТОЧНИТЬ: время ответа, мс]", "Точность"]),
        Block(Kind.PARAGRAPH, text="Без меток."),
    ]
    questions = open_questions(blocks)
    assert [str(q) for q in questions] == [
        "Введение: Количество пользователей?",
        "Результаты: Время ответа, мс?",
    ]


def test_mark_without_text_still_gives_a_question():
    blocks = [Block(Kind.PARAGRAPH, text="Данные [УТОЧНИТЬ] неизвестны.")]
    assert open_questions(blocks)[0].section == "без раздела"
