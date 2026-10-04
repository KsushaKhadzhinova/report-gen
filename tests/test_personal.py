from pathlib import Path

import pytest

from reportgen.domain.personal import PLACEHOLDERS, PersonalProfile, with_personal_data
from reportgen.infrastructure.profile_vault import EncryptedProfileVault, WrongCredentials

PROFILE = PersonalProfile(student="Иванов Иван Иванович", group="123456", supervisor="Петров П. П.", email="Ivan@Example.com")
PASSPHRASE = "длинная-парольная-фраза"


def test_without_unlock_title_page_has_placeholders():
    meta = with_personal_data({"title": "Тема"}, None)
    assert meta["student"] == PLACEHOLDERS["student"]
    assert meta["group"] == PLACEHOLDERS["group"]
    assert meta["title"] == "Тема"


def test_unlocked_profile_fills_title_page():
    meta = with_personal_data({"title": "Тема"}, PROFILE)
    assert meta["student"] == "Иванов Иван Иванович"
    assert meta["supervisor"] == "Петров П. П."


def test_vault_round_trip_ignores_email_case(tmp_path: Path):
    vault = EncryptedProfileVault(tmp_path / "profile.enc")
    vault.save(PROFILE, PASSPHRASE)
    assert vault.unlock("  ivan@example.COM ", PASSPHRASE) == PROFILE


def test_vault_file_contains_no_readable_personal_data(tmp_path: Path):
    vault = EncryptedProfileVault(tmp_path / "profile.enc")
    vault.save(PROFILE, PASSPHRASE)
    stored = (tmp_path / "profile.enc").read_text(encoding="utf-8")
    for secret in ("Иванов", "123456", "Петров", "example.com"):
        assert secret.lower() not in stored.lower()


@pytest.mark.parametrize("email,passphrase", [("other@example.com", PASSPHRASE), ("ivan@example.com", "неверная-фраза-123")])
def test_wrong_email_or_passphrase_is_rejected(tmp_path: Path, email: str, passphrase: str):
    vault = EncryptedProfileVault(tmp_path / "profile.enc")
    vault.save(PROFILE, PASSPHRASE)
    with pytest.raises(WrongCredentials):
        vault.unlock(email, passphrase)


def test_short_passphrase_is_refused(tmp_path: Path):
    with pytest.raises(ValueError):
        EncryptedProfileVault(tmp_path / "profile.enc").save(PROFILE, "коротко")
