from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from reportgen.settings import Provider, get_provider

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class LLM:
    """Клиент OpenAI-совместимого API с резервными моделями для каждой роли."""

    def __init__(self, provider: Provider | None = None, timeout: int = 300, retries: int = 3):
        self.provider = provider or get_provider()
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.provider.api_key:
            headers["Authorization"] = f"Bearer {self.provider.api_key}"
        return headers

    def _models_for(self, role: str) -> list[str]:
        models = self.provider.roles.get(role) or self.provider.roles["utility"]
        if models == ["auto"]:
            return [self._first_available_model()]
        return models

    def _first_available_model(self) -> str:
        response = self.session.get(
            f"{self.provider.base_url}/models", headers=self._headers(), timeout=30
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        if not data:
            raise LLMError("Сервер не вернул ни одной модели")
        return data[0]["id"]

    def _post(self, model: str, messages: list[dict], temperature: float, max_tokens: int | None) -> str:
        payload: dict = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        url = f"{self.provider.base_url}/chat/completions"
        last_error = ""
        for attempt in range(self.retries):
            try:
                response = self.session.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            except requests.RequestException as exc:
                last_error = str(exc)
                time.sleep(2 ** attempt)
                continue
            if response.status_code in RETRY_STATUSES:
                last_error = f"HTTP {response.status_code}"
                time.sleep(2 ** attempt * 2)
                continue
            if response.status_code != 200:
                raise LLMError(f"{model}: HTTP {response.status_code} {response.text[:200]}")
            choices = response.json().get("choices") or []
            text = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
            if text:
                return text
            last_error = "пустой ответ"
        raise LLMError(f"{model}: {last_error}")

    def chat(
        self,
        role: str,
        system: str,
        user: str,
        temperature: float = 0.6,
        max_tokens: int | None = None,
    ) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self._complete(role, messages, temperature, max_tokens)

    def describe_image(self, image: Path, instruction: str) -> str:
        encoded = base64.b64encode(image.read_bytes()).decode("ascii")
        mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        content = [
            {"type": "text", "text": instruction},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
        ]
        return self._complete("vision", [{"role": "user", "content": content}], 0.3, 400)

    def _complete(self, role: str, messages: list[dict], temperature: float, max_tokens: int | None) -> str:
        errors: list[str] = []
        for model in self._models_for(role):
            try:
                return self._post(model, messages, temperature, max_tokens)
            except LLMError as exc:
                errors.append(str(exc))
        raise LLMError("Все модели роли «%s» недоступны:\n  %s" % (role, "\n  ".join(errors)))

    def check(self) -> list[tuple[str, str, bool, str]]:
        """Проверяет доступность первой модели каждой роли."""
        results = []
        for role, models in self.provider.roles.items():
            model = models[0]
            try:
                self._post(model, [{"role": "user", "content": "Ответь одним словом: да"}], 0, 8)
                results.append((role, model, True, "ok"))
            except (LLMError, requests.RequestException) as exc:
                results.append((role, model, False, str(exc)[:120]))
        return results
