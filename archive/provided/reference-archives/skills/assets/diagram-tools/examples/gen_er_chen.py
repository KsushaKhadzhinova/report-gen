# -*- coding: utf-8 -*-
"""ER-диаграмма в нотации Питера Чена, подписи на русском.

Раскладка задана вручную и не пересчитывается graphviz: файл собирается
с ключом -n2, поэтому координаты pos (в пунктах) используются как есть.
Компоновка вертикальная и плотная -- так подписи на странице записки
остаются крупными. Координаты в коде заданы в дюймах, ось Y вверх.
"""
FS = 13          # кегль подписей
INCH = 72.0

ENT = [   # ключ, подпись, x, y
    ("attr",  "Атрибут\\nфильтра",       0.00,  9.94),
    ("val",   "Значение\\nатрибута",     0.00,  8.05),
    ("prod",  "Отслеживаемый\\nтовар",   0.00,  5.80),
    ("match", "Совпадение",              0.00,  3.19),
    ("sent",  "Уведомление",             0.00,  0.58),
    ("users", "Пользователь",           -3.25,  6.90),
    ("list",  "Объявление",             -3.25,  3.19),
]

REL = [   # ромбы связей
    ("R6", "имеет",            0.00,  9.00),
    ("R7", "уточняет",         0.00,  6.92),
    ("R2", "порождает",        0.00,  4.50),
    ("R4", "подтверждается",   0.00,  1.89),
    ("R1", "отслеживает",     -1.72,  6.35),
    ("R3", "входит в",        -1.72,  3.19),
]

ATTR = [  # ключ, подпись, x, y, первичный ключ
    ("a1", "идентификатор",               2.10, 10.30, True),
    ("a2", "код\\nзапроса",                2.10,  9.58, False),

    ("v1", "идентификатор",               2.10,  8.41, True),
    ("v2", "код\\nзначения",               2.10,  7.69, False),

    ("p1", "идентификатор",               2.10,  6.52, True),
    ("p2", "категория",                   2.10,  5.80, False),
    ("p3", "пороговая\\nцена",             2.10,  5.08, False),

    ("m1", "идентификатор",               2.10,  3.91, True),
    ("m2", "показатель\\nвыгоды",          2.10,  3.19, False),
    ("m3", "время\\nдоставки",             2.10,  2.47, False),

    ("s1", "идентификатор",               2.10,  1.30, True),
    ("s2", "цена при\\nотправке",          2.10,  0.58, False),
    ("s3", "дата\\nотправки",              2.10, -0.14, False),

    ("u1", "идентификатор",             -3.60,  5.90, True),
    ("u2", "идентификатор\\nTelegram",   -3.25,  7.90, False),
    ("u3", "электронная\\nпочта",        -4.85,  6.90, False),

    ("l1", "идентификатор",             -3.60,  2.20, True),
    ("l2", "внешний\\nидентификатор",    -3.25,  4.20, False),
    ("l3", "цена",                      -4.80,  3.19, False),
]

LINKS = [("attr", ["a1", "a2"]), ("val", ["v1", "v2"]),
         ("prod", ["p1", "p2", "p3"]), ("match", ["m1", "m2", "m3"]),
         ("sent", ["s1", "s2", "s3"]), ("users", ["u1", "u2", "u3"]),
         ("list", ["l1", "l2", "l3"])]

EDGES = [("attr",  "R6", "1", "val",   "N"),
         ("val",   "R7", "M", "prod",  "N"),
         ("prod",  "R2", "1", "match", "N"),
         ("match", "R4", "1", "sent",  "N"),
         ("users", "R1", "1", "prod",  "N"),
         ("list",  "R3", "1", "match", "N")]


def pos(x, y):
    return f'pos="{x*INCH:.1f},{y*INCH:.1f}!"'


out = ['graph ER {',
       '  bgcolor="white";',
       '  margin="0.04,0.04";',
       '  splines=true;',
       '  overlap=true;',
       f'  node [fontname="Arial", fontsize={FS}];',
       f'  edge [fontname="Arial", fontsize={FS}, color="#333333"];',
       '',
       '  // Сущности',
       '  node [shape=box, style="filled", fillcolor="#DCE9F7", color="#2C5F8D",',
       '        penwidth=1.4, margin="0.09,0.05"];']
for k, lab, x, y in ENT:
    out.append(f'  {k} [label="{lab}", {pos(x, y)}];')

out += ['', '  // Связи',
        '  node [shape=diamond, style="filled", fillcolor="#FCE8C8", color="#B5820A",',
        '        penwidth=1.4, height=0.60, width=1.70];']
for k, lab, x, y in REL:
    out.append(f'  {k} [label="{lab}", {pos(x, y)}];')

out += ['', '  // Ключевые атрибуты; полный состав приведён в тексте',
        '  node [shape=ellipse, style="filled", fillcolor="#E8F5E9", color="#3C7D40",',
        '        penwidth=1.1, height=0.34, margin="0.04,0.02"];']
for k, lab, x, y, pk in ATTR:
    text = f'<<u>{lab}</u>>'.replace("\\n", "<br/>") if pk else f'"{lab}"'
    out.append(f'  {k} [label={text}, {pos(x, y)}];')

out += ['', '  // Атрибуты -- сущности']
for ent, attrs in LINKS:
    out.append('  ' + ' '.join(f'{ent} -- {a};' for a in attrs))

out += ['', '  // Связи и мощность']
for a, r, ca, b, cb in EDGES:
    out.append(f'  {a} -- {r} [label="{ca}"];  {r} -- {b} [label="{cb}"];')
out.append('}')

open('er_chen.dot', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('er_chen.dot записан')
