import os
import httpx
import numpy as np

from volcenginesdkarkruntime import Ark

from app.memory.embedding.validation import validate_embedding_vector

# 接入真实embedding模型 api


class EmbeddingClient:
    """
    Embedding client based on Volcengine (Doubao-embedding-vision).
    """
    def __init__(
            self,
            model: str,
            api_key: str | None = None,
            expected_dimensions: int = 0,
            client=None,
    ):
        self.api_key = api_key or os.environ.get("ARK_API_KEY")
        if not self.api_key:
            raise RuntimeError("ARK_API_KEY environment variable is not set")
        self.model = model
        self.expected_dimensions = expected_dimensions
        timeout = float(os.getenv("MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS", "3"))
        max_retries = int(os.getenv("MYAI_EMBEDDING_MAX_RETRIES", "0"))
        trust_env_proxy = _get_bool("MYAI_MODEL_TRUST_ENV_PROXY", False)
        self._owns_client = client is None
        self._closed = False
        if client is None:
            http_client = httpx.Client(timeout=timeout, trust_env=trust_env_proxy)
            try:
                client = Ark(
                    api_key=self.api_key,
                    timeout=timeout,
                    max_retries=max_retries,
                    http_client=http_client,
                )
            except Exception:
                http_client.close()
                raise
        self.client = client

    def embed(self, text: str) -> np.ndarray:
        """
        Embed a single text into a vector.
        """
        if not text or not text.strip():
            raise ValueError("Text for embedding cannot be empty")

        resp = self.client.multimodal_embeddings.create(
            model=self.model,
            input=[{
                "type":"text",
                "text": text.strip()
            }]
        )

        response = resp.data.embedding
        return validate_embedding_vector(response, self.expected_dimensions)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "EmbeddingClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
