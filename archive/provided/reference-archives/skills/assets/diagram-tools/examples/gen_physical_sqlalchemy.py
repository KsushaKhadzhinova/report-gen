"""Генерация физической схемы БД (Graphviz) из метаданных схемы проекта.

Запуск из каталога проекта kufar_pars:
    DATABASE_URL=sqlite+aiosqlite:///:memory: BOT_TOKEN=x \
        .venv/bin/python <путь>/gen_physical.py > physical.dot
"""
from sqlalchemy import Enum
from sqlalchemy.dialects import postgresql
from core.database import Base
import core.models  # noqa: F401

DIALECT = postgresql.dialect()
GROUP_COLOR = {
    "users": "#2C5F8D", "tracked_products": "#2C5F8D", "listings": "#2C5F8D",
    "matches": "#B5820A", "sent_notifications": "#B5820A",
    "kufar_attributes": "#3C7D40", "kufar_attribute_values": "#3C7D40",
    "custom_attributes": "#6B4E9B", "price_references": "#6B4E9B",
}


def coltype(col):
    if isinstance(col.type, Enum):
        return "enum"
    return col.type.compile(dialect=DIALECT).split("(")[0].replace(
        " WITHOUT TIME ZONE", "").lower()


def flags(table, col):
    out = []
    if col.primary_key:
        out.append("PK")
    if col.foreign_keys:
        out.append("FK")
    if any(len(c.columns) == 1 and col in c.columns for c in table.constraints
           if c.__class__.__name__ == "UniqueConstraint"):
        out.append("UQ")
    if any(i.unique and list(i.columns) == [col] for i in table.indexes):
        out.append("UQ")
    if not col.nullable and not col.primary_key:
        out.append("NN")
    return " ".join(out)


print("digraph PHYSICAL {")
print('  rankdir=LR; bgcolor="white"; splines=spline; overlap=false;')
print("  graph [nodesep=0.9, ranksep=1.8];")
print('  node [shape=plaintext, fontname="Arial", fontsize=11];')
print('  edge [fontname="Arial", fontsize=10, color="#2C5F8D", penwidth=1.3];')

for table in Base.metadata.sorted_tables:
    color = GROUP_COLOR.get(table.name, "#555555")
    rows = [
        f'    <TR><TD COLSPAN="3" BGCOLOR="{color}">'
        f'<FONT COLOR="white"><B>{table.name}</B></FONT></TD></TR>'
    ]
    for col in table.columns:
        rows.append(
            f'    <TR><TD PORT="{col.name}" ALIGN="LEFT">{col.name}</TD>'
            f'<TD ALIGN="LEFT">{coltype(col)}</TD>'
            f'<TD ALIGN="LEFT">{flags(table, col)}</TD></TR>'
        )
    for constraint in table.constraints:
        if constraint.__class__.__name__ == "UniqueConstraint" and len(constraint.columns) > 1:
            cols = ", ".join(c.name for c in constraint.columns)
            rows.append(
                f'    <TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="#F2F2F2">'
                f'<FONT POINT-SIZE="9">UQ ({cols})</FONT></TD></TR>'
            )
    for index in sorted(table.indexes, key=lambda i: i.name):
        if len(index.columns) > 1:
            cols = ", ".join(c.name for c in index.columns)
            rows.append(
                f'    <TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="#F2F2F2">'
                f'<FONT POINT-SIZE="9">IDX ({cols})</FONT></TD></TR>'
            )
    body = "\n".join(rows)
    print(f"  {table.name} [label=<\n"
          f'   <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">\n'
          f"{body}\n   </TABLE>>];\n")

for table in Base.metadata.sorted_tables:
    for col in table.columns:
        for fk in col.foreign_keys:
            target = fk.column
            print(f"  {table.name}:{col.name} -> {target.table.name}:{target.name} "
                  f'[label="M:1"];')
print("}")
