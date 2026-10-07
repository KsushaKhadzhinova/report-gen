from __future__ import annotations

import re
import shutil
from pathlib import Path

from reportgen.domain import enterprise_standard as standard
from reportgen.domain.blocks import Block, Kind
from reportgen.domain.title_page import BLANK, CENTER, FIELD, build_title_page
from reportgen.infrastructure.safe_paths import resolve_inside

SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
INLINE_RE = re.compile(r"(`[^`]+`|\*[^*]+\*)")

PREAMBLE = r"""\documentclass[a4paper,14pt]{extarticle}
\usepackage{fontspec}
\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{\setmainfont{Liberation Serif}}
\IfFontExistsTF{Courier New}{\setmonofont{Courier New}}{\setmonofont{Liberation Mono}}
\usepackage[russian]{babel}
\usepackage[a4paper,left=%(left)smm,right=%(right)smm,top=%(top)smm,bottom=%(bottom)smm]{geometry}
\usepackage{graphicx}
\usepackage{longtable}
\usepackage{array}
\usepackage{fancyhdr}
\usepackage{tocloft}
\usepackage{fvextra}
\usepackage[hidelinks]{hyperref}

\fontsize{14}{18}\selectfont
\setlength{\parindent}{%(indent)scm}
\setlength{\parskip}{0pt}
\setlength{\baselineskip}{18pt}
\raggedbottom
\sloppy

\pagestyle{fancy}
\fancyhf{}
\fancyfoot[R]{\thepage}
\renewcommand{\headrulewidth}{0pt}

\renewcommand{\cftsecfont}{\normalfont}
\renewcommand{\cftsubsecfont}{\normalfont}
\renewcommand{\cftsecpagefont}{\normalfont}
\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}
\renewcommand{\cftsubsecleader}{\cftdotfill{\cftdotsep}}
\setlength{\cftbeforesecskip}{0pt}
\setlength{\cftbeforesubsecskip}{0pt}

\newcommand{\reportchapter}[2]{\clearpage\noindent\hspace{\parindent}\textbf{#1 #2}\par\vspace{\baselineskip}\addcontentsline{toc}{section}{#1 #2}}
\newcommand{\reportsection}[2]{\noindent\hspace{\parindent}\textbf{#1 #2}\par\vspace{\baselineskip}\addcontentsline{toc}{subsection}{#1 #2}}
\newcommand{\reportsubsection}[2]{\noindent\hspace{\parindent}\textbf{#1 #2}\par\vspace{\baselineskip}}
\newcommand{\reportplain}[1]{\clearpage\begin{center}\textbf{#1}\end{center}\vspace{\baselineskip}\addcontentsline{toc}{section}{#1}}
\newcommand{\reportappendix}[2]{\clearpage\begin{center}\textbf{ПРИЛОЖЕНИЕ #1}\\\textbf{#2}\end{center}\vspace{\baselineskip}\addcontentsline{toc}{section}{ПРИЛОЖЕНИЕ #1 #2}}

\begin{document}
"""


def escape(text: str) -> str:
    return "".join(SPECIAL.get(ch, ch) for ch in text)


def inline(text: str) -> str:
    out = []
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("`") and part.endswith("`"):
            out.append(r"\texttt{" + escape(part[1:-1]) + "}")
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(r"\textit{" + escape(part[1:-1]) + "}")
        else:
            out.append(escape(part))
    return "".join(out)


def _title_line(line) -> str:
    if line.kind == BLANK:
        return r"\vspace{\baselineskip}"
    text = inline(line.text)
    if line.kind == CENTER:
        return (r"\textbf{%s}" % text if line.bold else text) + r"\par"
    if line.kind == FIELD:
        return r"\noindent %s\hspace{1em}%s\par" % (inline(line.label), text)
    return r"\noindent %s\hfill %s\par" % (inline(line.label), text)


def _title_page(meta: dict) -> str:
    body = "\n".join(_title_line(line) for line in build_title_page(meta))
    return "\\begin{titlepage}\n\\centering\n" + body + "\n\\end{titlepage}"


def _heading(block: Block) -> str:
    title = escape(block.text)
    if block.appendix:
        return rf"\reportappendix{{{block.number}}}{{{title}}}"
    if block.level == 1 and not block.numbered:
        return rf"\reportplain{{{title}}}"
    command = {1: "reportchapter", 2: "reportsection", 3: "reportsubsection"}[block.level]
    return rf"\{command}{{{block.number}}}{{{title}}}"


def _table(block: Block) -> str:
    rows = block.rows
    columns = max(len(r) for r in rows)
    spec = "|" + "|".join([r">{\raggedright\arraybackslash}p{%.3f\textwidth}" % (0.98 / columns)] * columns) + "|"
    out = []
    if block.caption:
        out.append(r"\noindent " + escape(standard.table_caption(block.number, block.caption)) + r"\par\nopagebreak")
    out.append(r"\begin{longtable}{%s}" % spec)
    out.append(r"\hline")
    for index, row in enumerate(rows):
        cells = [inline(row[c]) if c < len(row) else "" for c in range(columns)]
        out.append(" & ".join(cells) + r" \\ \hline")
        if index == 0:
            out.append(r"\endhead")
    out.append(r"\end{longtable}")
    out.append(r"\vspace{\baselineskip}")
    return "\n".join(out)


def _figure(block: Block, build_dir: Path, base: Path, counter: int) -> str:
    source = resolve_inside(base, block.path)
    if source is None:
        return rf"\noindent\textit{{[нет файла: {escape(block.path)}]}}\par"
    target_dir = build_dir / "figures"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"fig{counter}{source.suffix.lower()}"
    shutil.copyfile(source, target)
    caption = escape(standard.figure_caption(block.number, block.caption))
    return (
        "\\begin{center}\n"
        f"\\includegraphics[width=\\textwidth,height=0.6\\textheight,keepaspectratio]{{figures/{target.name}}}\\par\n"
        f"{caption}\n"
        "\\end{center}\n\\vspace{\\baselineskip}"
    )


NEWLINE = chr(10)
NOINDENT = "\\noindent "
PAR_NOBREAK = "\\par\\nopagebreak"
SKIP_LINE = "\\vspace{\\baselineskip}"
VERBATIM_INPUT = "\\VerbatimInput[fontsize=\\small,breaklines=true,breakanywhere=true]{listings/%s}"


def _code(block: Block, build_dir: Path, counter: int) -> str:
    listings = build_dir / "listings"
    listings.mkdir(parents=True, exist_ok=True)
    source = listings / f"listing{counter}.txt"
    source.write_text(block.text, encoding="utf-8")
    lines = []
    if block.caption:
        caption = escape(standard.listing_caption(block.number, block.caption))
        lines.append(NOINDENT + caption + PAR_NOBREAK)
    lines.append(VERBATIM_INPUT % source.name)
    lines.append(SKIP_LINE)
    return NEWLINE.join(lines)


def _preamble() -> str:
    return PREAMBLE % {
        "left": standard.MARGIN_LEFT_MM,
        "right": standard.MARGIN_RIGHT_MM,
        "top": standard.MARGIN_TOP_MM,
        "bottom": standard.MARGIN_BOTTOM_MM,
        "indent": standard.PARAGRAPH_INDENT_CM,
    }


def _contents() -> str:
    return (
        r"\clearpage\begin{center}\textbf{СОДЕРЖАНИЕ}\end{center}\vspace{\baselineskip}"
        "\n" r"\renewcommand{\contentsname}{}\tableofcontents"
    )


class TexRenderer:
    def render(self, blocks: list[Block], meta: dict, base_dir: Path, output: Path) -> Path:
        build_dir = output.parent
        build_dir.mkdir(parents=True, exist_ok=True)
        parts = [_preamble()]
        if meta.get("title_page", True):
            parts.append(_title_page(meta))
        if meta.get("toc", True):
            parts.append(_contents())
        figure_count = listing_count = 0
        for block in blocks:
            if block.kind is Kind.FIGURE:
                figure_count += 1
                parts.append(_figure(block, build_dir, base_dir, figure_count))
            elif block.kind is Kind.CODE:
                listing_count += 1
                parts.append(_code(block, build_dir, listing_count))
            else:
                parts.append(self._render_block(block))
        parts.append(r"\end{document}")
        output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
        return output

    @staticmethod
    def _render_block(block: Block) -> str:
        handlers = {
            Kind.HEADING: lambda: _heading(block),
            Kind.PARAGRAPH: lambda: inline(block.text) + "\n",
            Kind.LIST: lambda: "".join(inline(line) + "\n\n" for line in standard.list_items(block.items)),
            Kind.TABLE: lambda: _table(block),
        }
        return handlers[block.kind]()
