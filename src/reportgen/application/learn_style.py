from __future__ import annotations

from pathlib import Path

from reportgen.application.ports import ProseSource, StyleStore
from reportgen.domain.style_profile import StyleProfile, build_profile


def learn_style(source: ProseSource, location: Path, store: StyleStore) -> StyleProfile:
    profile = build_profile(source.paragraphs(location))
    store.save(profile)
    return profile
