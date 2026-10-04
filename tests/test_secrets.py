import subprocess
from pathlib import Path

from reportgen.domain.redaction import MASK, find_tokens, redact
from reportgen.infrastructure.llm_client import OpenAICompatibleModel
from reportgen.infrastructure.secret_store import migrate_env_file
from reportgen.infrastructure.settings import Provider

FAKE_KEY = "sk-or-v1-" + "a1b2c3d4e5f6a7b8c9d0e1f2"
ROOT = Path(__file__).resolve().parent.parent


class MemoryStore:
    def __init__(self):
        self.values = {}

    def set(self, name, value):
        self.values[name] = value


def test_redact_hides_known_and_pattern_secrets():
    bearer = "abcdefgh" + "ijklmnop12"
    text = f"ключ {FAKE_KEY} и Authorization: " + "Bearer " + bearer + " и api_key = verysecretvalue"
    cleaned = redact(text, ("verysecretvalue",))
    assert FAKE_KEY not in cleaned and bearer not in cleaned and "verysecretvalue" not in cleaned
    assert MASK in cleaned


def test_find_tokens_ignores_ordinary_code():
    assert find_tokens("api_key=resolve_secret(api_key_env)") == []
    assert find_tokens(f"x = '{FAKE_KEY}'") == [FAKE_KEY]


def test_provider_repr_does_not_contain_key():
    provider = Provider("cloud", "d", "http://x", FAKE_KEY, "OPENROUTER_API_KEY", None, {"writer": ["m"]})
    assert FAKE_KEY not in repr(provider)


def test_model_scrubs_prompts_and_errors():
    provider = Provider("cloud", "d", "http://x", FAKE_KEY, "OPENROUTER_API_KEY", None, {"writer": ["m"]})
    model = OpenAICompatibleModel(provider)
    assert FAKE_KEY not in model._scrub(f"ошибка {FAKE_KEY}")


def test_env_migration_blanks_values_and_reports_names_only(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(f"REPORTGEN_PROVIDER=cloud\nOPENROUTER_API_KEY={FAKE_KEY}\nGEMINI_API_KEY=\n", encoding="utf-8")
    store = MemoryStore()
    names = migrate_env_file(env, store)
    assert names == ["OPENROUTER_API_KEY"]
    assert store.values["OPENROUTER_API_KEY"] == FAKE_KEY
    assert FAKE_KEY not in env.read_text(encoding="utf-8")
    assert "REPORTGEN_PROVIDER=cloud" in env.read_text(encoding="utf-8")


def test_env_files_are_ignored_by_git():
    for name in (".env", ".claude/settings.local.json", "workspace/style_profile.json"):
        result = subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT)
        assert result.returncode == 0, f"{name} должен быть в .gitignore"
