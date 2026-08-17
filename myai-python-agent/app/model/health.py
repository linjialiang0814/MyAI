from __future__ import annotations

import time
import os
from datetime import datetime, timezone
from typing import Any

from app.memory.embedding.openai_compatible_embedding import OpenAICompatibleEmbedding
from app.memory.embedding.volc_embedding import EmbeddingClient
from app.model.config import LLMSettings, load_llm_settings
from app.model.openai_compatible_llm import OpenAICompatibleLLM
from app.model.status import model_status
from app.model.volc_llm import VolcengineLLM
from app.runtime.storage_redaction import sanitize_text_for_storage

_LAST_PROBE: dict[str, Any] | None = None


def last_model_probe() -> dict[str, Any] | None:
    return _LAST_PROBE


def probe_model_health(settings: LLMSettings | None = None) -> dict[str, Any]:
    global _LAST_PROBE
    settings = settings or load_llm_settings()
    started_at = _now()
    role_results = {
        "chat": _probe_llm_role("chat", settings.chat_provider, settings.chat_model_id, settings),
        "task": _probe_llm_role("task", settings.task_provider, settings.task_model_id, settings),
        "memory": _probe_llm_role("memory", settings.memory_provider, settings.memory_model_id, settings),
        "embedding": _probe_embedding(settings.embedding_provider, settings.embedding_model_id, settings),
    }
    real_roles = [payload for payload in role_results.values() if payload["kind"] == "real"]
    failed_roles = [payload for payload in real_roles if not payload["ok"]]
    if not real_roles:
        status = "stub_only"
    elif failed_roles:
        status = "degraded"
    else:
        status = "healthy"
    payload = {
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "summary": {
            "real_roles": len(real_roles),
            "successful_real_roles": len(real_roles) - len(failed_roles),
            "failed_real_roles": len(failed_roles),
            "fallback_to_stub": settings.fallback_to_stub,
        },
        "network": _network_probe_metadata(),
        "roles": role_results,
    }
    _LAST_PROBE = payload
    return payload


def model_status_with_probe(settings: LLMSettings | None = None) -> dict[str, Any]:
    payload = model_status(settings)
    payload["last_probe"] = last_model_probe()
    return payload


def _probe_llm_role(role: str, provider: str, model_id: str, settings: LLMSettings) -> dict[str, Any]:
    base = _base_role_payload(role, provider, model_id)
    if provider == "stub":
        return {**base, "ok": True, "status": "stub", "latency_ms": 0}
    missing = _missing_real_provider_fields(provider, model_id, settings)
    if missing:
        return {**base, "ok": False, "status": "misconfigured", "missing": missing, "latency_ms": 0}
    started = time.perf_counter()
    llm = None
    try:
        if provider == "volcengine":
            llm = VolcengineLLM(
                model_id=model_id,
                temperature=0.0,
                base_url=settings.ark_base_url,
                api_key=settings.ark_api_key,
            )
        elif provider == "openai_compatible":
            llm = OpenAICompatibleLLM(
                model_id=model_id,
                temperature=0.0,
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key,
                timeout_seconds=settings.llm_request_timeout_seconds,
                max_retries=settings.llm_max_retries,
                seed=settings.llm_seed,
                max_tokens=min(settings.llm_max_tokens, 16),
                trust_env_proxy=settings.model_trust_env_proxy,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        reply = llm.generate("Health probe. Reply with OK.")
        return {
            **base,
            "ok": bool(reply),
            "status": "healthy" if reply else "empty_response",
            "latency_ms": _elapsed_ms(started),
            "response_chars": len(reply or ""),
        }
    except Exception as exc:
        return {
            **base,
            "ok": False,
            "status": "failed",
            "latency_ms": _elapsed_ms(started),
            "error_type": _classify_error(exc),
            "error_message": _safe_error_message(exc),
        }
    finally:
        _close_client(llm)


def _probe_embedding(provider: str, model_id: str, settings: LLMSettings) -> dict[str, Any]:
    base = {
        **_base_role_payload("embedding", provider, model_id),
        "fallback_to_stub": False,
        "effective_mode": "stub" if provider == "stub" else "real_fail_closed",
    }
    if provider == "stub":
        return {**base, "ok": True, "status": "stub", "latency_ms": 0}
    missing = _missing_real_provider_fields(provider, model_id, settings)
    if missing:
        return {
            **base,
            "ok": False,
            "status": "misconfigured",
            "effective_mode": "misconfigured",
            "missing": missing,
            "latency_ms": 0,
        }
    started = time.perf_counter()
    client = None
    try:
        if provider == "volcengine":
            client = EmbeddingClient(
                model=model_id,
                api_key=settings.ark_api_key,
                expected_dimensions=settings.embedding_expected_dimensions,
            )
        elif provider == "openai_compatible":
            client = OpenAICompatibleEmbedding(
                model=model_id,
                base_url=settings.openai_compatible_embedding_base_url,
                api_key=settings.openai_compatible_embedding_api_key,
                timeout_seconds=settings.embedding_request_timeout_seconds,
                max_retries=settings.embedding_max_retries,
                expected_dimensions=settings.embedding_expected_dimensions,
                trust_env_proxy=settings.model_trust_env_proxy,
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
        vector = client.embed("health probe")
        dimensions = int(getattr(vector, "shape", [len(vector)])[0])
        return {
            **base,
            "ok": dimensions > 0,
            "status": "healthy" if dimensions > 0 else "empty_response",
            "latency_ms": _elapsed_ms(started),
            "dimensions": dimensions,
        }
    except Exception as exc:
        return {
            **base,
            "ok": False,
            "status": "failed",
            "latency_ms": _elapsed_ms(started),
            "error_type": _classify_error(exc),
            "error_message": _safe_error_message(exc),
        }
    finally:
        _close_client(client)


def _base_role_payload(role: str, provider: str, model_id: str) -> dict[str, Any]:
    return {
        "role": role,
        "provider": provider,
        "model_id": model_id,
        "kind": "stub" if provider == "stub" else "real",
    }


def _missing_real_provider_fields(provider: str, model_id: str, settings: LLMSettings) -> list[str]:
    missing = []
    if provider not in {"stub", "volcengine", "openai_compatible"}:
        missing.append("unsupported_provider")
    if provider != "stub" and not model_id:
        missing.append("model_id")
    if provider in {"volcengine"} and not settings.ark_api_key:
        missing.append("provider_auth")
    return missing


def _classify_error(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if "authentication" in text or "unauthorized" in text or "401" in text:
        return "authentication"
    if "not found" in text or "404" in text or "model" in text and "not" in text:
        return "model_not_found"
    if "rate" in text or "429" in text:
        return "rate_limit"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connection" in text or "connect" in text or "dns" in text:
        return "network"
    if "5" in text and ("server" in text or "status" in text):
        return "provider_5xx"
    return "unknown"


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return str(sanitize_text_for_storage(text, max_chars=200) or exc.__class__.__name__)


def _close_client(client: Any) -> None:
    close = getattr(client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        # A cleanup failure must not replace the provider probe result.
        return


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _network_probe_metadata() -> dict[str, Any]:
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    configured = [key for key in proxy_keys if os.environ.get(key)]
    trust_env = os.environ.get("MYAI_MODEL_TRUST_ENV_PROXY", "false").strip().lower()
    return {
        "env_proxy_configured": bool(configured),
        "env_proxy_keys": configured,
        "trust_env_proxy": trust_env in {"1", "true", "yes", "on"},
    }
