# -*- coding: utf-8 -*-
"""Схема алгоритма обработки полученного объявления."""
from flowchart import Chart

c = Chart(ncols=1, col_w=160, col_gap=0, row_gap=17,
          left_margin=132, right_margin=20, font=9.5, lh=11.5)

M = 0

c.block("start", M, 1, "start",    "Начало")
c.block("find",  M, 2, "process",  "Найти объявление в базе данных по площадке и внешнему идентификатору")
c.block("save",  M, 3, "process",  "Добавить или обновить объявление, сохранить прежнюю цену")
c.block("d1",    M, 4, "decision", "Подходит по критериям?")
c.block("d2",    M, 5, "decision", "Новое или подешевело?")
c.block("match", M, 6, "process",  "Создать совпадение со статусом «не доставлено»")
c.block("end",   M, 7, "start",    "Конец")

c.gap_after(6, 26)
c.layout()
c.draw_blocks()

xc = c.colx[0]
x_out, x_in = 20.0, 72.0        # две полосы для ветвей «Нет»
y_in  = c.gapy(6, 7, 0.38)
y_out = c.gapy(6, 7, 0.74)

c.line([c.bottom("start"), c.top("find")])
c.line([c.bottom("find"), c.top("save")])
c.line([c.bottom("save"), c.top("d1")])
c.line([c.bottom("d1"), c.top("d2")])
c.label(xc + 9, (c.bottom("d1")[1] + c.top("d2")[1]) / 2 + 3, "Да", "start")
c.line([c.bottom("d2"), c.top("match")])
c.label(xc + 9, (c.bottom("d2")[1] + c.top("match")[1]) / 2 + 3, "Да", "start")
c.line([c.bottom("match"), c.top("end")])

# ветви «Нет» обходят создание совпадения и ведут к «Конец»
p = c.no("d1", x_out)
c.line([p, (x_out, p[1]), (x_out, y_out), (xc, y_out)], arrow=True)
p = c.no("d2", x_in)
c.line([p, (x_in, p[1]), (x_in, y_in), (xc, y_in)], arrow=True)

w, h = c.save("algorithm_listing.svg")
print(f"listing {w:.0f} x {h:.0f} pt")
