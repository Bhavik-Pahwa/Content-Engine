"""LLM provider implementations for writing."""

from __future__ import annotations

from typing import Protocol
import json
import urllib.error
import urllib.request

from content_engine.providers import ProviderMetadata
from content_engine.writing.models import LLMRequest, LLMResponse


class TextGenerationProvider(Protocol):
    metadata: ProviderMetadata

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text for a writing request."""


class OpenRouterProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        endpoint: str = "https://openrouter.ai/api/v1/chat/completions",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint
        self.metadata = ProviderMetadata(
            name="openrouter",
            provider_type="llm",
            version="0.1.0",
            requires_network=True,
            cost_profile="provider-dependent",
            capabilities=("text_generation",),
        )

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise LLMProviderError("OPENROUTER_API_KEY is required for OpenRouter generation")
        model = request.model or self.model
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": 0.7,
        }
        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost/content-engine",
                "X-Title": "Content Engine",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMProviderError(f"OpenRouter generation failed: {exc}") from exc
        try:
            choice = data["choices"][0]
            text = str(choice["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("OpenRouter response did not include generated content") from exc
        usage = data.get("usage") if isinstance(data, dict) else {}
        return LLMResponse(
            text=text,
            provider_name=self.metadata.name,
            model=model,
            token_usage=_token_usage(usage),
            metadata={"provider_response_id": data.get("id"), "finish_reason": choice.get("finish_reason")},
        )


class LLMProviderError(RuntimeError):
    """Raised when text generation fails."""


def _token_usage(value) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(raw) for key, raw in value.items() if isinstance(raw, int)}
