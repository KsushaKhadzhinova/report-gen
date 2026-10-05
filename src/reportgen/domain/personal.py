from __future__ import annotations

from dataclasses import asdict, dataclass

PLACEHOLDERS = {
    "student": "<И.О. Фамилия студента>",
    "supervisor": "<И.О. Фамилия руководителя>",
    "faculty": "<факультет>",
    "department": "<кафедра>",
}


@dataclass(frozen=True)
class PersonalProfile:
    """Личные данные автора для титульного листа. Хранятся только на его компьютере."""

    student: str = ""
    supervisor: str = ""
    faculty: str = ""
    department: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "PersonalProfile":
        return PersonalProfile(**{key: data.get(key, "") for key in PLACEHOLDERS})


def with_personal_data(meta: dict, profile: PersonalProfile | None) -> dict:
    """Значение из документа важнее сохранённого профиля; если нет ни того, ни другого, ставится заглушка."""
    saved = profile.to_dict() if profile else {}
    return {**meta, **{key: meta.get(key) or saved.get(key) or PLACEHOLDERS[key] for key in PLACEHOLDERS}}
