from __future__ import annotations

import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import yaml
from PIL import Image, ImageDraw, ImageFont

from reportgen.application.capture_screens import CaptureResult, capture_all

FONT_CANDIDATES = (
    "consola.ttf",
    "DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
)
CONSOLE_WIDTH_CHARS = 100
CONSOLE_MAX_LINES = 40
CONSOLE_LINE_HEIGHT = 24
CONSOLE_FONT_SIZE = 18
CONSOLE_CHAR_WIDTH = 11
CONSOLE_PADDING = 20
DEFAULT_COMMAND_TIMEOUT = 120
DEFAULT_VIEWPORT = (1366, 768)
PAGE_LOAD_TIMEOUT_MS = 60000
SELECTOR_TIMEOUT_MS = 30000
APP_START_WAIT_SECONDS = 8


class CaptureError(RuntimeError):
    pass


def _console_font() -> ImageFont.ImageFont:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, CONSOLE_FONT_SIZE)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    lines = []
    for raw in text.splitlines():
        while len(raw) > width:
            lines.append(raw[:width])
            raw = raw[width:]
        lines.append(raw)
    return lines


def render_console(text: str, target: Path) -> Path:
    lines = _wrap(text, CONSOLE_WIDTH_CHARS)[-CONSOLE_MAX_LINES:]
    width = CONSOLE_WIDTH_CHARS * CONSOLE_CHAR_WIDTH + 2 * CONSOLE_PADDING
    height = max(1, len(lines)) * CONSOLE_LINE_HEIGHT + 2 * CONSOLE_PADDING
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    font = _console_font()
    for index, line in enumerate(lines):
        draw.text((CONSOLE_PADDING, CONSOLE_PADDING + index * CONSOLE_LINE_HEIGHT), line, fill=(20, 20, 20), font=font)
    image.save(target)
    return target


class ConsoleTaker:
    def take(self, item: dict, target: Path, project_root: Path) -> None:
        command = item["command"]
        result = subprocess.run(
            command,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=item.get("timeout", DEFAULT_COMMAND_TIMEOUT),
        )
        render_console(f"> {command}\n{result.stdout}{result.stderr}", target)


class WebTaker:
    def take(self, item: dict, target: Path, project_root: Path) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise CaptureError("Для веб-скриншотов установите playwright: pip install 'report-gen[capture]'") from error
        width, height = item.get("width", DEFAULT_VIEWPORT[0]), item.get("height", DEFAULT_VIEWPORT[1])
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(item["url"], wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT_MS)
            if item.get("wait_for"):
                page.wait_for_selector(item["wait_for"], timeout=SELECTOR_TIMEOUT_MS)
            self._perform_actions(page, item.get("actions", []))
            page.screenshot(path=str(target), full_page=item.get("full_page", False))
            browser.close()

    @staticmethod
    def _perform_actions(page, actions: list[dict]) -> None:
        for action in actions:
            if "click" in action:
                page.click(action["click"])
            elif "fill" in action:
                page.fill(action["fill"]["selector"], action["fill"]["value"])
            page.wait_for_load_state("networkidle")


class DesktopTaker:
    def take(self, item: dict, target: Path, project_root: Path) -> None:
        try:
            import pyautogui
        except ImportError as error:
            raise CaptureError("Для скриншотов окон установите pyautogui: pip install 'report-gen[capture]'") from error
        windows = pyautogui.getWindowsWithTitle(item["window"]) if item.get("window") and hasattr(pyautogui, "getWindowsWithTitle") else []
        if not windows:
            pyautogui.screenshot().save(target)
            return
        window = windows[0]
        window.activate()
        time.sleep(1)
        pyautogui.screenshot(region=(window.left, window.top, window.width, window.height)).save(target)


class DiagramTaker:
    def take(self, item: dict, target: Path, project_root: Path) -> None:
        source = project_root / item["source"]
        if source.suffix == ".dot":
            self._run(["dot", "-Tpng", "-Gdpi=150", str(source), "-o", str(target)], "Graphviz (dot)")
        elif source.suffix in {".puml", ".plantuml"}:
            self._run(["plantuml", "-tpng", "-o", str(target.parent.resolve()), str(source)], "PlantUML")
            produced = target.parent / f"{source.stem}.png"
            if produced != target:
                produced.replace(target)
        else:
            raise CaptureError(f"Неизвестный формат диаграммы: {source.suffix}")

    @staticmethod
    def _run(command: list[str], tool: str) -> None:
        if not shutil.which(command[0]):
            raise CaptureError(f"Не найден {tool}")
        subprocess.run(command, check=True)


TAKERS = {"web": WebTaker(), "console": ConsoleTaker(), "desktop": DesktopTaker(), "diagram": DiagramTaker()}


@contextmanager
def running_application(command: str | None, project_root: Path, wait_seconds: int) -> Iterator[None]:
    process = subprocess.Popen(command, shell=True, cwd=project_root) if command else None
    try:
        if process:
            time.sleep(wait_seconds)
        yield
    finally:
        if process:
            process.terminate()


def capture_project(project_root: Path) -> list[CaptureResult]:
    plan_file = project_root / "screens.yaml"
    if not plan_file.is_file():
        raise CaptureError(f"Не найден {plan_file}")
    plan = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or {}
    output_dir = project_root / "screenshots"
    output_dir.mkdir(exist_ok=True)
    with running_application(plan.get("start"), project_root, plan.get("start_wait", APP_START_WAIT_SECONDS)):
        results = capture_all(plan.get("items", []), TAKERS, output_dir, project_root)
    _write_index(output_dir, results)
    return results


def _write_index(output_dir: Path, results: list[CaptureResult]) -> None:
    index = [{"file": r.file, "caption": r.caption, "ok": r.ok, **({"error": r.error} if r.error else {})} for r in results]
    (output_dir / "index.yaml").write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False), encoding="utf-8")
