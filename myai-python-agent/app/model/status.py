from __future__ import annotations

from app.model.config import LLMSettings, load_llm_settings


def model_status(settings: LLMSettings | None = None) -> dict:
    settings = settings or load_llm_settings()
    key_configured = bool(
        settings.ark_api_key
        or settings.openai_compatible_api_key
        or settings.openai_compatible_embedding_api_key
    )
    return {
        "fallback_to_stub": settings.fallback_to_stub,
        "provider_auth_configured": key_configured,
        "memory_llm_extractor_enabled": settings.memory_llm_extractor_enabled,
        "roles": {
            "chat": _llm_role_status(
                provider=settings.chat_provider,
                model_id=settings.chat_model_id,
                key_configured=_provider_key_configured(settings.chat_provider, settings),
                fallback_to_stub=settings.fallback_to_stub,
            ),
            "task": _llm_role_status(
                provider=settings.task_provider,
                model_id=settings.task_model_id,
                key_configured=_provider_key_configured(settings.task_provider, settings),
                fallback_to_stub=settings.fallback_to_stub,
            ),
            "memory": _llm_role_status(
                provider=settings.memory_provider,
                model_id=settings.memory_model_id,
                key_configured=_provider_key_configured(settings.memory_provider, settings),
                fallback_to_stub=settings.fallback_to_stub,
            ),
            "embedding": _embedding_status(
                provider=settings.embedding_provider,
                model_id=settings.embedding_model_id,
                key_configured=_provider_key_configured(
                    settings.embedding_provider,
                    settings,
                    embedding=True,
                ),
            ),
        },
    }


def _llm_role_status(*, provider: str, model_id: str, key_configured: bool, fallback_to_stub: bool) -> dict:
    missing = []
    if provider not in {"stub", "volcengine", "openai_compatible"}:
        missing.append("unsupported_provider")
    if provider != "stub" and not model_id:
        missing.append("model_id")
    if provider in {"volcengine"} and not key_configured:
        missing.append("api_key")
    return {
        "provider": provider,
        "model_id": model_id,
        "kind": "stub" if provider == "stub" else "real",
        "effective_mode": _effective_mode(provider, missing, fallback_to_stub),
        "fallback_to_stub": fallback_to_stub,
        "missing": missing,
    }


def _embedding_status(*, provider: str, model_id: str, key_configured: bool) -> dict:
    missing = []
    if provider not in {"stub", "volcengine", "openai_compatible"}:
        missing.append("unsupported_provider")
    if provider != "stub" and not model_id:
        missing.append("model_id")
    if provider in {"volcengine"} and not key_configured:
        missing.append("api_key")
    if provider == "stub":
        effective_mode = "stub"
    elif missing:
        effective_mode = "misconfigured"
    else:
        effective_mode = "real_fail_closed"
    return {
        "provider": provider,
        "model_id": model_id,
        "kind": "stub" if provider == "stub" else "real",
        "effective_mode": effective_mode,
        "fallback_to_stub": False,
        "missing": missing,
    }


def _effective_mode(provider: str, missing: list[str], fallback_to_stub: bool) -> str:
    if provider == "stub":
        return "stub"
    if missing:
        return "stub_fallback" if fallback_to_stub else "misconfigured"
    return "real_with_fallback" if fallback_to_stub else "real"


def _provider_key_configured(
    provider: str,
    settings: LLMSettings,
    *,
    embedding: bool = False,
) -> bool:
    if provider == "volcengine":
        return bool(settings.ark_api_key)
    if provider == "openai_compatible":
        key = (
            settings.openai_compatible_embedding_api_key
            if embedding
            else settings.openai_compatible_api_key
        )
        return bool(key)
    return False
