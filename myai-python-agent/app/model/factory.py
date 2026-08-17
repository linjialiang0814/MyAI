from __future__ import annotations

import logging

from app.model.base import BaseLLM
from app.model.config import LLMSettings, load_llm_settings
from app.model.openai_compatible_llm import OpenAICompatibleLLM
from app.model.stub_llm import StubLLM
from app.model.volc_llm import VolcengineLLM
from app.runtime.error_model import classify_exception
from app.runtime.resilience import CircuitBreaker, CircuitBreakerRegistry, is_transient_dependency_error

logger = logging.getLogger(__name__)


class CircuitProtectedLLM(BaseLLM):
    def __init__(self, client: BaseLLM, breaker: CircuitBreaker, role: str):
        self.client = client
        self.breaker = breaker
        self.role = role
        self._closed = False

    def generate(self, prompt: str) -> str:
        permit = self.breaker.before_call(operation=f"llm.{self.role}.generate", dependency=self.role)
        try:
            response = self.client.generate(prompt)
        except Exception as exc:
            if is_transient_dependency_error(exc):
                self.breaker.record_failure(permit)
            else:
                self.breaker.release_probe(permit)
            raise
        self.breaker.record_success(permit)
        return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self.client, "close", None)
        if callable(close):
            close()


class FallbackLLM(BaseLLM):
    def __init__(
        self,
        primary: BaseLLM,
        fallback: BaseLLM,
        role: str,
        breaker: CircuitBreaker | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.role = role
        self.breaker = breaker or CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=60.0)
        self._closed = False

    def generate(self, prompt: str) -> str:
        try:
            permit = self.breaker.before_call(operation=f"llm.{self.role}.generate", dependency=self.role)
        except Exception:
            return self.fallback.generate(prompt)
        try:
            response = self.primary.generate(prompt)
        except Exception as exc:
            if is_transient_dependency_error(exc):
                self.breaker.record_failure(permit)
            else:
                self.breaker.release_probe(permit)
            error_info = classify_exception(exc, operation=f"llm.{self.role}.generate", dependency=self.role)
            logger.warning(
                "Falling back to StubLLM role=%s error_type=%s error_code=%s",
                self.role,
                type(exc).__name__,
                error_info.code.value,
            )
            return self.fallback.generate(prompt)
        self.breaker.record_success(permit)
        return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        closed_ids: set[int] = set()
        resources = []
        for client in (self.primary, self.fallback):
            if id(client) in closed_ids:
                continue
            close = getattr(client, "close", None)
            if callable(close):
                resources.append(close)
            closed_ids.add(id(client))
        first_error = None
        for close in resources:
            try:
                close()
            except Exception as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error


def create_llm(
    role: str = "chat",
    settings: LLMSettings | None = None,
    *,
    circuit_registry: CircuitBreakerRegistry | None = None,
) -> BaseLLM:
    settings = settings or load_llm_settings()
    provider = _resolve_provider(role, settings)

    if provider == "stub":
        return StubLLM()

    if provider == "volcengine":
        try:
            llm = VolcengineLLM(
                model_id=_resolve_model_id(role, settings),
                temperature=settings.temperature,
                base_url=settings.ark_base_url,
                api_key=settings.ark_api_key,
            )
            return _apply_runtime_resilience(
                llm,
                role=role,
                provider=provider,
                fallback_to_stub=settings.fallback_to_stub,
                circuit_registry=circuit_registry,
            )
        except Exception as exc:
            if settings.fallback_to_stub:
                error_info = classify_exception(exc, operation=f"llm.{role}.initialize", dependency=provider)
                logger.warning(
                    "Falling back to StubLLM role=%s provider=%s error_type=%s error_code=%s",
                    role,
                    provider,
                    type(exc).__name__,
                    error_info.code.value,
                )
                return StubLLM()
            raise

    if provider == "openai_compatible":
        try:
            llm = OpenAICompatibleLLM(
                model_id=_resolve_model_id(role, settings),
                temperature=settings.temperature,
                base_url=settings.openai_compatible_base_url,
                api_key=settings.openai_compatible_api_key,
                timeout_seconds=settings.llm_request_timeout_seconds,
                max_retries=settings.llm_max_retries,
                seed=settings.llm_seed,
                max_tokens=settings.llm_max_tokens,
                trust_env_proxy=settings.model_trust_env_proxy,
            )
            return _apply_runtime_resilience(
                llm,
                role=role,
                provider=provider,
                fallback_to_stub=settings.fallback_to_stub,
                circuit_registry=circuit_registry,
            )
        except Exception as exc:
            if settings.fallback_to_stub:
                error_info = classify_exception(exc, operation=f"llm.{role}.initialize", dependency=provider)
                logger.warning(
                    "Falling back to StubLLM role=%s provider=%s error_type=%s error_code=%s",
                    role,
                    provider,
                    type(exc).__name__,
                    error_info.code.value,
                )
                return StubLLM()
            raise

    if settings.fallback_to_stub:
        logger.warning("Unknown provider '%s' for role=%s, falling back to StubLLM.", provider, role)
        return StubLLM()
    raise ValueError(f"Unsupported LLM provider: {provider}")


def _apply_runtime_resilience(
    llm: BaseLLM,
    *,
    role: str,
    provider: str,
    fallback_to_stub: bool,
    circuit_registry: CircuitBreakerRegistry | None,
) -> BaseLLM:
    breaker = (
        circuit_registry.get(f"llm:{role}:{provider}")
        if circuit_registry is not None
        else None
    )
    if fallback_to_stub:
        return FallbackLLM(primary=llm, fallback=StubLLM(), role=role, breaker=breaker)
    if breaker is not None:
        return CircuitProtectedLLM(client=llm, breaker=breaker, role=role)
    return llm


def _resolve_provider(role: str, settings: LLMSettings) -> str:
    role = role.lower()
    if role == "chat":
        return settings.chat_provider
    if role == "task":
        return settings.task_provider
    if role == "memory":
        return settings.memory_provider
    return settings.default_provider


def _resolve_model_id(role: str, settings: LLMSettings) -> str:
    role = role.lower()
    if role == "chat":
        return settings.chat_model_id
    if role == "task":
        return settings.task_model_id
    if role == "memory":
        return settings.memory_model_id
    return settings.default_model_id
