from __future__ import annotations

import httpx
from openai import OpenAI

from app.model.base import BaseLLM


DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:11434/v1"
_LOCAL_PLACEHOLDER_API_KEY = "myai-local"


class OpenAICompatibleLLM(BaseLLM):
    """Chat-completions client for a local OpenAI-compatible model server."""

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.7,
        base_url: str = DEFAULT_LOCAL_BASE_URL,
        api_key: str = "",
        timeout_seconds: float = 3.0,
        max_retries: int = 0,
        seed: int | None = 42,
        max_tokens: int = 512,
        trust_env_proxy: bool = False,
        client=None,
    ):
        if not model_id.strip():
            raise RuntimeError("MYAI_*_MODEL_ID is not set for openai_compatible provider")
        if not base_url.strip():
            raise RuntimeError("MYAI_OPENAI_COMPATIBLE_BASE_URL is not set")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be greater than zero")

        self.model_id = model_id.strip()
        self.temperature = temperature
        self.seed = seed
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._closed = False
        if client is None:
            http_client = httpx.Client(timeout=timeout_seconds, trust_env=trust_env_proxy)
            try:
                client = OpenAI(
                    api_key=api_key or _LOCAL_PLACEHOLDER_API_KEY,
                    base_url=self.base_url,
                    timeout=timeout_seconds,
                    max_retries=max_retries,
                    http_client=http_client,
                )
            except Exception:
                http_client.close()
                raise
        self.client = client

    def generate(self, prompt: str) -> str:
        request = {
            "model": self.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a personal AI assistant with long-term memory.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            request["seed"] = self.seed

        response = self.client.chat.completions.create(**request)
        if not response.choices:
            raise RuntimeError("OpenAI-compatible provider returned no completion choices")
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenAI-compatible provider returned empty text content")
        return content.strip()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "OpenAICompatibleLLM":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
