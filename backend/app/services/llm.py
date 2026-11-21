"""LLM provider abstraction: Anthropic, OpenAI-compatible (OpenAI/Ollama) and an offline demo provider."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from ..config import Settings, get_settings

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the provider call fails (network, auth, refusal...). Message is user-friendly."""


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""
    local: bool = False  # True => no data leaves the machine
    is_demo: bool = False

    @abstractmethod
    def complete(self, system: str, messages: list[dict], *, json_mode: bool = True, max_tokens: int = 8000) -> str:
        """messages: [{'role': 'user'|'assistant', 'content': str}, ...]. Returns the raw text reply."""

    def describe(self) -> dict:
        return {"provider": self.name, "model": self.model, "local": self.local, "demo": self.is_demo}


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    local = False

    def __init__(self, api_key: str, model: str, timeout: float = 120.0):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
        self.model = model

    def complete(self, system: str, messages: list[dict], *, json_mode: bool = True, max_tokens: int = 8000) -> str:
        a = self._anthropic
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system, messages=messages
            )
        except a.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY.") from e
        except a.NotFoundError as e:
            raise LLMError(f"Anthropic model '{self.model}' was not found. Check ANTHROPIC_MODEL.") from e
        except a.RateLimitError as e:
            raise LLMError("Anthropic rate limit reached. Try again in a minute.") from e
        except a.APIConnectionError as e:
            raise LLMError("Could not reach the Anthropic API. Check your internet connection.") from e
        except a.APIStatusError as e:
            raise LLMError(f"Anthropic API error ({e.status_code}).") from e
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined to process this transcript.")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


class OpenAICompatProvider(LLMProvider):
    """Works with OpenAI, Ollama (/v1), LM Studio, vLLM and other OpenAI-compatible servers."""

    def __init__(self, name: str, base_url: str, model: str, api_key: str = "", timeout: float = 120.0, local: bool = False):
        self.name, self.base_url, self.model, self.api_key, self.timeout, self.local = (
            name, base_url.rstrip("/"), model, api_key, timeout, local,
        )

    def complete(self, system: str, messages: list[dict], *, json_mode: bool = True, max_tokens: int = 8000) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": 0.1,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
                if r.status_code == 400 and json_mode:  # server may not support response_format
                    body.pop("response_format", None)
                    r = c.post(f"{self.base_url}/chat/completions", headers=headers, json=body)
        except httpx.ConnectError as e:
            hint = " Is Ollama running (`ollama serve`)?" if self.name == "ollama" else ""
            raise LLMError(f"Could not connect to {self.base_url}.{hint}") from e
        except httpx.TimeoutException as e:
            raise LLMError(f"The {self.name} model timed out. Try a smaller model or a shorter transcript.") from e
        if r.status_code in (401, 403):
            raise LLMError(f"{self.name} rejected the API key.")
        if r.status_code == 404:
            raise LLMError(f"{self.name} model '{self.model}' was not found (try `ollama pull {self.model}`).")
        if r.status_code == 429:
            raise LLMError(f"{self.name} rate limit reached. Try again shortly.")
        if r.status_code >= 400:
            raise LLMError(f"{self.name} API error ({r.status_code}).")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"Unexpected response format from {self.name}.") from e


def build_provider(settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    p = s.effective_provider
    try:
        if p == "anthropic":
            if not s.anthropic_api_key:
                raise LLMError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set.")
            return AnthropicProvider(s.anthropic_api_key, s.anthropic_model, s.llm_timeout)
        if p == "openai":
            if not s.openai_api_key:
                raise LLMError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set.")
            return OpenAICompatProvider("openai", s.openai_base_url, s.openai_model, s.openai_api_key, s.llm_timeout)
        if p == "ollama":
            return OpenAICompatProvider("ollama", s.ollama_base_url, s.ollama_model, "", s.llm_timeout, local=True)
    except LLMError:
        log.warning("Falling back to demo provider: misconfigured %s", p)
    from .demo import DemoProvider

    return DemoProvider()


_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = build_provider()
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None
