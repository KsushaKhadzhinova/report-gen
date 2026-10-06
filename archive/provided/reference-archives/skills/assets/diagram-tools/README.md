# Инструменты диаграмм

| Файл | Назначение |
|---|---|
| `flowchart.py` | Генератор схем алгоритмов по СТП 3.12 (ГОСТ 19.701-90). Правила оформления зашиты в код. |
| `check_er.py` | Проверка ER-диаграммы: наложения узлов и линии, проходящие сквозь чужие узлы. Запуск из папки с `er_chen.dot`. |
| `render.sh` | Рендер `.puml`, `.dot`, `.svg` в PDF и отчёт: размер, шрифты, кегль на странице. |
| `examples/flowchart_single_column.py` | Эталон: одна колонка, две обходные ветви «Нет». |
| `examples/flowchart_loop.py` | Цикл с возвратом и боковыми блоками (режим `uniform`). |
| `examples/flowchart_branches.py` | Несколько ветвлений подряд с чередованием сторон. |
| `examples/gen_er_chen.py` | ER в нотации Чена с закреплёнными координатами. |
| `examples/gen_physical_sqlalchemy.py` | Физическая схема из метаданных SQLAlchemy (если проект на нём). |
| `examples/logical.dot` | Логическая схема БД. |
| `examples/usecase.puml` | Варианты использования: CRUDL, глаголы, без рамки системы. |
| `examples/classes_logic.puml`, `classes_data.puml` | Диаграммы классов без пакетов, реальные имена. |
| `examples/sequence_*.puml` | Диаграммы последовательности. |
| `examples/context.puml`, `architecture.puml` | Контекст (C4) и архитектура развёртывания. |

Примеры взяты из курсовой про Telegram-бота мониторинга объявлений. Содержимое в них нужно заменить своим, оформление (skinparam, шрифт, направление) оставить.

Примеры показывают оформление, а не предельный объём. По отчёту `render.sh` схемы алгоритмов, ER и диаграммы классов дают на странице 9 пт и больше. Примеры `usecase`, `context`, `architecture`, `logical` с исходным содержимым дают 5–7 пт: в новой работе делайте их компактнее (меньше блоков, короче подписи, переносы строк), чтобы выйти на цель.

Нужны: `python3` с `Pillow`, `plantuml`, `graphviz`, `rsvg-convert`, `poppler` (`pdfinfo`, `pdffonts`), шрифт Arial.

```bash
# схема алгоритма
cp flowchart.py examples/flowchart_loop.py <папка диаграмм>/ && cd <папка диаграмм>
python3 flowchart_loop.py                 # получится .svg
./render.sh algorithm_scrape.svg 1.0 9    # PDF и отчёт о читаемости

# ER
python3 gen_er_chen.py && python3 check_er.py && ./render.sh er_chen.dot 1.0 13
```
