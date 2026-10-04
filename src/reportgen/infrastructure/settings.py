from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

ENV_FILE = ".env"


def load_env(path: Path | None = None) -> None:
    """Подгружает переменные из .env, не перезаписывая уже заданные."""
    env_path = path or Path.cwd() / ENV_FILE
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def home() -> Path:
    """Каталог пользовательских данных: профиль стиля, кеш, история запусков."""
    path = Path(os.environ.get("REPORTGEN_HOME", "workspace")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_data(name: str) -> str:
    return resources.files("reportgen.data").joinpath(name).read_text(encoding="utf-8")


@dataclass(frozen=True)
class Provider:
    name: str
    description: str
    base_url: str
    api_key: str | None
    api_key_env: str | None
    signup_url: str | None
    roles: dict[str, list[str]]


def load_models_config() -> dict:
    user_file = home() / "models.yaml"
    text = user_file.read_text(encoding="utf-8") if user_file.is_file() else read_data("models.yaml")
    return yaml.safe_load(text)


def active_provider_name(override: str | None = None) -> str:
    cfg = load_models_config()
    return override or os.environ.get("REPORTGEN_PROVIDER") or cfg["default_provider"]


def get_provider(name: str | None = None) -> Provider:
    cfg = load_models_config()
    key = active_provider_name(name)
    if key not in cfg["providers"]:
        raise SystemExit(f"Неизвестный провайдер «{key}». Доступны: {', '.join(cfg['providers'])}")
    raw = cfg["providers"][key]
    base_url = raw.get("base_url") or os.environ.get(raw.get("base_url_env", ""), "")
    api_key_env = raw.get("api_key_env")
    return Provider(
        name=key,
        description=raw.get("description", ""),
        base_url=base_url.rstrip("/"),
        api_key=os.environ.get(api_key_env) if api_key_env else None,
        api_key_env=api_key_env,
        signup_url=raw.get("signup_url"),
        roles=raw["roles"],
    )


def set_default_provider(name: str) -> None:
    """Сохраняет выбор провайдера в пользовательском models.yaml."""
    cfg = load_models_config()
    if name not in cfg["providers"]:
        raise SystemExit(f"Неизвестный провайдер «{name}»")
    cfg["default_provider"] = name
    (home() / "models.yaml").write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
