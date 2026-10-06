# -*- coding: utf-8 -*-
"""Схема алгоритма доставки уведомлений."""
import sys
sys.dont_write_bytecode = True      # не создавать __pycache__ рядом с диаграммами
from flowchart import Chart

c = Chart(ncols=3, col_w=118, col_gap=26, row_gap=9,
          left_margin=28, right_margin=28, font=9, lh=11, uniform=True)

L, C, R = 0, 1, 2

c.block("start",  C, 1, "start",    "Начало")
c.block("sel",    C, 2, "process",  "Выбрать недоставленные совпадения из очереди")
c.block("d1",     C, 3, "decision", "Остались совпадения?")
c.block("d2",     C, 4, "decision", "Лимит исчерпан?")
c.block("commit", L, 4, "process",  "Зафиксировать транзакцию")
c.block("d3",     C, 5, "decision", "Цена ниже прежней?")
c.block("keep",   R, 5, "process",  "Оставить в очереди")
c.block("send",   C, 6, "data",     "Отправить уведомление в Telegram")
c.block("dup",    L, 6, "process",  "Закрыть совпадение как дубликат")
c.block("d4",     C, 7, "decision", "Сообщение принято?")
c.block("fail",   L, 8, "process",  "Увеличить число попыток, сохранить текст ошибки")
c.block("ok",     R, 8, "process",  "Отметить доставку, записать в журнал")
c.block("end",    C, 9, "start",    "Конец")

c.gap_after(8, 30)
c.layout()
c.draw_blocks()

xl, xc, xr = c.colx
xfl, xfr = 13.0, c.width - 13.0
g23   = c.gapy(2, 3)
y_ret = c.gapy(8, 9, 0.28)      # возврат к началу цикла
y_end = c.gapy(8, 9, 0.70)      # выход из цикла к «Конец»

# основная линия сверху вниз
c.line([c.bottom("start"), c.top("sel")])
c.line([c.bottom("sel"), c.top("d1")])
c.line([c.bottom("d1"), c.top("d2")])
c.label(xc + 8, (c.bottom("d1")[1] + c.top("d2")[1]) / 2 + 3, "Да", "start")
c.line([c.bottom("d2"), c.top("d3")])
c.label(xc + 8, (c.bottom("d2")[1] + c.top("d3")[1]) / 2 + 3, "Нет", "start")
c.line([c.bottom("d3"), c.top("send")])
c.label(xc + 8, (c.bottom("d3")[1] + c.top("send")[1]) / 2 + 3, "Да", "start")
c.line([c.bottom("send"), c.top("d4")])

# боковые ветви: линия входит в блок сверху
p = c.no("d1", xl);   c.line([p, (xl, p[1]), c.top("commit")])
p = c.yes("d2", xr);  c.line([p, (xr, p[1]), c.top("keep")])
p = c.no("d3", xl);   c.line([p, (xl, p[1]), c.top("dup")])
p = c.yes("d4", xr);  c.line([p, (xr, p[1]), c.top("ok")])
p = c.no("d4", xl);   c.line([p, (xl, p[1]), c.top("fail")])

# возврат к проверке «Остались совпадения?» -- общая линия справа, одна стрелка
c.line([c.bottom("ok"), (xr, y_ret), (xfr, y_ret), (xfr, g23), (xc, g23)], arrow=True)
c.line([c.bottom("keep"), (xr, c.gapy(5, 6, 0.30)), (xfr, c.gapy(5, 6, 0.30))])
c.line([c.bottom("dup"), (xl, c.gapy(6, 7, 0.30)), (xfr, c.gapy(6, 7, 0.30))])
c.line([c.bottom("fail"), (xl, y_ret), (xr, y_ret)])

# выход из цикла: одна линия входит в «Конец» сверху
c.line([c.bottom("commit"), (xl, c.gapy(4, 5, 0.30)), (xfl, c.gapy(4, 5, 0.30)),
        (xfl, y_end), (xc, y_end)])
c.line([(xc, y_end), c.top("end")])

w, h = c.save("algorithm_deliver.svg")
print(f"deliver {w:.0f} x {h:.0f} pt")
