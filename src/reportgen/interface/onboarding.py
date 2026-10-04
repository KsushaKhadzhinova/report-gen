from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from reportgen.application.learn_style import learn_style
from reportgen.infrastructure import settings
from reportgen.infrastructure.file_stores import FileStyleStore
from reportgen.infrastructure.readers import DocumentProseSource
from reportgen.interface import doctor

MARKER = ".onboarded"

INTRO = """\
Добро пожаловать в report-gen.

Программа собирает пояснительные записки и отчёты по СТП БГУИР и выдаёт три файла:
DOCX, LaTeX и PDF. Текст пишет языковая модель, оформление делает программа.

Как это работает:
  1. init     создаёт папку работы с шаблонами (сведения, источники, скриншоты);
  2. shots    снимает скриншоты приложения и диаграммы;
  3. write    пишет разделы по вашему проекту и заданию;
  4. lint     проверяет текст на соответствие СТП;
  5. build    собирает DOCX, TEX и PDF.
Всё одной командой: report-gen make <папка работы> --code <папка проекта>
"""


def is_first_run() -> bool:
    return not (settings.home() / MARKER).exists()


def mark_done() -> None:
    (settings.home() / MARKER).write_text("ok", encoding="utf-8")


def _ask(question: str, default: str = "") -> str:
    if not sys.stdin.isatty():
        return default
    answer = input(f"{question} ").strip()
    return answer or default


def _save_env(key: str, value: str) -> None:
    env_path = Path.cwd() / settings.ENV_FILE
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.is_file() else []
    lines = [l for l in lines if not l.startswith(f"{key}=")] + [f"{key}={value}"]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _setup_provider() -> None:
    provider = settings.get_provider()
    print(f"\nШаг 1. Языковая модель. Сейчас выбрано: «{provider.name}» ({provider.description}).")
    if provider.name != "cloud" or provider.api_key:
        return
    print(
        "Облачные модели бесплатны, но нужен ключ OpenRouter. Регистрация занимает минуту; "
        "создайте ключ на странице, которая сейчас откроется."
    )
    if _ask("Открыть страницу ключей в браузере? [Д/н]", "д").lower().startswith("д"):
        webbrowser.open(provider.signup_url)
    key = _ask("Вставьте ключ (Enter, чтобы пропустить):")
    if key:
        _save_env("OPENROUTER_API_KEY", key)
        print("Ключ сохранён в файле .env рядом с программой.")
    else:
        print("Без ключа можно переключиться на локальную модель: report-gen use local")


def _learn_style() -> None:
    print("\nШаг 2. Ваш стиль. Программа может изучить ваши прошлые работы и писать похоже.")
    folder = _ask("Путь к папке с вашими работами (Enter, чтобы пропустить):")
    if not folder:
        return
    try:
        profile = learn_style(DocumentProseSource(), Path(folder), FileStyleStore())
        print(f"Изучено документов: {len(profile.documents)}, абзацев: {profile.paragraphs}.")
    except (ValueError, OSError) as exc:
        print(f"Не удалось изучить работы: {exc}")


def run() -> None:
    print(INTRO)
    _setup_provider()
    _learn_style()
    print("\nШаг 3. Проверка окружения.")
    for name, ok, hint in doctor.checks():
        print(f"  [{'+' if ok else '-'}] {name}" + (f"  ({hint})" if not ok and hint else ""))
    print(
        "\nГотово. Создайте первую работу:\n"
        "  report-gen init моя-работа --title \"Тема работы\"\n"
        "  report-gen make моя-работа --code путь/к/проекту\n"
        "Справка по любой команде: report-gen <команда> --help"
    )
    mark_done()
