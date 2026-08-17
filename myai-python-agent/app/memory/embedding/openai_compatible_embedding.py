from __future__ import annotations

import httpx
from openai import OpenAI

from app.memory.embedding.validation import validate_embedding_vector
from app.model.openai_compatible_llm import DEFAULT_LOCAL_BASE_URL


_LOCAL_PLACEHOLDER_API_KEY = "myai-local"


class OpenAICompatibleEmbedding:
    """Embedding client for a local OpenAI-compatible model server."""

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_LOCAL_BASE_URL,
        api_key: str = "",
        timeout_seconds: float = 3.0,
        max_retries: int = 0,
        expected_dimensions: int = 0,
        trust_env_proxy: bool = False,
        client=None,
    ):
        if not model.strip():
            raise RuntimeError("MYAI_EMBEDDING_MODEL_ID is not set for openai_compatible provider")
        if not base_url.strip():
            raise RuntimeError("MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL is not set")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if expected_dimensions < 0:
            raise ValueError("expected_dimensions must be non-negative")

        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.expected_dimensions = expected_dimensions
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

    def embed(self, text: str):
        if not text or not text.strip():
            raise ValueError("Text for embedding cannot be empty")

        response = self.client.embeddings.create(
            model=self.model,
            input=text.strip(),
        )
        if not response.data:
            raise ValueError("Embedding provider returned no data")
        return validate_embedding_vector(
            response.data[0].embedding,
            expected_dimensions=self.expected_dimensions,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "OpenAICompatibleEmbedding":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
