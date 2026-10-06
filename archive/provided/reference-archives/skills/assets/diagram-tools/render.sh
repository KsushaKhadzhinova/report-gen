#!/usr/bin/env bash
# Рендер исходника диаграммы в PDF и отчёт о читаемости.
#
#   render.sh <исходник> [доля_ширины_строки] [кегль_исходника_пт]
#
# Исходник: .puml (PlantUML), .dot (Graphviz), .svg (схемы алгоритмов из flowchart.py).
# Для .dot с закреплёнными координатами (pos="x,y!") используется neato -n2.
# Доля ширины строки -- аргумент width в \includegraphics (по умолчанию 1.0).
# Отчёт: размер диаграммы, шрифты в PDF, оценка кегля на странице.
set -euo pipefail

src="${1:?укажите исходник диаграммы}"
frac="${2:-1.0}"
font="${3:-}"
TEXTWIDTH_PT=467.7        # A4: 210 мм - поля 30 и 15 мм = 165 мм
TEXTHEIGHT_PT=708.0       # A4: 297 мм - поля 20 и 27 мм = 250 мм

dir="$(dirname "$src")"; base="$(basename "$src")"; name="${base%.*}"; ext="${base##*.}"
out="$dir/$name.pdf"

case "$ext" in
  puml)
    # через SVG: при прямом -tpdf PlantUML подставляет Helvetica вместо Arial
    plantuml -tsvg "$src"
    rsvg-convert -f pdf "$dir/$name.svg" -o "$out" ;;
  dot)
    if grep -q 'pos="[^"]*!"' "$src"; then neato -n2 -Tpdf "$src" -o "$out"
    else dot -Tpdf "$src" -o "$out"; fi ;;
  svg)  rsvg-convert -f pdf "$src" -o "$out" ;;
  *) echo "неизвестный тип исходника: $ext" >&2; exit 2 ;;
esac

[ -s "$out" ] || { echo "PDF не создан: $out" >&2; exit 1; }

read -r w h < <(pdfinfo "$out" | awk '/Page size/ {print $3, $5}')
echo "файл:    $out"
echo "размер:  ${w} x ${h} пт"
echo "шрифты:"; pdffonts "$out" | tail -n +3 | awk '{print "  " $1}' | sort -u

python3 - "$w" "$h" "$frac" "$font" "$TEXTWIDTH_PT" "$TEXTHEIGHT_PT" "$ext" <<'EOF'
import sys
w, h, frac, font, tw, th, ext = sys.argv[1:8]
w, h, frac, tw, th = float(w), float(h), float(frac), float(tw), float(th)
scale = min(frac * tw / w, th / h)          # рисунок не должен быть выше полосы
limit = "по ширине" if frac * tw / w <= th / h else "по высоте страницы"
print(f"масштаб на странице: {scale:.2f} ({limit})")
if scale > 1.05:
    print("  при такой ширине вставки рисунок будет растянут: уменьшите width в \\includegraphics")
if font:
    # в PlantUML кегль задаётся в пикселях SVG: 1 px = 0,75 пт
    onpage = float(font) * (0.75 if ext == "puml" else 1.0) * scale
    verdict = "читаемо" if onpage >= 9 else ("на грани" if onpage >= 7 else "МЕЛКО: перекомпоновать или разделить")
    print(f"кегль на странице: {onpage:.1f} пт ({verdict}; цель не ниже 9 пт)")
else:
    print("кегль исходника не задан: передайте третьим аргументом, чтобы получить оценку")
EOF

if pdffonts "$out" | tail -n +3 | grep -qvi 'arial'; then
  echo "ВНИМАНИЕ: в PDF есть шрифты кроме Arial" >&2
fi
