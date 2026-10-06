# -*- coding: utf-8 -*-
"""Проверка ER-диаграммы: наложения узлов и линии, проходящие сквозь чужие узлы.

    python3 check_er.py [файл.dot]      (по умолчанию er_chen.dot)

Раскладка читается из graphviz (neato -n2, координаты из pos берутся как есть).
Форма узла учитывается: прямоугольник сущности, ромб связи, эллипс атрибута.
Код возврата 0 -- нарушений нет, 1 -- есть.
"""
import math
import shlex
import subprocess
import sys

PAD = 0.03          # требуемый зазор между фигурами, дюймы
src = sys.argv[1] if len(sys.argv) > 1 else 'er_chen.dot'

plain = subprocess.run(['neato', '-n2', '-Tplain', src],
                       capture_output=True).stdout.decode()
nodes, edges = {}, []
for line in plain.splitlines():
    t = shlex.split(line)
    if t and t[0] == 'node':
        nodes[t[1]] = dict(x=float(t[2]), y=float(t[3]),
                           w=float(t[4]), h=float(t[5]), shape=t[8])
    elif t and t[0] == 'edge':
        edges.append((t[1], t[2]))
if not nodes:
    sys.exit(f'не удалось прочитать раскладку из {src}')


def inside(n, x, y, pad=0.0):
    """Лежит ли точка внутри фигуры узла, раздутой на pad."""
    a, b = n['w'] / 2 + pad, n['h'] / 2 + pad
    dx, dy = abs(x - n['x']), abs(y - n['y'])
    if n['shape'] == 'diamond':
        return dx / a + dy / b < 1
    if n['shape'] == 'ellipse':
        return (dx / a) ** 2 + (dy / b) ** 2 < 1
    return dx < a and dy < b


def outline(n, steps=72):
    """Точки контура фигуры."""
    a, b = n['w'] / 2, n['h'] / 2
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        c, s = math.cos(t), math.sin(t)
        if n['shape'] == 'ellipse':
            k = 1.0
        elif n['shape'] == 'diamond':
            k = 1 / (abs(c) + abs(s))
        else:
            k = 1 / max(abs(c), abs(s))
        if n['shape'] == 'diamond':
            pts.append((n['x'] + a * c * k, n['y'] + b * s * k))
        elif n['shape'] == 'ellipse':
            pts.append((n['x'] + a * c, n['y'] + b * s))
        else:
            pts.append((n['x'] + a * c * k, n['y'] + b * s * k))
    return pts


bad = 0
names = list(nodes)
linked = {frozenset(e) for e in edges}
for i, a in enumerate(names):
    for b in names[i + 1:]:
        A, B = nodes[a], nodes[b]
        hit = (any(inside(B, x, y, PAD) for x, y in outline(A)) or
               any(inside(A, x, y, PAD) for x, y in outline(B)))
        if hit:
            print(f'наложение: {a} и {b}')
            bad += 1

for a, b in edges:
    p, q = (nodes[a]['x'], nodes[a]['y']), (nodes[b]['x'], nodes[b]['y'])
    for name, n in nodes.items():
        if name in (a, b):
            continue
        for i in range(201):
            t = i / 200
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            if inside(n, x, y):
                print(f'линия {a}--{b} проходит через узел {name}')
                bad += 1
                break

print('нарушений нет' if not bad else f'нарушений: {bad}')
sys.exit(1 if bad else 0)
