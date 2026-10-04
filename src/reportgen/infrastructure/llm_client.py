from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from reportgen.domain.redaction import redact
from reportgen.infrastructure.settings import Provider, get_provider

RETRY_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
MODELS_TIMEOUT_SECONDS = 30
AUTO_MODEL = "auto"
CHECK_MAX_TOKENS = 512


class LLMError(RuntimeError):
    pass


class OpenAICompatibleModel:
    """Клиент OpenAI-совместимого API с резервными моделями для каждой роли."""

    def __init__(self, provider: Provider | None = None, timeout: int = 300, retries: int = 3) -> None:
        self.provider = provider or get_provider()
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    @property
    def identity(self) -> str:
        roles = "|".join(f"{role}={','.join(models)}" for role, models in sorted(self.provider.roles.items()))
        return f"{self.provider.name}:{roles}"

    def complete(self, role: str, system: str, user: str, temperature: float = 0.6, max_tokens: int | None = None) -> str:
        messages = [{"role": "system", "content": self._scrub(system)}, {"role": "user", "content": self._scrub(user)}]
        return self._complete(role, messages, temperature, max_tokens)

    def describe_image(self, image: Path, instruction: str) -> str:
        encoded = base64.b64encode(image.read_bytes()).decode("ascii")
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        content = [
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]
        return self._complete("vision", [{"role": "user", "content": content}], 0.3, 400)

    def check(self) -> list[tuple[str, str, bool, str]]:
        """Для каждой роли возвращает первую отвечающую модель цепочки или последнюю ошибку."""
        results = []
        for role, models in self.provider.roles.items():
            outcome = (role, models[0], False, "нет моделей")
            for model in models:
                try:
                    self._request(model, [{"role": "user", "content": "Ответь одним словом: да"}], 0, CHECK_MAX_TOKENS)
                    outcome = (role, model, True, "ok")
                    break
                except LLMError as error:
                    outcome = (role, model, False, self._scrub(str(error))[:120])
            results.append(outcome)
        return results

    def _complete(self, role: str, messages: list[dict], temperature: float, max_tokens: int | None) -> str:
        errors = []
        for model in self._candidates(role):
            try:
                return self._request(model, messages, temperature, max_tokens)
            except LLMError as error:
                errors.append(str(error))
        raise LLMError(f"Все модели роли «{role}» недоступны:\n  " + "\n  ".join(errors))

    def _scrub(self, value: str) -> str:
        return redact(value, (self.provider.api_key,) if self.provider.api_key else ())

    def _candidates(self, role: str) -> list[str]:
        models = self.provider.roles.get(role) or self.provider.roles["utility"]
        return [self._first_available_model()] if models == [AUTO_MODEL] else models

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider.api_key:
            headers["Authorization"] = f"Bearer {self.provider.api_key}"
        return headers

    def _first_available_model(self) -> str:
        response = self.session.get(f"{self.provider.base_url}/models", headers=self._headers(), timeout=MODELS_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            raise LLMError("Сервер не вернул ни одной модели")
        return data[0]["id"]

    def _request(self, model: str, messages: list[dict], temperature: float, max_tokens: int | None) -> str:
        payload = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        last_problem = ""
        for attempt in range(self.retries):
            response = self._post_once(payload)
            if response is None or response.status_code in RETRY_STATUSES:
                last_problem = "нет ответа" if response is None else f"HTTP {response.status_code}"
                time.sleep(2**attempt * 2)
                continue
            if response.status_code != 200:
                raise LLMError(f"{model}: HTTP {response.status_code} {self._scrub(response.text[:200])}")
            text = self._extract_text(response.json())
            if text:
                return text
            last_problem = "пустой ответ"
        raise LLMError(f"{model}: {last_problem}")

    def _post_once(self, payload: dict) -> requests.Response | None:
        try:
            return self.session.post(
                f"{self.provider.base_url}/chat/completions", json=payload, headers=self._headers(), timeout=self.timeout
            )
        except requests.RequestException:
            return None

    @staticmethod
    def _extract_text(body: dict) -> str:
        choices = body.get("choices") or []
        return (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
