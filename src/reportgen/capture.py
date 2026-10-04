from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "consola.ttf",
    "DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


class CaptureError(RuntimeError):
    pass


def _font(size: int) -> ImageFont.ImageFont:
    for name in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render_console(text: str, target: Path, width_chars: int = 100, max_lines: int = 40) -> Path:
    lines: list[str] = []
    for raw in text.splitlines():
        while len(raw) > width_chars:
            lines.append(raw[:width_chars])
            raw = raw[width_chars:]
        lines.append(raw)
    lines = lines[-max_lines:]
    font = _font(18)
    line_height = 24
    image = Image.new("RGB", (width_chars * 11 + 40, max(1, len(lines)) * line_height + 40), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((20, 20 + index * line_height), line, fill=(20, 20, 20), font=font)
    image.save(target)
    return target


def _console(item: dict, target: Path, cwd: Path) -> Path:
    command = item["command"]
    shown = f"> {command}"
    result = subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=item.get("timeout", 120))
    return render_console(f"{shown}\n{result.stdout}{result.stderr}", target)


def _web(item: dict, target: Path) -> Path:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise CaptureError("Для веб-скриншотов установите playwright: pip install 'report-gen[capture]'") from exc
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": item.get("width", 1366), "height": item.get("height", 768)})
        page.goto(item["url"], wait_until="networkidle", timeout=60000)
        if item.get("wait_for"):
            page.wait_for_selector(item["wait_for"], timeout=30000)
        for action in item.get("actions", []):
            if "click" in action:
                page.click(action["click"])
            elif "fill" in action:
                page.fill(action["fill"]["selector"], action["fill"]["value"])
            page.wait_for_load_state("networkidle")
        page.screenshot(path=str(target), full_page=item.get("full_page", False))
        browser.close()
    return target


def _desktop(item: dict, target: Path) -> Path:
    try:
        import pyautogui
    except ImportError as exc:
        raise CaptureError("Для скриншотов окон установите pyautogui: pip install 'report-gen[capture]'") from exc
    window = item.get("window")
    if window:
        matches = pyautogui.getWindowsWithTitle(window) if hasattr(pyautogui, "getWindowsWithTitle") else []
        if matches:
            matches[0].activate()
            time.sleep(1)
            region = (matches[0].left, matches[0].top, matches[0].width, matches[0].height)
            pyautogui.screenshot(region=region).save(target)
            return target
    pyautogui.screenshot().save(target)
    return target


def _diagram(item: dict, target: Path, project: Path) -> Path:
    source = project / item["source"]
    if source.suffix == ".dot":
        if not shutil.which("dot"):
            raise CaptureError("Не найден Graphviz (dot)")
        subprocess.run(["dot", "-Tpng", "-Gdpi=150", str(source), "-o", str(target)], check=True)
    elif source.suffix in {".puml", ".plantuml"}:
        if not shutil.which("plantuml"):
            raise CaptureError("Не найден PlantUML")
        subprocess.run(["plantuml", "-tpng", "-o", str(target.parent.resolve()), str(source)], check=True)
        produced = target.parent / f"{source.stem}.png"
        if produced != target:
            produced.replace(target)
    else:
        raise CaptureError(f"Неизвестный формат диаграммы: {source.suffix}")
    return target


def run(project: Path) -> list[dict]:
    plan_file = project / "screens.yaml"
    if not plan_file.is_file():
        raise CaptureError(f"Не найден {plan_file}")
    plan = yaml.safe_load(plan_file.read_text(encoding="utf-8")) or {}
    out_dir = project / "screenshots"
    out_dir.mkdir(exist_ok=True)

    server = None
    if plan.get("start"):
        server = subprocess.Popen(plan["start"], shell=True, cwd=project)
        time.sleep(plan.get("start_wait", 8))

    captured: list[dict] = []
    try:
        for item in plan.get("items", []):
            target = out_dir / f"{item['name']}.png"
            kind = item["kind"]
            try:
                if kind == "web":
                    _web(item, target)
                elif kind == "console":
                    _console(item, target, project)
                elif kind == "desktop":
                    _desktop(item, target)
                elif kind == "diagram":
                    _diagram(item, target, project)
                else:
                    raise CaptureError(f"Неизвестный вид: {kind}")
                captured.append({"file": f"screenshots/{target.name}", "caption": item.get("caption", item["name"]), "ok": True})
            except Exception as exc:
                captured.append({"file": f"screenshots/{target.name}", "caption": item.get("caption", item["name"]), "ok": False, "error": str(exc)})
    finally:
        if server:
            server.terminate()

    (out_dir / "index.yaml").write_text(yaml.safe_dump(captured, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return captured
