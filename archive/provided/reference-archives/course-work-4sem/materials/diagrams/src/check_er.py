# -*- coding: utf-8 -*-
"""Проверка ER-диаграммы: наложения узлов и линии, проходящие сквозь узлы."""
import subprocess, sys

plain = subprocess.run(['neato', '-n2', '-Tplain', 'er_chen.dot'],
                       capture_output=True).stdout.decode()
nodes, edges = {}, []
for line in plain.splitlines():
    t = line.split()
    if t and t[0] == 'node':
        nodes[t[1]] = dict(x=float(t[2]), y=float(t[3]),
                           w=float(t[4]), h=float(t[5]))
    elif t and t[0] == 'edge':
        edges.append((t[1], t[2]))

PAD = 0.04          # требуемый зазор, дюймы
bad = 0
names = list(nodes)
for i, a in enumerate(names):
    for b in names[i + 1:]:
        A, B = nodes[a], nodes[b]
        dx = abs(A['x'] - B['x']) - (A['w'] + B['w']) / 2
        dy = abs(A['y'] - B['y']) - (A['h'] + B['h']) / 2
        if dx < PAD and dy < PAD:
            print(f'наложение: {a} и {b}  (зазор по x {dx:+.2f}, по y {dy:+.2f})')
            bad += 1

def seg_box(p, q, box):
    """Пересекает ли отрезок прямоугольник узла (грубая, но достаточная проверка)."""
    x0, y0 = box['x'] - box['w'] / 2, box['y'] - box['h'] / 2
    x1, y1 = box['x'] + box['w'] / 2, box['y'] + box['h'] / 2
    for t in [i / 60 for i in range(61)]:
        x = p[0] + (q[0] - p[0]) * t
        y = p[1] + (q[1] - p[1]) * t
        if x0 + 0.02 < x < x1 - 0.02 and y0 + 0.02 < y < y1 - 0.02:
            return True
    return False

for a, b in edges:
    p = (nodes[a]['x'], nodes[a]['y'])
    q = (nodes[b]['x'], nodes[b]['y'])
    for n, box in nodes.items():
        if n in (a, b):
            continue
        if seg_box(p, q, box):
            print(f'линия {a}--{b} проходит через узел {n}')
            bad += 1

print('нарушений нет' if not bad else f'нарушений: {bad}')
sys.exit(1 if bad else 0)
