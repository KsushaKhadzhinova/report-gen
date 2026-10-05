import pytest

from reportgen.infrastructure import llm_client
from reportgen.infrastructure.llm_client import LLMError, OpenAICompatibleModel, RateLimitExhausted
from reportgen.infrastructure.settings import Provider


class FakeResponse:
    def __init__(self, status=200, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._body


def reply(text, finish="stop"):
    return FakeResponse(body={"choices": [{"message": {"content": text}, "finish_reason": finish}]})


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, url, json, headers, timeout):
        self.payloads.append(json)
        return self.responses.pop(0)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)
    provider = Provider("cloud", "d", "http://x", "k", "KEY", None, {"writer": ["m1", "m2"], "utility": ["m1"]})
    return OpenAICompatibleModel(provider)


def test_rate_limit_is_retried_and_honours_retry_after(model):
    waits = []
    llm_client.time.sleep = waits.append
    model.session = FakeSession([FakeResponse(429, headers={"Retry-After": "7"}), reply("готово")])
    assert model.complete("writer", "s", "u") == "готово"
    assert waits == [7.0]


def test_truncated_reasoning_answer_is_retried_with_larger_budget(model):
    model.session = FakeSession([reply("", finish="length"), reply("текст")])
    assert model.complete("writer", "s", "u", max_tokens=1000) == "текст"
    assert [p["max_tokens"] for p in model.session.payloads] == [1000, 2000]


def test_falls_back_to_next_model_when_first_keeps_failing(model):
    model.retries = 2
    model.session = FakeSession([FakeResponse(503), FakeResponse(503), reply("из резерва")])
    assert model.complete("writer", "s", "u") == "из резерва"
    assert [p["model"] for p in model.session.payloads] == ["m1", "m1", "m2"]


def test_error_text_is_scrubbed(model):
    secret = "sk-or-v1-" + "0123456789abcdef0123"
    model.session = FakeSession([FakeResponse(401, text=f"bad key {secret}")] * 2)
    with pytest.raises(LLMError) as error:
        model.complete("writer", "s", "u")
    assert secret not in str(error.value)


def test_long_rate_limit_stops_at_once_and_names_the_reset_time(model):
    far_future_ms = str(int((llm_client.time.time() + 6 * 3600) * 1000))
    model.session = FakeSession([FakeResponse(429, headers={"X-RateLimit-Reset": far_future_ms})] * 10)
    with pytest.raises(RateLimitExhausted) as error:
        model.complete("writer", "s", "u")
    assert "сбросится" in str(error.value)
    assert len(model.session.payloads) == 1


def test_short_rate_limit_is_still_retried(model):
    soon_ms = str(int((llm_client.time.time() + 5) * 1000))
    model.session = FakeSession([FakeResponse(429, headers={"X-RateLimit-Reset": soon_ms}), reply("готово")])
    assert model.complete("writer", "s", "u") == "готово"
