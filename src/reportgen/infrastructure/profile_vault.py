from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from reportgen.domain.personal import PersonalProfile
from reportgen.infrastructure.settings import home

VAULT_FILE = "profile.enc"
SALT_BYTES = 16
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
MIN_PASSPHRASE_CHARS = 8


class WrongCredentials(RuntimeError):
    pass


class ProfileNotFound(RuntimeError):
    pass


def _derive_key(email: str, passphrase: str, salt: bytes) -> bytes:
    """Ключ зависит и от почты, и от парольной фразы: без обеих данные не открыть."""
    material = f"{email.strip().lower()}\n{passphrase}".encode("utf-8")
    kdf = Scrypt(salt=salt, length=32, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return base64.urlsafe_b64encode(kdf.derive(material))


class EncryptedProfileVault:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or home() / VAULT_FILE

    def exists(self) -> bool:
        return self.path.is_file()

    def save(self, profile: PersonalProfile, passphrase: str) -> None:
        if len(passphrase) < MIN_PASSPHRASE_CHARS:
            raise ValueError(f"Парольная фраза должна быть не короче {MIN_PASSPHRASE_CHARS} символов")
        salt = os.urandom(SALT_BYTES)
        token = Fernet(_derive_key(profile.email, passphrase, salt)).encrypt(json.dumps(profile.to_dict(), ensure_ascii=False).encode("utf-8"))
        payload = {"salt": base64.b64encode(salt).decode("ascii"), "token": token.decode("ascii")}
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def unlock(self, email: str, passphrase: str) -> PersonalProfile:
        if not self.exists():
            raise ProfileNotFound("Личные данные ещё не заданы: report-gen profile set")
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        salt = base64.b64decode(payload["salt"])
        try:
            raw = Fernet(_derive_key(email, passphrase, salt)).decrypt(payload["token"].encode("ascii"))
        except InvalidToken as error:
            raise WrongCredentials("Неверная почта или парольная фраза") from error
        return PersonalProfile.from_dict(json.loads(raw))
