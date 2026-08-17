from __future__ import annotations

import math
import os
from dataclasses import dataclass


def _get_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(
    name: str,
    default: float,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = float(_get_env(name, str(default)))
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def _get_int(name: str, default: int, *, minimum: int | None = None) -> int:
    value = int(_get_env(name, str(default)))
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _get_optional_int(name: str, default: int | None) -> int | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return None
    return int(value)


def _same_endpoint(left: str, right: str) -> bool:
    return left.strip().rstrip("/").casefold() == right.strip().rstrip("/").casefold()


@dataclass(frozen=True)
class LLMSettings:
    default_provider: str
    chat_provider: str
    task_provider: str
    memory_provider: str
    embedding_provider: str
    memory_llm_extractor_enabled: bool
    fallback_to_stub: bool
    temperature: float
    ark_api_key: str
    ark_base_url: str
    default_model_id: str
    chat_model_id: str
    task_model_id: str
    memory_model_id: str
    embedding_model_id: str
    memory_collection_name: str
    knowledge_collection_name: str
    openai_compatible_base_url: str = "http://127.0.0.1:11434/v1"
    openai_compatible_api_key: str = ""
    openai_compatible_embedding_base_url: str = "http://127.0.0.1:11434/v1"
    openai_compatible_embedding_api_key: str = ""
    llm_request_timeout_seconds: float = 3.0
    llm_max_retries: int = 0
    llm_seed: int | None = 42
    llm_max_tokens: int = 512
    embedding_request_timeout_seconds: float = 3.0
    embedding_max_retries: int = 0
    embedding_expected_dimensions: int = 0
    model_trust_env_proxy: bool = False


def load_llm_settings() -> LLMSettings:
    default_provider = _get_env("MYAI_LLM_PROVIDER", "stub").lower()
    default_model_id = _get_env("ARK_MODEL_ID", "")
    embedding_provider = _get_env("MYAI_EMBEDDING_PROVIDER", "stub").lower()
    embedding_model_id = _get_env("MYAI_EMBEDDING_MODEL_ID", _get_env("ARK_EMBEDDING_MODEL_ID", ""))
    openai_compatible_base_url = _get_env(
        "MYAI_OPENAI_COMPATIBLE_BASE_URL",
        "http://127.0.0.1:11434/v1",
    )
    openai_compatible_api_key = os.getenv("MYAI_OPENAI_COMPATIBLE_API_KEY", "").strip()
    openai_compatible_embedding_base_url = _get_env(
        "MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL",
        openai_compatible_base_url,
    )
    openai_compatible_embedding_api_key = os.getenv(
        "MYAI_OPENAI_COMPATIBLE_EMBEDDING_API_KEY",
        "",
    ).strip()
    if (
        not openai_compatible_embedding_api_key
        and _same_endpoint(openai_compatible_embedding_base_url, openai_compatible_base_url)
    ):
        openai_compatible_embedding_api_key = openai_compatible_api_key

    return LLMSettings(
        default_provider=default_provider,
        chat_provider=_get_env("MYAI_CHAT_PROVIDER", default_provider).lower(),
        task_provider=_get_env("MYAI_TASK_PROVIDER", default_provider).lower(),
        memory_provider=_get_env("MYAI_MEMORY_PROVIDER", default_provider).lower(),
        embedding_provider=embedding_provider,
        memory_llm_extractor_enabled=_get_bool("MYAI_MEMORY_LLM_EXTRACTOR_ENABLED", False),
        fallback_to_stub=_get_bool("MYAI_LLM_FALLBACK_TO_STUB", True),
        temperature=_get_float(
            "MYAI_LLM_TEMPERATURE",
            0.7,
            minimum=0.0,
            maximum=2.0,
        ),
        ark_api_key=os.getenv("ARK_API_KEY", "").strip(),
        ark_base_url=_get_env("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
        default_model_id=default_model_id,
        chat_model_id=_get_env("MYAI_CHAT_MODEL_ID", default_model_id),
        task_model_id=_get_env("MYAI_TASK_MODEL_ID", default_model_id),
        memory_model_id=_get_env("MYAI_MEMORY_MODEL_ID", default_model_id),
        embedding_model_id=embedding_model_id,
        memory_collection_name=_get_env(
            "MYAI_MEMORY_COLLECTION",
            _build_collection_name("long_term_memory", embedding_provider, embedding_model_id),
        ),
        knowledge_collection_name=_get_env(
            "MYAI_KNOWLEDGE_COLLECTION",
            _build_collection_name("knowledge_base", embedding_provider, embedding_model_id),
        ),
        openai_compatible_base_url=openai_compatible_base_url,
        openai_compatible_api_key=openai_compatible_api_key,
        openai_compatible_embedding_base_url=openai_compatible_embedding_base_url,
        openai_compatible_embedding_api_key=openai_compatible_embedding_api_key,
        llm_request_timeout_seconds=_get_float(
            "MYAI_LLM_REQUEST_TIMEOUT_SECONDS",
            3.0,
            minimum=0.1,
        ),
        llm_max_retries=_get_int("MYAI_LLM_MAX_RETRIES", 0, minimum=0),
        llm_seed=_get_optional_int("MYAI_LLM_SEED", 42),
        llm_max_tokens=_get_int("MYAI_LLM_MAX_TOKENS", 512, minimum=1),
        embedding_request_timeout_seconds=_get_float(
            "MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS",
            3.0,
            minimum=0.1,
        ),
        embedding_max_retries=_get_int("MYAI_EMBEDDING_MAX_RETRIES", 0, minimum=0),
        embedding_expected_dimensions=_get_int(
            "MYAI_EMBEDDING_EXPECTED_DIMENSIONS",
            0,
            minimum=0,
        ),
        model_trust_env_proxy=_get_bool("MYAI_MODEL_TRUST_ENV_PROXY", False),
    )


def _build_collection_name(prefix: str, provider: str, model_id: str) -> str:
    raw = f"{prefix}_{provider}_{model_id or 'default'}"
    sanitized = []
    for ch in raw.lower():
        if ch.isalnum():
            sanitized.append(ch)
        else:
            sanitized.append("_")
    collapsed = "".join(sanitized)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_")
