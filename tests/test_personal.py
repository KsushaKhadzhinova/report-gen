from pathlib import Path

import pytest

from reportgen.domain.personal import PLACEHOLDERS, PersonalProfile, with_personal_data
from reportgen.infrastructure.profile_vault import LocalProfileStore, export_encrypted, import_encrypted

PROFILE = PersonalProfile(student="Иванов Иван Иванович", group="123456", supervisor="Петров П. П.")
PASSWORD = "длинный-пароль-123"


def test_without_saved_data_title_page_has_placeholders():
    meta = with_personal_data({"title": "Тема"}, None)
    assert meta["student"] == PLACEHOLDERS["student"]
    assert meta["group"] == PLACEHOLDERS["group"]
    assert meta["title"] == "Тема"


def test_saved_profile_fills_title_page():
    meta = with_personal_data({"title": "Тема"}, PROFILE)
    assert meta["student"] == "Иванов Иван Иванович"
    assert meta["supervisor"] == "Петров П. П."


def test_empty_fields_fall_back_to_placeholders():
    meta = with_personal_data({}, PersonalProfile(student="Иванов", group="", supervisor=""))
    assert meta["group"] == PLACEHOLDERS["group"]


def test_local_store_round_trip(tmp_path: Path):
    store = LocalProfileStore(tmp_path / "profile.yaml")
    assert store.load() is None
    store.save(PROFILE)
    assert store.load() == PROFILE


def test_encrypted_export_hides_data_and_needs_the_password(tmp_path: Path):
    target = tmp_path / "profile.enc"
    export_encrypted(PROFILE, PASSWORD, target)
    stored = target.read_text(encoding="utf-8").lower()
    assert all(secret not in stored for secret in ("иванов", "123456", "петров"))
    assert import_encrypted(target, PASSWORD) == PROFILE
    assert import_encrypted(target, "неверный-пароль-1") is None
    assert import_encrypted(tmp_path / "нет-файла.enc", PASSWORD) is None


def test_short_export_password_is_refused(tmp_path: Path):
    with pytest.raises(ValueError):
        export_encrypted(PROFILE, "коротко", tmp_path / "profile.enc")
