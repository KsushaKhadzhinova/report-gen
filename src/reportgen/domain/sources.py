from __future__ import annotations

import re

DATE = r"(?P<date>\d{2}\.\d{2}\.\d{4})"
SITE_ENTRY_RE = re.compile(
    rf"^(?P<head>.*?)\s*\[Электронный ресурс\]\.\s*[–-]\s*Режим доступа:\s*(?P<url>\S+?)\.?\s*[–-]\s*Дата доступа:\s*{DATE}\.?\s*$"
)
DOMAIN = r"[\w\-]+(?:\.[\w\-]+)*\.[a-z]{2,}"
DOMAINS_ENTRY_RE = re.compile(
    rf"^(?P<label>[^:\[]+?):\s*(?P<domains>{DOMAIN}(?:\s*,\s*{DOMAIN})+)\s*\[Электронный ресурс\]\.\s*[–-]\s*Дата доступа:\s*{DATE}\.?\s*$"
)
SUBTITLE_COLON_RE = re.compile(r"(?<=\S): (?=\S)")


def to_vak_site_entry(entry: str) -> str:
    """Сайт по образцам ВАК РБ: «Название : [сайт]. – URL: адрес (дата обращения: дд.мм.гггг).»"""
    match = SITE_ENTRY_RE.match(entry.strip())
    if not match:
        return entry
    head = SUBTITLE_COLON_RE.sub(" : ", match.group("head").rstrip(" .,;"))
    return f"{head} : [сайт]. – URL: {match.group('url')} (дата обращения: {match.group('date')})."


def split_domain_entry(entry: str) -> list[str] | None:
    """Запись со списком сайтов без адресов превращается в отдельную запись на каждый сайт; иначе None."""
    match = DOMAINS_ENTRY_RE.match(entry.strip())
    if not match:
        return None
    domains = [domain.strip() for domain in match.group("domains").split(",")]
    return [f"{domain} : [сайт]. – URL: https://{domain} (дата обращения: {match.group('date')})." for domain in domains]


def vak_entries(entry: str) -> list[str]:
    """Записи по форме ВАК, которые получаются из одной исходной записи."""
    return split_domain_entry(entry) or [to_vak_site_entry(entry)]
