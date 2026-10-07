"""Послеобработка собранных в Word DOCX: Word склеивает соседние фрагменты и может оставить курсив не там, где нужно.

Запуск: python scripts/post_fix.py <файл.docx> [...]
Затем обновить PDF: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/refresh_word.ps1 <файл.docx> <файл.pdf>
"""

from __future__ import annotations

import sys

from docx import Document

from reportgen.infrastructure.docx_objects import count_wrong_italics, fix_italics

for path in sys.argv[1:]:
    document = Document(path)
    fix_italics(document)
    document.save(path)
    print(f"{path}: фрагментов с неверным курсивом: {count_wrong_italics(document)}")
