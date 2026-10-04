from __future__ import annotations

from dataclasses import asdict, dataclass

PLACEHOLDERS = {
    "student": "<ФИО студента>",
    "group": "<группа>",
    "supervisor": "<руководитель>",
}


@dataclass(frozen=True)
class PersonalProfile:
    """Личные данные автора для титульного листа. Хранятся только в зашифрованном виде."""

    student: str
    group: str
    supervisor: str
    email: str

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "PersonalProfile":
        return PersonalProfile(**{key: data.get(key, "") for key in ("student", "group", "supervisor", "email")})

    def title_page_fields(self) -> dict:
        return {"student": self.student, "group": self.group, "supervisor": self.supervisor}


def with_personal_data(meta: dict, profile: PersonalProfile | None) -> dict:
    """Подставляет в данные титульного листа личные сведения или, без разблокировки, заглушки."""
    fields = profile.title_page_fields() if profile else PLACEHOLDERS
    return {**meta, **{key: value or PLACEHOLDERS[key] for key, value in fields.items()}}
