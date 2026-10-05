from pathlib import Path

import pytest

from reportgen.domain.personal import PLACEHOLDERS, PersonalProfile, with_personal_data
from reportgen.domain.title_page import build_title_page
from reportgen.infrastructure.profile_vault import LocalProfileStore, export_encrypted, import_encrypted

PROFILE = PersonalProfile(student="И.И. Иванов", supervisor="П.П. Петров", faculty="Факультет примера", department="Кафедра примера")
PASSWORD = "длинный-пароль-123"


def title_texts(meta: dict) -> list[str]:
    return [line.text for line in build_title_page(with_personal_data(meta, None))]


def test_without_saved_data_title_page_has_placeholders():
    meta = with_personal_data({"title": "Тема"}, None)
    assert meta["student"] == PLACEHOLDERS["student"]
    assert meta["faculty"] == PLACEHOLDERS["faculty"]
    assert meta["title"] == "Тема"


def test_saved_profile_fills_title_page():
    meta = with_personal_data({"title": "Тема"}, PROFILE)
    assert meta["student"] == "И.И. Иванов"
    assert meta["department"] == "Кафедра примера"


def test_document_value_wins_over_profile():
    meta = with_personal_data({"supervisor": "А.А. Другой"}, PROFILE)
    assert meta["supervisor"] == "А.А. Другой"
    assert meta["student"] == "И.И. Иванов"


def test_title_page_follows_the_standard_layout():
    texts = [line.text for line in build_title_page({**with_personal_data({}, PROFILE), "title": "тема работы", "year": "2026"})]
    assert texts[0].startswith("Министерство образования")
    assert "ПОЯСНИТЕЛЬНАЯ ЗАПИСКА" in texts
    assert "на тему" in texts
    assert "ТЕМА РАБОТЫ" in texts
    assert texts[-1] == "Минск 2026"


def test_title_page_without_data_contains_only_placeholders():
    texts = title_texts({"title": "Тема"})
    assert PLACEHOLDERS["student"] in texts and PLACEHOLDERS["supervisor"] in texts


def test_local_store_round_trip(tmp_path: Path):
    store = LocalProfileStore(tmp_path / "profile.yaml")
    assert store.load() is None
    store.save(PROFILE)
    assert store.load() == PROFILE


def test_encrypted_export_hides_data_and_needs_the_password(tmp_path: Path):
    target = tmp_path / "profile.enc"
    export_encrypted(PROFILE, PASSWORD, target)
    stored = target.read_text(encoding="utf-8").lower()
    assert all(secret not in stored for secret in ("иванов", "петров", "примера"))
    assert import_encrypted(target, PASSWORD) == PROFILE
    assert import_encrypted(target, "неверный-пароль-1") is None
    assert import_encrypted(tmp_path / "нет-файла.enc", PASSWORD) is None


def test_short_export_password_is_refused(tmp_path: Path):
    with pytest.raises(ValueError):
        export_encrypted(PROFILE, "коротко", tmp_path / "profile.enc")
