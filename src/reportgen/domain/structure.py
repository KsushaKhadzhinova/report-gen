from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_WORDS = 300
REFERENCES_KIND = "references"


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    level: int = 1
    numbered: bool = True
    words: int = 0
    guide: str = ""
    figures: tuple[str, ...] = ()
    kind: str = ""
    rules: str = ""

    @property
    def is_container(self) -> bool:
        return self.words == 0 and self.kind != REFERENCES_KIND

    @property
    def is_references(self) -> bool:
        return self.kind == REFERENCES_KIND

    def to_dict(self) -> dict:
        data = {"id": self.id, "title": self.title, "level": self.level, "numbered": self.numbered, "words": self.words}
        if self.guide:
            data["guide"] = self.guide
        if self.figures:
            data["figures"] = list(self.figures)
        if self.kind:
            data["kind"] = self.kind
        if self.rules:
            data["rules"] = self.rules
        return data

    @staticmethod
    def from_dict(data: dict) -> "Section":
        return Section(
            id=data["id"],
            title=data["title"],
            level=data.get("level", 1),
            numbered=data.get("numbered", True),
            words=data.get("words", 0),
            guide=(data.get("guide") or "").strip(),
            figures=tuple(data.get("figures", ())),
            kind=data.get("kind", ""),
            rules=data.get("rules", ""),
        )


@dataclass(frozen=True)
class Structure:
    name: str
    sections: tuple[Section, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {"name": self.name, "sections": [section.to_dict() for section in self.sections]}

    @staticmethod
    def from_dict(data: dict) -> "Structure":
        return Structure(data.get("name", ""), tuple(Section.from_dict(s) for s in data["sections"]))
