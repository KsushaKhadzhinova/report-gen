from __future__ import annotations

import re

DATE = r"\d{2}\.\d{2}\.\d{4}"
DATES = rf"(?P<date>{DATE}(?:,\s*{DATE})*)"
SITE_ENTRY_RE = re.compile(
    rf"^(?P<head>.*?)\s*\[Электронный ресурс\]\.\s*[–-]\s*Режим доступа:\s*(?P<url>\S+?)\.?\s*[–-]\s*Дата доступа:\s*{DATES}\.?\s*$"
)
DOMAIN = r"[\w\-]+(?:\.[\w\-]+)*\.[a-z]{2,}"
DOMAINS_ENTRY_RE = re.compile(
    rf"^(?P<label>[^:\[]+?):\s*(?P<domains>{DOMAIN}(?:\s*,\s*{DOMAIN})+)\s*\[Электронный ресурс\]\.\s*[–-]\s*Дата доступа:\s*{DATES}\.?\s*$"
)
TITLE_END_RE = re.compile(r"\s:\s|(?<=\S):\s|\s/\s")
SUBTITLE_COLON_RE = re.compile(r"(?<=\S): (?=\S)")
RESOURCE_MARK = "[Электронный ресурс]"


def _site_entry(title: str, rest: str, url: str, date: str) -> str:
    return f"{title} {RESOURCE_MARK}{rest}. – Режим доступа: {url}. – Дата доступа: {date}."


def to_vak_site_entry(entry: str) -> str:
    """Сайт по образцам ВАК РБ: «Заглавие [Электронный ресурс] : сведения. – Режим доступа: адрес. – Дата доступа: дд.мм.гггг.»"""
    match = SITE_ENTRY_RE.match(entry.strip())
    if not match:
        return entry
    head = match.group("head").rstrip(" .,;")
    end = TITLE_END_RE.search(head)
    title, rest = (head[: end.start()], head[end.start() :].strip()) if end else (head, "")
    if rest.startswith((":", "/")):
        rest = f" {rest[0]} {SUBTITLE_COLON_RE.sub(' : ', rest[1:].strip())}"
    return _site_entry(title.rstrip(), rest, match.group("url"), match.group("date"))


def split_domain_entry(entry: str) -> list[str] | None:
    """Запись со списком сайтов без адресов превращается в отдельную запись на каждый сайт; иначе None."""
    match = DOMAINS_ENTRY_RE.match(entry.strip())
    if not match:
        return None
    domains = [domain.strip() for domain in match.group("domains").split(",")]
    return [_site_entry(domain, "", f"https://{domain}", match.group("date")) for domain in domains]


def vak_entries(entry: str) -> list[str]:
    """Записи по форме ВАК РБ, которые получаются из одной исходной записи."""
    return split_domain_entry(entry) or [to_vak_site_entry(entry)]
