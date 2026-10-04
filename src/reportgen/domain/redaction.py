from __future__ import annotations

import re

MASK = "[секрет скрыт]"

TOKEN_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]{12,}"),
)
ASSIGNMENT_PATTERN = re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")
SECRET_PATTERNS = TOKEN_PATTERNS + (ASSIGNMENT_PATTERN,)


def redact(text: str, known_secrets: tuple[str, ...] = ()) -> str:
    """Скрывает ключи и токены: известные значения и всё, что похоже на ключ."""
    for secret in known_secrets:
        if secret:
            text = text.replace(secret, MASK)
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(MASK, text)
    return text


def find_tokens(text: str) -> list[str]:
    """Фрагменты, похожие на токены известных сервисов; без эвристики по именам переменных."""
    found = (match.group(0) for pattern in TOKEN_PATTERNS for match in pattern.finditer(text))
    return list(dict.fromkeys(found))
