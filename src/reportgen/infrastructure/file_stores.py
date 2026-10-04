from __future__ import annotations

import json
from pathlib import Path

from reportgen.domain.overlap import ReferenceDocument, index_references
from reportgen.domain.style_profile import StyleProfile
from reportgen.infrastructure.readers import DocumentProseSource
from reportgen.infrastructure.settings import home

PROFILE_FILE = "style_profile.json"
REFERENCE_MIN_CHARS = 60


class FileStyleStore:
    def __init__(self, directory: Path | None = None) -> None:
        self.path = (directory or home()) / PROFILE_FILE

    def load(self) -> StyleProfile | None:
        if not self.path.is_file():
            return None
        return StyleProfile.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, profile: StyleProfile) -> None:
        self.path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class FolderReferenceLibrary:
    """Эталонные работы из каталога; индекс строится один раз при первом обращении."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._index: list[ReferenceDocument] | None = None

    def documents(self) -> list[ReferenceDocument]:
        if self._index is None:
            self._index = index_references(DocumentProseSource(REFERENCE_MIN_CHARS).paragraphs(self.folder))
        return self._index
