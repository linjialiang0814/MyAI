import os

import httpx
from openai import OpenAI

from app.model.base import BaseLLM


class VolcengineLLM(BaseLLM):
    """Volcengine ARK model backend compatible with the OpenAI SDK."""

    def __init__(
        self,
        model_id: str,
        temperature: float = 0.7,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        api_key: str | None = None,
        client=None,
    ):
        api_key = api_key or os.getenv("ARK_API_KEY")
        if not api_key:
            raise RuntimeError("ARK_API_KEY environment variable is not set")
        if not model_id:
            raise RuntimeError("ARK_MODEL_ID environment variable is not set")

        timeout = float(os.getenv("MYAI_LLM_REQUEST_TIMEOUT_SECONDS", "3"))
        max_retries = int(os.getenv("MYAI_LLM_MAX_RETRIES", "0"))
        trust_env_proxy = _get_bool("MYAI_MODEL_TRUST_ENV_PROXY", False)
        self._owns_client = client is None
        self._closed = False
        if client is None:
            http_client = httpx.Client(timeout=timeout, trust_env=trust_env_proxy)
            try:
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=timeout,
                    max_retries=max_retries,
                    http_client=http_client,
                )
            except Exception:
                http_client.close()
                raise
        self.client = client
        self.model_id = model_id
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model_id,
            input=[
                {
                    "role": "system",
                    "content": "You are a personal AI assistant with long-term memory.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=self.temperature,
        )
        return response.output_text.strip()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "VolcengineLLM":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
