#!/usr/bin/env bash
# Фиксация итерации работы над запиской: коммит делается только если PDF
# собирается и текст проходит автопроверку.
#
#   commit_iteration.sh -s <папка sources> -m "<что сделано>" [ключи] -- <путь> [<путь> ...]
#
#   -s <папка>        каталог с Makefile и note/ (обязательно)
#   -m "<текст>"      что сделано в итерации (обязательно)
#   -t "<строки>"     завершающие строки сообщения (например Co-Authored-By)
#   --max-overfull N  допустимое число Overfull \hbox (по умолчанию 0)
#   --local           сборка локальным latexmk без Docker
#   --skip-lint       не останавливать коммит из-за ошибок автопроверки текста
#   --dry-run         всё проверить и показать, что попало бы в коммит, но не коммитить
#   -- <пути>         что добавлять в коммит: папка записки, исходники диаграмм
#
# В коммит попадают только перечисленные пути. git add -A, push, amend
# и обход хуков не используются.
set -uo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
check="$here/../../build-check/scripts/check_build.sh"
lint="$here/../../text-lint/scripts/lint_tex.py"

src=""; msg=""; trailer=""; max_overfull=0; skip_lint=0; dry=0; build_args=()
while [ $# -gt 0 ]; do
  case "$1" in
    -s) src="$2"; shift 2 ;;
    -m) msg="$2"; shift 2 ;;
    -t) trailer="$2"; shift 2 ;;
    --max-overfull) max_overfull="$2"; shift 2 ;;
    --local) build_args+=(--local); shift ;;
    --skip-lint) skip_lint=1; shift ;;
    --dry-run) dry=1; shift ;;
    --) shift; break ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "неизвестный ключ: $1" >&2; exit 2 ;;
  esac
done
paths=("$@")

[ -n "$src" ] && [ -n "$msg" ] || { echo "нужны -s <папка sources> и -m \"<что сделано>\"" >&2; exit 2; }
[ "${#paths[@]}" -gt 0 ] || { echo "после -- укажите пути, которые войдут в коммит" >&2; exit 2; }
git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "ОТКАЗ: здесь нет git-репозитория" >&2; exit 1; }
if [ -d "$(git rev-parse --git-dir)/rebase-merge" ] || [ -f "$(git rev-parse --git-dir)/MERGE_HEAD" ]; then
  echo "ОТКАЗ: в репозитории идёт слияние или перебазирование" >&2; exit 1
fi

echo "== 1. Сборка PDF"
result="$("$check" "$src" --max-overfull "$max_overfull" "${build_args[@]}")"
rc=$?
echo "$result"
if [ "$rc" -ne 0 ]; then
  echo "ОТКАЗ: PDF не прошёл проверку, коммит не сделан. Исправьте сборку и повторите." >&2
  exit 1
fi
summary="$(printf '%s\n' "$result" | tail -n 1)"
pages="$(printf '%s' "$summary" | sed -n 's/.*pages=\([0-9]*\).*/\1/p')"
overfull="$(printf '%s' "$summary" | sed -n 's/.*overfull=\([0-9]*\).*/\1/p')"

echo "== 2. Автопроверка текста"
if [ -d "$src/note/sections" ]; then
  python3 "$lint" "$src/note/sections" --quiet-review
  lrc=$?
  if [ "$lrc" -ne 0 ] && [ "$skip_lint" -eq 0 ]; then
    echo "ОТКАЗ: автопроверка текста нашла ошибки, коммит не сделан. Исправьте их или повторите с --skip-lint, если пользователь согласен оставить." >&2
    exit 1
  fi
fi

echo "== 3. Состав коммита"
git add -- "${paths[@]}" || { echo "ОТКАЗ: git add не выполнен" >&2; exit 1; }
staged="$(git diff --cached --name-only -- "${paths[@]}")"
if [ -z "$staged" ]; then
  echo "Изменений в указанных путях нет, коммит не нужен."
  exit 0
fi
junk="$(printf '%s\n' "$staged" | grep -E '\.(aux|log|fls|fdb_latexmk|out|toc|synctex\.gz|bbl|blg)$|(^|/)__pycache__/' || true)"
if [ -n "$junk" ]; then
  echo "ОТКАЗ: в индекс попали сборочные файлы, добавьте их в .gitignore:" >&2
  printf '%s\n' "$junk" >&2
  git reset -q -- "${paths[@]}"
  exit 1
fi
git diff --cached --stat -- "${paths[@]}"

full="записка: $msg (${pages} стр., Overfull ${overfull})"
[ -n "$trailer" ] && full="$full"$'\n\n'"$trailer"

if [ "$dry" -eq 1 ]; then
  echo "== пробный запуск: коммит не сделан. Сообщение было бы:"
  printf '%s\n' "$full"
  git reset -q -- "${paths[@]}"
  exit 0
fi

# только перечисленные пути: чужие подготовленные изменения в коммит не попадут
git commit -q -m "$full" -- "${paths[@]}" || { echo "ОТКАЗ: git commit не выполнен" >&2; exit 1; }
echo "== Готово: $(git log -1 --format='%h %s')"
