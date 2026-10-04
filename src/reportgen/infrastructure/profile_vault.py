from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import yaml
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from reportgen.domain.personal import PersonalProfile
from reportgen.infrastructure.settings import home

LOCAL_FILE = "profile.yaml"
EXPORT_FILE = "profile.enc"
SALT_BYTES = 16
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
MIN_PASSWORD_CHARS = 8


class LocalProfileStore:
    """Личные данные на этом компьютере: обычный файл в рабочей папке, который не попадает в git."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or home() / LOCAL_FILE

    def load(self) -> PersonalProfile | None:
        if not self.path.is_file():
            return None
        return PersonalProfile.from_dict(yaml.safe_load(self.path.read_text(encoding="utf-8")) or {})

    def save(self, profile: PersonalProfile) -> None:
        self.path.write_text(yaml.safe_dump(profile.to_dict(), allow_unicode=True, sort_keys=False), encoding="utf-8")


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def export_encrypted(profile: PersonalProfile, password: str, target: Path) -> None:
    """Сохраняет данные зашифрованными паролем, чтобы безопасно перенести их на другой компьютер."""
    if len(password) < MIN_PASSWORD_CHARS:
        raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_CHARS} символов")
    salt = os.urandom(SALT_BYTES)
    token = Fernet(_derive_key(password, salt)).encrypt(json.dumps(profile.to_dict(), ensure_ascii=False).encode("utf-8"))
    target.write_text(json.dumps({"salt": base64.b64encode(salt).decode("ascii"), "token": token.decode("ascii")}), encoding="utf-8")


def import_encrypted(source: Path, password: str) -> PersonalProfile | None:
    """Расшифровывает выгрузку; при неверном пароле или повреждённом файле возвращает None."""
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        key = _derive_key(password, base64.b64decode(payload["salt"]))
        return PersonalProfile.from_dict(json.loads(Fernet(key).decrypt(payload["token"].encode("ascii"))))
    except (OSError, ValueError, KeyError, InvalidToken):
        return None
