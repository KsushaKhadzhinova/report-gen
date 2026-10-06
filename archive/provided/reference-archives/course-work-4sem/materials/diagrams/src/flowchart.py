# -*- coding: utf-8 -*-
"""Генератор схем алгоритмов по ГОСТ 19.701-90 (СТП, подраздел 3.12).

Правила, заложенные в генератор:
  * единица SVG = 1 пункт, толщина всех линий и контуров одинакова (1,5 пт = 2 px);
  * шрифт Arial без курсива;
  * все блоки одной ширины; при uniform=True высота тоже общая,
    а «Начало» и «Конец» вдвое ниже остальных блоков;
  * линия входит в блок сверху, а не сбоку;
  * линии потока строятся только из горизонтальных и вертикальных отрезков;
  * «Начало» -- вверху по центру, «Конец» -- один, внизу по центру;
  * возвраты и переходы показаны линиями со стрелками (СТП, рисунок 3.33);
    линии могут пересекаться и сливаться, точка в месте пересечения
    не ставится;
  * из правого угла ромба выходит «Да», из левого -- «Нет».
"""

from __future__ import annotations

import html
from PIL import ImageFont

FONT_FILE = "/home/gudi/.local/share/fonts/Arial.ttf"
STROKE = 1.5          # пт; 2 px при 96 dpi
ARROW_LEN = 8.0
ARROW_HALF = 30.0     # половина развала 60 градусов


class Chart:
    def __init__(self, ncols, col_w=126, col_gap=30, row_gap=26,
                 left_margin=34, right_margin=34, top_margin=12, bottom_margin=12,
                 font=10.5, lh=12.5, uniform=False):
        self.uniform = uniform
        self.ncols = ncols
        self.col_w = col_w
        self.col_gap = col_gap
        self.row_gap = row_gap
        self.left_margin = left_margin
        self.right_margin = right_margin
        self.top_margin = top_margin
        self.bottom_margin = bottom_margin
        self.font = font
        self.lh = lh
        self.fnt = ImageFont.truetype(FONT_FILE, int(round(font * 4)))  # x4 для точности
        self.blocks = {}
        self.rows = {}          # row -> height
        self.rowy = {}          # row -> y центра
        self.extra_gap = {}     # (r1, r2) -> добавка к промежутку
        self.items = []         # готовые фрагменты svg
        self.colx = [left_margin + col_w / 2 + i * (col_w + col_gap)
                     for i in range(ncols)]
        self.width = left_margin + ncols * col_w + (ncols - 1) * col_gap + right_margin
        self.height = 0

    # ------------------------------------------------------------------ текст
    def _tw(self, s):
        return self.fnt.getlength(s) / 4.0

    def _wrap(self, text, maxw):
        out = []
        for para in text.split("\n"):
            words, line = para.split(), ""
            for w in words:
                trial = (line + " " + w).strip()
                if line and self._tw(trial) > maxw:
                    out.append(line)
                    line = w
                else:
                    line = trial
            out.append(line)
        return out

    # ---------------------------------------------------------------- блоки
    def block(self, key, col, row, kind, text, x=None):
        """kind: start | process | decision | data | connector.

        x -- явная координата центра вместо центра колонки (для соединителей,
        которые стоят в узкой полосе за крайней колонкой).
        """
        w = self.col_w
        if kind == "connector":
            d = max(24.0, 2.4 * self.font)
            self.blocks[key] = dict(col=col, row=row, kind=kind, lines=[text],
                                    w=d, h=d, xfix=x)
            self.rows[row] = max(self.rows.get(row, 0), d)
            return key
        if kind == "decision":
            lines = self._wrap(text, 0.56 * w)
            th = len(lines) * self.lh
            h = (th + 6) / 0.44
        elif kind == "data":
            lines = self._wrap(text, w - 2 * 0.30 * 34 - 16)
            h = len(lines) * self.lh + 18
        else:
            lines = self._wrap(text, w - 18)
            h = len(lines) * self.lh + 18
        h = max(h, 30)
        self.blocks[key] = dict(col=col, row=row, kind=kind, lines=lines,
                                w=w, h=h, xfix=x)
        self.rows[row] = max(self.rows.get(row, 0), h)
        return key

    def gap_after(self, row, extra):
        self.extra_gap[row] = self.extra_gap.get(row, 0) + extra

    def layout(self):
        if self.uniform:
            # общая высота по самому высокому блоку; терминаторы вдвое ниже
            big = max(b["h"] for b in self.blocks.values()
                      if b["kind"] not in ("start", "connector"))
            self.rows = {}
            for b in self.blocks.values():
                if b["kind"] == "start":
                    b["h"] = big / 2
                elif b["kind"] != "connector":
                    b["h"] = big
                self.rows[b["row"]] = max(self.rows.get(b["row"], 0), b["h"])
        y = self.top_margin
        for r in sorted(self.rows):
            h = self.rows[r]
            self.rowy[r] = y + h / 2
            y += h + self.row_gap + self.extra_gap.get(r, 0)
        self.height = y - self.row_gap + self.bottom_margin
        for b in self.blocks.values():
            b["x"] = b["xfix"] if b["xfix"] is not None else self.colx[b["col"]]
            b["y"] = self.rowy[b["row"]]

    # --------------------------------------------------------------- порты
    def x(self, key):
        return self.blocks[key]["x"]

    def y(self, key):
        return self.blocks[key]["y"]

    def top(self, key):
        b = self.blocks[key]
        return (b["x"], b["y"] - b["h"] / 2)

    def bottom(self, key):
        b = self.blocks[key]
        return (b["x"], b["y"] + b["h"] / 2)

    def left(self, key):
        b = self.blocks[key]
        return (b["x"] - b["w"] / 2, b["y"])

    def right(self, key):
        b = self.blocks[key]
        return (b["x"] + b["w"] / 2, b["y"])

    def gapy(self, r1, r2, frac=0.5):
        """Точка в промежутке между строками r1 и r2."""
        b1 = self.rowy[r1] + self.rows[r1] / 2
        b2 = self.rowy[r2] - self.rows[r2] / 2
        return b1 + (b2 - b1) * frac

    def lane_left(self, col, off=0.0):
        return self.colx[col] - self.col_w / 2 - self.col_gap / 2 - off

    def lane_right(self, col, off=0.0):
        return self.colx[col] + self.col_w / 2 + self.col_gap / 2 + off

    # ---------------------------------------------------------------- рисование
    def _add(self, s):
        self.items.append(s)

    def draw_blocks(self):
        for b in self.blocks.values():
            x, y, w, h, k = b["x"], b["y"], b["w"], b["h"], b["kind"]
            st = f'fill="none" stroke="black" stroke-width="{STROKE}"'
            if k == "start":
                self._add(f'<rect x="{x-w/2:.2f}" y="{y-h/2:.2f}" width="{w:.2f}" '
                          f'height="{h:.2f}" rx="{h/2:.2f}" ry="{h/2:.2f}" {st}/>')
            elif k == "process":
                self._add(f'<rect x="{x-w/2:.2f}" y="{y-h/2:.2f}" width="{w:.2f}" '
                          f'height="{h:.2f}" {st}/>')
            elif k == "decision":
                pts = f"{x:.2f},{y-h/2:.2f} {x+w/2:.2f},{y:.2f} {x:.2f},{y+h/2:.2f} {x-w/2:.2f},{y:.2f}"
                self._add(f'<polygon points="{pts}" {st}/>')
            elif k == "connector":
                self._add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{w/2:.2f}" {st}/>')
            elif k == "data":
                s = 0.30 * h
                pts = (f"{x-w/2+s:.2f},{y-h/2:.2f} {x+w/2:.2f},{y-h/2:.2f} "
                       f"{x+w/2-s:.2f},{y+h/2:.2f} {x-w/2:.2f},{y+h/2:.2f}")
                self._add(f'<polygon points="{pts}" {st}/>')
            self._text_block(x, y, b["lines"])

    def _text_block(self, cx, cy, lines):
        n = len(lines)
        y0 = cy - (n - 1) * self.lh / 2 + self.font * 0.35
        parts = [f'<text x="{cx:.2f}" y="{y0:.2f}" text-anchor="middle" '
                 f'font-family="Arial" font-size="{self.font}" fill="black">']
        for i, ln in enumerate(lines):
            dy = 0 if i == 0 else self.lh
            parts.append(f'<tspan x="{cx:.2f}" dy="{dy:.2f}">{html.escape(ln)}</tspan>')
        parts.append("</text>")
        self._add("".join(parts))

    def line(self, pts, arrow=False, mid=False):
        """Линия потока: только горизонтальные и вертикальные отрезки.

        arrow -- стрелка в конце линии, mid -- стрелка посередине самого
        длинного отрезка (для длинных возвратов, как на рисунке 3.33 СТП).
        """
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            assert abs(x1 - x2) < 0.01 or abs(y1 - y2) < 0.01, f"косой отрезок {pts}"
        d = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        self._add(f'<polyline points="{d}" fill="none" stroke="black" '
                  f'stroke-width="{STROKE}"/>')
        if arrow:
            self.arrow(pts[-2], pts[-1])
        if mid:
            seg = max(zip(pts, pts[1:]),
                      key=lambda ab: abs(ab[0][0] - ab[1][0]) + abs(ab[0][1] - ab[1][1]))
            self.mid_arrow(*seg)

    def arrow(self, p_from, p_to):
        """Открытая стрелка с развалом 60 градусов (СТП, пункт 3.12.2)."""
        import math
        x1, y1 = p_from
        x2, y2 = p_to
        ang = math.atan2(y2 - y1, x2 - x1)
        for side in (+1, -1):
            a = ang + math.pi + side * math.radians(ARROW_HALF)
            self._add(f'<line x1="{x2:.2f}" y1="{y2:.2f}" '
                      f'x2="{x2 + ARROW_LEN*math.cos(a):.2f}" '
                      f'y2="{y2 + ARROW_LEN*math.sin(a):.2f}" '
                      f'stroke="black" stroke-width="{STROKE}" stroke-linecap="round"/>')

    def mid_arrow(self, p1, p2):
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = (dx ** 2 + dy ** 2) ** 0.5
        self.arrow((mx - dx / n * 6, my - dy / n * 6), (mx, my))

    def label(self, x, y, text, anchor="middle"):
        self._add(f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" '
                  f'font-family="Arial" font-size="{self.font}" fill="black">'
                  f'{html.escape(text)}</text>')

    # ------------------------------------------------------- ветвления ромба
    def yes(self, key, to_x, label_gap=4):
        """Линия из правого угла ромба с подписью «Да». Возвращает точку конца."""
        x0, y0 = self.right(key)
        self.label((x0 + to_x) / 2, y0 - label_gap, "Да")
        return (x0, y0)

    def no(self, key, to_x, label_gap=4):
        x0, y0 = self.left(key)
        self.label((x0 + to_x) / 2, y0 - label_gap, "Нет")
        return (x0, y0)

    # ----------------------------------------------------------------- вывод
    def save(self, path):
        body = "\n".join(self.items)
        svg = (f'<?xml version="1.0" encoding="UTF-8"?>\n'
               f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
               f'width="{self.width:.2f}pt" height="{self.height:.2f}pt" '
               f'viewBox="0 0 {self.width:.2f} {self.height:.2f}">\n'
               f'<rect width="{self.width:.2f}" height="{self.height:.2f}" fill="white"/>\n'
               f'{body}\n</svg>\n')
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        return self.width, self.height
