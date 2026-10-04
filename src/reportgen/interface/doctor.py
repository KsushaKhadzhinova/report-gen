from __future__ import annotations

import importlib.util
import shutil

from reportgen.infrastructure.settings import get_provider


def checks() -> list[tuple[str, bool, str]]:
    provider = get_provider()
    results: list[tuple[str, bool, str]] = []

    needs_key = provider.name == "cloud" or provider.api_key is not None
    key_ok = bool(provider.api_key) or not needs_key
    hint = "" if key_ok else f"ключ не задан; получить: {provider.signup_url or 'у провайдера'}"
    results.append((f"Провайдер «{provider.name}»: {provider.description}", key_ok, hint))

    results.append(("xelatex или Docker для PDF", bool(shutil.which("xelatex") or shutil.which("docker")), "установите Docker или TeX Live"))
    results.append(("Graphviz (dot) для диаграмм", bool(shutil.which("dot")), "нужен для диаграмм .dot"))
    results.append(("PlantUML для диаграмм", bool(shutil.which("plantuml")), "нужен для диаграмм .puml"))
    results.append(("Playwright для веб-скриншотов", importlib.util.find_spec("playwright") is not None, "pip install 'report-gen[capture]'"))
    results.append(("pyautogui для окон рабочего стола", importlib.util.find_spec("pyautogui") is not None, "pip install 'report-gen[capture]'"))
    return results
