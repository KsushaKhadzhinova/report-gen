from __future__ import annotations

import json
import random
import re
from collections import Counter
from pathlib import Path

from reportgen.readers import prose_paragraphs
from reportgen.settings import home

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z«\"])")
WORD_RE = re.compile(r"[а-яёa-z\-]+", re.IGNORECASE)
PROFILE_NAME = "style_profile.json"


def profile_path() -> Path:
    return home() / PROFILE_NAME


def learn(source: Path, exemplars: int = 6, seed: int = 7) -> dict:
    """Строит профиль стиля по работам автора в каталоге или файле."""
    pairs = prose_paragraphs(source)
    if not pairs:
        raise ValueError(f"В {source} не найдено связного текста для анализа")

    sentences: list[str] = []
    for _, paragraph in pairs:
        sentences.extend(s for s in SENTENCE_RE.split(paragraph) if len(s) > 20)

    lengths = [len(WORD_RE.findall(s)) for s in sentences]
    openers = Counter(" ".join(WORD_RE.findall(s)[:2]).lower() for s in sentences if len(WORD_RE.findall(s)) > 3)
    words = [w.lower() for s in sentences for w in WORD_RE.findall(s)]
    bigrams = Counter(zip(words, words[1:]))
    stop = {"в", "на", "и", "с", "по", "для", "от", "из", "к", "о", "не", "что", "как", "а", "то", "же"}
    phrases = Counter({" ".join(k): v for k, v in bigrams.items() if k[0] not in stop and k[1] not in stop and v >= 4})

    rng = random.Random(seed)
    pool = [p for _, p in pairs if 250 <= len(p) <= 900]
    rng.shuffle(pool)

    profile = {
        "documents": sorted({name for name, _ in pairs}),
        "paragraphs": len(pairs),
        "sentences": len(sentences),
        "avg_sentence_words": round(sum(lengths) / len(lengths), 1),
        "avg_paragraph_chars": round(sum(len(p) for _, p in pairs) / len(pairs)),
        "sentence_openers": [w for w, _ in openers.most_common(15)],
        "signature_phrases": [w for w, _ in phrases.most_common(25)],
        "exemplars": pool[:exemplars],
    }
    profile_path().write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def load() -> dict | None:
    path = profile_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def style_prompt() -> str:
    profile = load()
    base = (
        "Пиши на русском языке в научно-техническом стиле для пояснительной записки по СТП БГУИР. "
        "Без личных местоимений («я», «мы»), без разговорных оборотов, без списков с жирным шрифтом. "
        "Числа до десяти пиши словами. Не выдумывай факты, источники и цифры: опирайся только на предоставленные сведения."
    )
    if not profile:
        return base
    parts = [
        base,
        f"Средняя длина предложения автора — около {profile['avg_sentence_words']} слов, "
        f"абзаца — около {profile['avg_paragraph_chars']} символов.",
    ]
    if profile["sentence_openers"]:
        parts.append("Типичные начала предложений автора: " + "; ".join(profile["sentence_openers"][:10]) + ".")
    if profile["signature_phrases"]:
        parts.append("Характерные обороты автора: " + "; ".join(profile["signature_phrases"][:12]) + ".")
    if profile["exemplars"]:
        samples = "\n\n".join(f"Образец {i}:\n{t}" for i, t in enumerate(profile["exemplars"][:3], 1))
        parts.append("Перенимай манеру изложения, но не копируй формулировки из образцов.\n\n" + samples)
    return "\n\n".join(parts)
