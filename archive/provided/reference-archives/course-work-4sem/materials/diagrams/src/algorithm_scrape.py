# -*- coding: utf-8 -*-
"""Схема алгоритма цикла опроса площадки."""
from flowchart import Chart

c = Chart(ncols=3, col_w=118, col_gap=26, row_gap=9,
          left_margin=28, right_margin=28, font=9, lh=11, uniform=True)

L, C, R = 0, 1, 2

c.block("start",  C, 1, "start",    "Начало")
c.block("d0",     C, 2, "decision", "Пауза после отказа?")
c.block("sel",    C, 3, "process",  "Выбрать активные отслеживаемые товары")
c.block("dec",    R, 3, "process",  "Уменьшить счётчик пропускаемых циклов")
c.block("d1",     C, 4, "decision", "Остались товары?")
c.block("req",    C, 5, "process",  "Сформировать запрос к площадке")
c.block("commit", L, 5, "process",  "Зафиксировать транзакцию")
c.block("get",    C, 6, "data",     "Получить объявления")
c.block("d2",     C, 7, "decision", "Отказ площадки?")
c.block("proc",   C, 8, "process",  "Обработать полученные объявления")
c.block("pause",  R, 8, "process",  "Увеличить паузу, оповестить администратора")
c.block("end",    C, 9, "start",    "Конец")

c.gap_after(8, 30)
c.layout()
c.draw_blocks()

xl, xc, xr = c.colx
xfl, xfr = 13.0, c.width - 13.0
g34   = c.gapy(3, 4)
y_ret = c.gapy(8, 9, 0.28)      # возврат к началу цикла
y_end = c.gapy(8, 9, 0.70)      # сбор завершающих ветвей

# основная линия сверху вниз
c.line([c.bottom("start"), c.top("d0")])
c.line([c.bottom("d0"), c.top("sel")])
c.label(xc + 8, (c.bottom("d0")[1] + c.top("sel")[1]) / 2 + 3, "Нет", "start")
c.line([c.bottom("sel"), c.top("d1")])
c.line([c.bottom("d1"), c.top("req")])
c.label(xc + 8, (c.bottom("d1")[1] + c.top("req")[1]) / 2 + 3, "Да", "start")
c.line([c.bottom("req"), c.top("get")])
c.line([c.bottom("get"), c.top("d2")])
c.line([c.bottom("d2"), c.top("proc")])
c.label(xc + 8, (c.bottom("d2")[1] + c.top("proc")[1]) / 2 + 3, "Нет", "start")

# боковые ветви: линия входит в блок сверху
p = c.yes("d0", xr);  c.line([p, (xr, p[1]), c.top("dec")])
p = c.no("d1", xl);   c.line([p, (xl, p[1]), c.top("commit")])
p = c.yes("d2", xr);  c.line([p, (xr, p[1]), c.top("pause")])

# возврат к проверке «Остались товары?» -- одна стрелка при входе в линию
c.line([c.bottom("proc"), (xc, y_ret), (xfl, y_ret), (xfl, g34), (xc, g34)], arrow=True)

# завершающие ветви сходятся в одну линию, которая входит в «Конец» сверху
c.line([c.bottom("dec"), (xr, c.gapy(3, 4, 0.30)), (xfr, c.gapy(3, 4, 0.30)),
        (xfr, y_end), (xc, y_end)])
c.line([c.bottom("pause"), (xr, y_end)])
c.line([c.bottom("commit"), (xl, y_end), (xc, y_end)])
c.line([(xc, y_end), c.top("end")])

w, h = c.save("algorithm_scrape.svg")
print(f"scrape  {w:.0f} x {h:.0f} pt")
