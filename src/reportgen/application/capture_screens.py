from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from reportgen.application.ports import ScreenshotTaker


@dataclass(frozen=True)
class CaptureResult:
    name: str
    file: str
    caption: str
    ok: bool
    error: str = ""


def capture_all(
    items: list[dict],
    takers: Mapping[str, ScreenshotTaker],
    output_dir: Path,
    project_root: Path,
) -> list[CaptureResult]:
    """Снимает все элементы плана; сбой одного элемента не прерывает остальные."""
    return [_capture_one(item, takers, output_dir, project_root) for item in items]


def _capture_one(item: dict, takers: Mapping[str, ScreenshotTaker], output_dir: Path, project_root: Path) -> CaptureResult:
    name = item["name"]
    caption = item.get("caption", name)
    file = f"screenshots/{name}.png"
    taker = takers.get(item["kind"])
    if taker is None:
        return CaptureResult(name, file, caption, False, f"Неизвестный вид: {item['kind']}")
    try:
        taker.take(item, output_dir / f"{name}.png", project_root)
    except Exception as error:  # адаптеры бросают разные исключения: сбой снимка не должен ронять весь план
        return CaptureResult(name, file, caption, False, str(error))
    return CaptureResult(name, file, caption, True)
