from __future__ import annotations

import os
import re
from pathlib import Path

SERVICE = "report-gen"
SECRET_NAME_RE = re.compile(r"^[A-Z0-9_]*(API_KEY|TOKEN|SECRET)$")


class SecretStoreUnavailable(RuntimeError):
    pass


class KeyringSecretStore:
    """Хранилище ключей операционной системы: Windows Credential Manager, macOS Keychain, Secret Service."""

    def _keyring(self):
        try:
            import keyring
            from keyring.errors import KeyringError
        except ImportError as error:
            raise SecretStoreUnavailable("Не установлен пакет keyring: pip install keyring") from error
        return keyring, KeyringError

    def get(self, name: str) -> str | None:
        keyring, error_type = self._keyring()
        try:
            return keyring.get_password(SERVICE, name)
        except error_type:
            return None

    def set(self, name: str, value: str) -> None:
        keyring, error_type = self._keyring()
        try:
            keyring.set_password(SERVICE, name, value)
        except error_type as error:
            raise SecretStoreUnavailable("В системе нет защищённого хранилища ключей; задайте ключ переменной окружения") from error

    def delete(self, name: str) -> None:
        keyring, error_type = self._keyring()
        try:
            keyring.delete_password(SERVICE, name)
        except error_type:
            pass


def resolve_secret(name: str | None) -> str | None:
    """Ключ из переменной окружения, а если её нет — из защищённого хранилища."""
    if not name:
        return None
    value = os.environ.get(name)
    if value:
        return value
    try:
        return KeyringSecretStore().get(name)
    except SecretStoreUnavailable:
        return None


def migrate_env_file(env_path: Path, store: KeyringSecretStore | None = None) -> list[str]:
    """Переносит ключи из .env в хранилище и очищает их значения в файле. Возвращает только имена."""
    store = store or KeyringSecretStore()
    if not env_path.is_file():
        return []
    migrated: list[str] = []
    lines: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        name = key.strip()
        if separator and SECRET_NAME_RE.match(name) and value.strip().strip("\"'"):
            store.set(name, value.strip().strip("\"'"))
            migrated.append(name)
            line = f"{name}="
        lines.append(line)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return migrated
