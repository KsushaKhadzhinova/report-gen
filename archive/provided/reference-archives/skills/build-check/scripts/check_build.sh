#!/usr/bin/env bash
# Проверка, что пояснительная записка собирается в корректный PDF.
#
#   check_build.sh <папка sources> [--max-overfull N] [--no-clean] [--local]
#
# <папка sources> -- каталог, где лежат Makefile и подкаталог note/ с note.tex.
# --max-overfull N  допустимое число «Overfull \hbox» (по умолчанию 0)
# --no-clean        не сбрасывать кеш latexmk (быстрее, но замена картинок
#                   может остаться незамеченной)
# --local           собирать локальным latexmk без Docker
#
# Код возврата: 0 -- PDF собран и прошёл все проверки, 1 -- нет.
# Последняя строка вывода: «OK pages=N overfull=N warnings=N» либо «FAIL: причины».
set -uo pipefail

src=""; max_overfull=0; clean=1; local_build=0
while [ $# -gt 0 ]; do
  case "$1" in
    --max-overfull) max_overfull="$2"; shift 2 ;;
    --no-clean) clean=0; shift ;;
    --local) local_build=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) src="$1"; shift ;;
  esac
done
[ -n "$src" ] || { echo "FAIL: не указана папка sources"; exit 1; }
cd "$src" || { echo "FAIL: нет папки $src"; exit 1; }
[ -f note/note.tex ] || { echo "FAIL: не найден note/note.tex в $(pwd)"; exit 1; }

log=build.log
marker="$(mktemp)"
trap 'rm -f "$marker"' EXIT

if [ "$clean" -eq 1 ]; then
  # Makefile зависит только от note/*.tex, а latexmk сравнивает содержимое
  # файлов: без сброса кеша подмена рисунка или раздела в sections/ не видна.
  rm -f note.pdf note/note.pdf note/note.fdb_latexmk note/note.aux note/note.toc note/note.out
fi

if [ "$local_build" -eq 1 ]; then
  ( cd note && latexmk -pdf \
      -pdflatex='pdflatex -shell-escape -interaction=nonstopmode -synctex=1 %O %S' \
      note.tex ) > "$log" 2>&1
  rc=$?
  [ -f note/note.pdf ] && cp note/note.pdf .
else
  if ! command -v docker >/dev/null 2>&1; then
    echo "FAIL: docker не найден. Установите Docker или запустите с ключом --local"; exit 1
  fi
  if ! docker image inspect neitex:latex >/dev/null 2>&1; then
    echo "FAIL: нет образа neitex:latex. Соберите его один раз: (cd $(pwd) && docker build -t neitex:latex .)"; exit 1
  fi
  timeout 900 make all > "$log" 2>&1
  rc=$?
fi

fail=()
[ "$rc" -eq 0 ] || fail+=("сборка завершилась с кодом $rc (см. $(pwd)/$log)")

if [ ! -s note.pdf ]; then
  fail+=("note.pdf не создан")
  pages=0
else
  [ note.pdf -nt "$marker" ] || fail+=("note.pdf не обновился при сборке")
  pages="$(pdfinfo note.pdf 2>/dev/null | awk '/^Pages:/ {print $2}')"
  [ "${pages:-0}" -gt 0 ] 2>/dev/null || { fail+=("note.pdf повреждён: pdfinfo не читает страницы"); pages=0; }
fi

texlog=note/note.log
overfull=0; warnings=0
if [ -f "$texlog" ]; then
  errs="$(grep -a -c '^!' "$texlog")"
  if [ "$errs" -gt 0 ]; then
    fail+=("ошибок LaTeX: $errs")
    grep -a -n -A2 '^!' "$texlog" | head -20
  fi
  undef="$(grep -a -c -E 'Reference .* undefined|Citation .* undefined|There were undefined references' "$texlog")"
  if [ "$undef" -gt 0 ]; then
    fail+=("неразрешённые ссылки: $undef")
    grep -a -E 'Reference .* undefined|Citation .* undefined' "$texlog" | sort -u | head -20
  fi
  missing="$(grep -a -c -E 'File .* not found|No file .*\.(tex|pdf|png)' "$texlog")"
  [ "$missing" -eq 0 ] || { fail+=("не найдены файлы: $missing"); grep -a -E 'File .* not found' "$texlog" | sort -u | head -10; }
  overfull="$(grep -a -c 'Overfull \\hbox' "$texlog")"
  if [ "$overfull" -gt "$max_overfull" ]; then
    fail+=("Overfull \\hbox: $overfull (допустимо $max_overfull)")
    grep -a -A1 'Overfull \\hbox' "$texlog" | head -20
  fi
  warnings="$(grep -a -c 'Warning' "$texlog")"
else
  fail+=("нет файла $texlog")
fi

if [ "${#fail[@]}" -eq 0 ]; then
  echo "OK pages=$pages overfull=$overfull warnings=$warnings"
  exit 0
fi
IFS=';'; echo "FAIL: ${fail[*]}"
exit 1
