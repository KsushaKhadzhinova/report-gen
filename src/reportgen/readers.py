from __future__ import annotations

import re
from pathlib import Path

SUPPORTED = {".docx", ".pdf", ".tex", ".md", ".txt"}
TEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?")
TEX_COMMENT_RE = re.compile(r"(?<!\\)%.*$", re.MULTILINE)


def read_paragraphs(path: Path) -> list[str]:
    """Возвращает абзацы документа в виде обычного текста."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx(path)
    if suffix == ".pdf":
        return _pdf(path)
    if suffix == ".tex":
        return _tex(path)
    if suffix in {".md", ".txt"}:
        return _plain(path.read_text(encoding="utf-8", errors="replace"))
    return []


def _docx(path: Path) -> list[str]:
    from docx import Document

    document = Document(str(path))
    return [p.text.strip() for p in document.paragraphs if p.text.strip()]


def _pdf(path: Path) -> list[str]:
    import pymupdf

    paragraphs: list[str] = []
    with pymupdf.open(str(path)) as pdf:
        for page in pdf:
            paragraphs.extend(_plain(page.get_text()))
    return paragraphs


def _tex(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if "\\begin{document}" in text:
        text = text.split("\\begin{document}", 1)[1]
    text = TEX_COMMENT_RE.sub("", text)
    text = TEX_COMMAND_RE.sub(lambda m: (m.group(2) or "")[1:-1], text)
    text = re.sub(r"[{}$]", "", text)
    return _plain(text)


def _plain(text: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", text)
    return [re.sub(r"\s+", " ", c).strip() for c in chunks if c.strip()]


def iter_documents(root: Path):
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED and not path.name.startswith("~$"):
            yield path


def prose_paragraphs(root: Path, min_chars: int = 120) -> list[tuple[str, str]]:
    """Связные абзацы основного текста: пары (файл, текст)."""
    result = []
    for path in iter_documents(root):
        try:
            paragraphs = read_paragraphs(path)
        except Exception:
            continue
        for paragraph in paragraphs:
            if len(paragraph) >= min_chars and not paragraph.isupper() and paragraph.count(" ") > 12:
                result.append((path.name, paragraph))
    return result
