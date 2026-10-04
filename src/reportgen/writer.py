from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

from reportgen import overlap, style
from reportgen.analyze import analyze, summary_text
from reportgen.llm import LLM
from reportgen.settings import read_data

FIG_TOKEN = "{fig:%s}"
MARKUP_RE = re.compile(r"^(#+\s*|\*\*|__|>\s*)|(\*\*|__)", re.MULTILINE)
LEADING_NUMBER_RE = re.compile(r"^\d+[.)]?\s*")
MAX_REWRITE_PASSES = 2

Progress = Callable[[str], None]


@dataclass
class Context:
    project: Path
    facts: str
    figures: dict[str, str]
    task: str = ""


def load_structure(name: str, custom: Path | None = None) -> dict:
    if custom and custom.is_file():
        return yaml.safe_load(custom.read_text(encoding="utf-8"))
    return yaml.safe_load(read_data(f"{name}.yaml"))


def build_context(project: Path, code_dir: Path | None = None, task: str = "") -> Context:
    parts: list[str] = []
    brief = project / "brief.md"
    if brief.is_file():
        parts.append("Сведения от автора:\n" + brief.read_text(encoding="utf-8")[:3500])
    if code_dir and code_dir.is_dir():
        parts.append("Анализ проекта:\n" + summary_text(analyze(code_dir))[:3000])
    figures: dict[str, str] = {}
    index = project / "screenshots" / "index.yaml"
    if index.is_file():
        for item in yaml.safe_load(index.read_text(encoding="utf-8")) or []:
            if item.get("ok"):
                figures[Path(item["file"]).stem] = item["caption"]
    return Context(project, "\n\n".join(parts), figures, task)


def _clean(text: str) -> str:
    text = MARKUP_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _fingerprint(section: dict, ctx: Context, llm: LLM) -> str:
    payload = json.dumps(
        {
            "section": section,
            "facts": ctx.facts,
            "figures": ctx.figures,
            "task": ctx.task,
            "style": style.style_prompt(),
            "provider": llm.provider.name,
            "models": llm.provider.roles.get("writer"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _heading_line(section: dict) -> str:
    marks = "#" * section.get("level", 1)
    suffix = "" if section.get("numbered", True) else " {-}"
    return f"{marks} {section['title']}{suffix}"


def _write_references(section: dict, ctx: Context) -> str:
    source = ctx.project / "sources.txt"
    lines = [_heading_line(section), ""]
    if source.is_file():
        entries = [l.strip() for l in source.read_text(encoding="utf-8").splitlines() if l.strip()]
        for number, entry in enumerate(entries, 1):
            text = LEADING_NUMBER_RE.sub("", entry)
            lines += [f"{number} {text}", ""]
    else:
        lines += ["TODO: добавьте источники в файл sources.txt (по одному в строке).", ""]
    return "\n".join(lines)


def _prompt(section: dict, ctx: Context) -> str:
    figures = ""
    wanted = [n for n in section.get("figures", []) if n in ctx.figures]
    if wanted:
        listing = "; ".join(f"{FIG_TOKEN % n} — {ctx.figures[n]}" for n in wanted)
        figures = (
            "\nВ тексте обязательно сошлись на каждый рисунок оборотом вида «на рисунке {fig:имя} показано…», "
            f"сохраняя метки в фигурных скобках без изменений. Рисунки: {listing}."
        )
    task = f"\nЗадание:\n{ctx.task}" if ctx.task else ""
    words = section.get("words", 300)
    return (
        f"Напиши текст раздела «{section['title']}».\n"
        f"Содержание: {section.get('guide', '').strip()}\n"
        f"Объём: около {words} слов. Только связные абзацы, без заголовков, без markdown, без списков, без таблиц."
        f"{figures}{task}\n\nСведения:\n{ctx.facts or 'Сведений нет: пиши общим научно-техническим текстом без конкретных названий.'}"
    )


def _rewrite_overlaps(llm: LLM, body: str, reference: Path | None) -> tuple[str, int]:
    if not reference or not reference.exists():
        return body, 0
    paragraphs = [p for p in body.split("\n\n") if p.strip()]
    rewritten = 0
    for _ in range(MAX_REWRITE_PASSES):
        flagged = {m.text for m in overlap.scan(paragraphs, reference)}
        if not flagged:
            break
        updated = []
        for paragraph in paragraphs:
            if paragraph in flagged:
                paragraph = llm.chat(
                    "rewriter",
                    style.style_prompt(),
                    "Перепиши абзац другими словами и с другой структурой предложений, сохранив смысл, факты и метки в "
                    "фигурных скобках. Верни только абзац.\n\n" + paragraph,
                    temperature=0.9,
                )
                paragraph = _clean(paragraph)
                rewritten += 1
            updated.append(paragraph)
        paragraphs = updated
    return "\n\n".join(paragraphs), rewritten


def write_section(llm: LLM, section: dict, ctx: Context, reference: Path | None) -> tuple[str, int]:
    if section.get("kind") == "references":
        return _write_references(section, ctx), 0
    if not section.get("words"):
        return _heading_line(section) + "\n", 0

    body = _clean(llm.chat("writer", style.style_prompt(), _prompt(section, ctx), max_tokens=3000))
    body, rewritten = _rewrite_overlaps(llm, body, reference)

    wanted = [n for n in section.get("figures", []) if n in ctx.figures]
    for name in wanted:
        if FIG_TOKEN % name not in body:
            body += f"\n\nВнешний вид показан на рисунке {FIG_TOKEN % name}."
    figure_lines = [f"![{ctx.figures[n]}](screenshots/{n}.png)" for n in wanted]
    parts = [_heading_line(section), "", body]
    if figure_lines:
        parts += [""] + ["\n\n".join(figure_lines)]
    return "\n".join(parts) + "\n", rewritten


def write_all(
    llm: LLM,
    structure: dict,
    ctx: Context,
    reference: Path | None = None,
    only: str | None = None,
    force: bool = False,
    progress: Progress = print,
) -> dict[str, str]:
    content = ctx.project / "content"
    content.mkdir(exist_ok=True)
    cache_file = ctx.project / ".reportgen" / "cache.json"
    cache_file.parent.mkdir(exist_ok=True)
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.is_file() else {}
    status: dict[str, str] = {}

    for section in structure["sections"]:
        sid = section["id"]
        if only and only != sid:
            continue
        target = content / f"{sid}.md"
        key = _fingerprint(section, ctx, llm)
        if not force and target.is_file() and cache.get(sid) == key:
            status[sid] = "без изменений"
            progress(f"  {sid}: без изменений")
            continue
        progress(f"  {sid}: генерация…")
        text, rewritten = write_section(llm, section, ctx, reference)
        target.write_text(text, encoding="utf-8")
        cache[sid] = key
        cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        status[sid] = "готово" + (f", переписано абзацев: {rewritten}" if rewritten else "")
        progress(f"  {sid}: {status[sid]}")
    return status
