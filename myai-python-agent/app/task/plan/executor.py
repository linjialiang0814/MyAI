from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError, wait
from typing import Dict, Any, Tuple
import logging
import random
import threading
import time
from pydantic import ValidationError

from app.runtime.error_model import AppError, ErrorCode, ErrorInfo, classify_exception, error_info_from_message
from app.runtime.resilience import BackoffPolicy, CircuitBreakerRegistry, bounded_exponential_backoff
from app.task.tool.tool_registry import ToolRegistry
from app.task.tool.tool import ToolResult

logger = logging.getLogger(__name__)

class ToolExecutor:

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        sleep_fn=time.sleep,
        random_source=random.random,
        circuit_registry: CircuitBreakerRegistry | None = None,
        retry_backoff: BackoffPolicy | None = None,
        timeout_workers: int = 1,
    ):
        self.registry = registry
        self._sleep = sleep_fn
        self._random_source = random_source
        self._circuit_registry = circuit_registry or CircuitBreakerRegistry()
        self._retry_backoff = retry_backoff or BackoffPolicy(
            max_attempts=2,
            base_delay_seconds=0.25,
            max_delay_seconds=2.0,
            jitter_ratio=0.2,
        )
        self._timeout_workers = max(1, int(timeout_workers))
        self._timeout_pools: dict[str, ThreadPoolExecutor] = {}
        self._active_futures: set[Future] = set()
        self._timeout_pools_lock = threading.Lock()
        self._closed = False
        self._shutdown_complete = False

    def close(self, timeout_seconds: float = 5.0) -> bool:
        with self._timeout_pools_lock:
            self._closed = True
            if self._shutdown_complete:
                return True
            futures = list(self._active_futures)
        for future in futures:
            future.cancel()
        not_done = set()
        if futures:
            _, not_done = wait(futures, timeout=max(0.0, timeout_seconds))
        if not_done:
            return False
        with self._timeout_pools_lock:
            pools = list(self._timeout_pools.values())
            self._timeout_pools.clear()
            self._active_futures.clear()
            self._shutdown_complete = True
        for pool in pools:
            pool.shutdown(wait=False, cancel_futures=True)
        return True

    def execute(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        runtime_context: Dict[str, Any] | None = None,
    ) -> Tuple[ToolResult, float]:
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool'{tool_name}' not found"), 0.0

        start = time.perf_counter()
        try:
            prepared_args = tool.prepare_args(tool_args, runtime_context)
            validated_args = tool.validate_args(prepared_args).model_dump()
            policy = tool.policy_for_args(validated_args, runtime_context)
            policy_payload = policy.to_dict()
            if not policy.allowed_in_local:
                result = ToolResult(
                    success=False,
                    error=f"Tool '{tool_name}' is disabled by tool policy.",
                    metadata={"tool_policy": policy_payload, "policy_decision": "blocked"},
                )
                latency_ms = (time.perf_counter() - start) * 1000.0
                return result, latency_ms
            if policy.requires_confirmation and not (runtime_context or {}).get("permission_confirmed"):
                result = ToolResult(
                    success=False,
                    error=f"Tool '{tool_name}' requires confirmation before execution.",
                    metadata={
                        "tool_policy": policy_payload,
                        "policy_decision": "permission_required",
                        "permission_required": True,
                    },
                )
                latency_ms = (time.perf_counter() - start) * 1000.0
                return result, latency_ms
            policy_payload["idempotent"] = self._is_idempotent_operation(tool, policy_payload)
            logger.info("Executing tool=%s args=%s", tool_name, validated_args)
            result = self._execute_with_recovery(
                tool,
                validated_args,
                policy_payload,
                deadline=(runtime_context or {}).get("deadline"),
            )
            result.metadata = {
                **(result.metadata or {}),
                "tool_policy": policy_payload,
                "policy_decision": "allowed",
            }
        except ValidationError as exc:
            error = classify_exception(ValueError(f"Argument validation failed: {exc}"), operation=f"tool.{tool_name}")
            result = ToolResult(success=False, error=error.message, metadata={"error_info": error.to_dict()})
        except Exception as exc:
            error = classify_exception(exc, operation=f"tool.{tool_name}")
            logger.error(
                "Tool execution failed tool=%s error_type=%s error_code=%s",
                tool_name,
                type(exc).__name__,
                error.code.value,
            )
            result = ToolResult(success=False, error=error.message, metadata={"error_info": error.to_dict()})
        latency_ms = (time.perf_counter() - start) * 1000.0
        return result, latency_ms

    def _execute_with_recovery(
        self,
        tool,
        validated_args: Dict[str, Any],
        policy_payload: Dict[str, Any],
        *,
        deadline=None,
    ) -> ToolResult:
        requested_retry_count = max(0, int(policy_payload.get("retry_count") or 0))
        timeout_seconds = float(policy_payload.get("timeout_seconds") or 10.0)
        if deadline is not None:
            timeout_seconds = min(timeout_seconds, deadline.remaining_seconds())
            if timeout_seconds <= 0:
                return ToolResult(
                    success=False,
                    error="The operation deadline was exceeded.",
                    metadata={
                        "retryable": False,
                        "recovery_status": "deadline_exhausted",
                    },
                )
        risk_level = str(policy_payload.get("risk_level") or "safe")
        idempotent = bool(policy_payload.get("idempotent"))
        retry_count = min(requested_retry_count, self._retry_backoff.max_attempts - 1) if idempotent else 0
        max_attempts = 1 + retry_count
        errors: list[str] = []
        error_infos: list[dict[str, Any]] = []
        backoff_delays: list[float] = []
        breaker = self._circuit_registry.get(f"tool:{tool.name}") if idempotent else None

        for attempt in range(1, max_attempts + 1):
            permit = None
            if breaker is not None:
                try:
                    permit = breaker.before_call(operation=f"tool.{tool.name}", dependency=tool.name)
                except AppError as exc:
                    return ToolResult(
                        success=False,
                        error=exc.info.message,
                        metadata={
                            "attempt": attempt,
                            "max_attempts": max_attempts,
                            "requested_retry_count": requested_retry_count,
                            "retry_count": retry_count,
                            "timeout_seconds": timeout_seconds,
                            "idempotent": idempotent,
                            "retryable": exc.info.retryable,
                            "recovery_attempted": attempt > 1,
                            "recovery_status": "circuit_open",
                            "errors": errors,
                            "error_infos": [*error_infos, exc.info.to_dict()],
                            "backoff_delays_seconds": backoff_delays,
                            "error_info": exc.info.to_dict(),
                        },
                    )
            result = self._run_with_timeout(tool, validated_args, timeout_seconds)
            result.metadata = {
                **(result.metadata or {}),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "requested_retry_count": requested_retry_count,
                "retry_count": retry_count,
                "timeout_seconds": timeout_seconds,
                "idempotent": idempotent,
                "retryable": False,
                "recovery_attempted": attempt > 1,
            }
            if requested_retry_count and not idempotent:
                result.metadata["retry_suppressed_reason"] = "operation is not declared safe or idempotent"
            if result.success:
                if breaker is not None:
                    breaker.record_success(permit)
                result.metadata["recovery_status"] = "succeeded_after_retry" if attempt > 1 else "not_needed"
                if errors:
                    result.metadata["errors"] = errors
                    result.metadata["error_infos"] = error_infos
                    result.metadata["backoff_delays_seconds"] = backoff_delays
                return result

            raw_error = result.error or "tool execution failed"
            typed_error = (result.metadata or {}).get("error_info")
            if isinstance(typed_error, dict) and typed_error.get("code"):
                try:
                    error_info = ErrorInfo(
                        code=ErrorCode(str(typed_error["code"])),
                        message=str(typed_error.get("message") or "Tool execution failed."),
                        retryable=bool(typed_error.get("retryable")),
                        operation=str(typed_error.get("operation") or f"tool.{tool.name}"),
                        dependency=str(typed_error.get("dependency") or tool.name),
                        details=typed_error.get("details") or {},
                    )
                except (TypeError, ValueError):
                    error_info = error_info_from_message(
                        raw_error,
                        operation=f"tool.{tool.name}",
                        dependency=tool.name,
                    )
            else:
                error_info = error_info_from_message(
                    raw_error,
                    operation=f"tool.{tool.name}",
                    dependency=tool.name,
                )
            error = error_info.message
            result.error = error
            errors.append(error)
            error_infos.append(error_info.to_dict())
            result.metadata["error_info"] = error_info.to_dict()
            timeout_boundary = bool(result.metadata.get("timeout_boundary"))
            outcome_unknown = bool(result.metadata.get("outcome_unknown"))
            retryable = (
                idempotent
                and not timeout_boundary
                and risk_level not in {"sensitive", "destructive"}
                and error_info.retryable
            )
            result.metadata["retryable"] = retryable
            if timeout_boundary:
                result.metadata["retry_suppressed_reason"] = (
                    "caller-side timeout cannot prove the prior tool attempt stopped"
                )
            dependency_failure = error_info.code in {
                ErrorCode.DEPENDENCY_UNAVAILABLE,
                ErrorCode.RATE_LIMITED,
                ErrorCode.OPERATION_TIMEOUT,
            }
            if breaker is not None:
                if dependency_failure or timeout_boundary:
                    breaker.record_failure(permit)
                elif permit is not None and permit.half_open_probe:
                    # A validation/business failure proves neither dependency
                    # recovery nor dependency failure. Release the single probe
                    # so a later valid request can test the dependency again.
                    breaker.release_probe(permit)
            if attempt < max_attempts and retryable:
                delay = bounded_exponential_backoff(
                    attempt,
                    self._retry_backoff,
                    random_value=self._random_source(),
                )
                backoff_delays.append(round(delay, 6))
                if deadline is not None and delay >= deadline.remaining_seconds():
                    result.metadata["retryable"] = False
                    result.metadata["recovery_status"] = "deadline_exhausted"
                    result.metadata["retry_suppressed_reason"] = "request deadline budget exhausted"
                    result.metadata["errors"] = errors
                    result.metadata["error_infos"] = error_infos
                    result.metadata["backoff_delays_seconds"] = backoff_delays[:-1]
                    return result
                logger.info(
                    "Retrying tool=%s attempt=%s/%s after=%.3fs error=%s",
                    tool.name,
                    attempt + 1,
                    max_attempts,
                    delay,
                    error,
                )
                self._sleep(delay)
                continue

            result.metadata["errors"] = errors
            result.metadata["error_infos"] = error_infos
            result.metadata["backoff_delays_seconds"] = backoff_delays
            result.metadata["recovery_status"] = "exhausted" if retryable and attempt >= max_attempts else "not_retryable"
            result.metadata["recovery_recommendation"] = self._recovery_recommendation(error, retryable)
            return result

        return ToolResult(
            success=False,
            error=errors[-1] if errors else "tool execution failed",
            metadata={
                "attempt": max_attempts,
                "max_attempts": max_attempts,
                "requested_retry_count": requested_retry_count,
                "retry_count": retry_count,
                "timeout_seconds": timeout_seconds,
                "idempotent": idempotent,
                "errors": errors,
                "error_infos": error_infos,
                "backoff_delays_seconds": backoff_delays,
                "recovery_status": "exhausted",
                "recovery_recommendation": "Review the tool error and retry later.",
            },
        )

    def _run_with_timeout(self, tool, validated_args: Dict[str, Any], timeout_seconds: float) -> ToolResult:
        if self._closed:
            error = ErrorInfo(
                code=ErrorCode.INTERNAL_ERROR,
                message="Tool executor is closed.",
                operation=f"tool.{tool.name}",
            )
            return ToolResult(success=False, error=error.message, metadata={"error_info": error.to_dict()})
        try:
            future = self._submit_tool(tool, validated_args)
        except RuntimeError:
            error = ErrorInfo(
                code=ErrorCode.INTERNAL_ERROR,
                message="Tool executor is closed.",
                operation=f"tool.{tool.name}",
            )
            return ToolResult(success=False, error=error.message, metadata={"error_info": error.to_dict()})
        try:
            succeeded, value = future.result(timeout=max(0.001, timeout_seconds))
        except TimeoutError:
            cancelled_before_start = future.cancel()
            error = ErrorInfo(
                code=ErrorCode.OPERATION_TIMEOUT,
                message="The operation timed out.",
                retryable=False,
                operation=f"tool.{tool.name}",
                dependency=tool.name,
                details={
                    "outcome_unknown": not cancelled_before_start,
                    "execution_may_continue": not cancelled_before_start,
                },
            )
            return ToolResult(
                success=False,
                error=error.message,
                metadata={
                    "error_info": error.to_dict(),
                    "timeout_boundary": True,
                    "outcome_unknown": not cancelled_before_start,
                    "execution_may_continue": not cancelled_before_start,
                },
            )
        if not succeeded:
            error = classify_exception(
                value,
                operation=f"tool.{tool.name}",
                dependency=tool.name,
            )
            return ToolResult(
                success=False,
                error=error.message,
                metadata={
                    "error_info": error.to_dict(),
                    "execution_stopped": True,
                    "outcome_unknown": False,
                },
            )
        result = value
        if not isinstance(result, ToolResult):
            return ToolResult(success=False, error="Tool did not return ToolResult")
        return result

    def _submit_tool(self, tool, validated_args: Dict[str, Any]) -> Future:
        with self._timeout_pools_lock:
            if self._closed:
                raise RuntimeError("Tool executor is closed")
            pool = self._timeout_pools.get(tool.name)
            if pool is None:
                pool = ThreadPoolExecutor(
                    max_workers=self._timeout_workers,
                    thread_name_prefix=f"myai-tool-{tool.name[:24]}",
                )
                self._timeout_pools[tool.name] = pool
            future = pool.submit(self._invoke_tool, tool, validated_args)
            self._active_futures.add(future)
        future.add_done_callback(self._discard_future)
        return future

    def _discard_future(self, future: Future) -> None:
        with self._timeout_pools_lock:
            self._active_futures.discard(future)

    @staticmethod
    def _invoke_tool(tool, validated_args: Dict[str, Any]) -> tuple[bool, Any]:
        try:
            return True, tool.run(**validated_args)
        except Exception as exc:  # marshalled back to the caller thread
            return False, exc

    def _is_retryable_error(self, *, error: str, risk_level: str) -> bool:
        if risk_level in {"sensitive", "destructive"}:
            return False
        return error_info_from_message(error).retryable

    @staticmethod
    def _is_idempotent_operation(tool, policy_payload: Dict[str, Any]) -> bool:
        explicit = getattr(tool, "idempotent", None)
        if explicit is not None:
            return bool(explicit)
        risk_level = str(policy_payload.get("risk_level") or "safe").lower()
        if bool(policy_payload.get("requires_confirmation")):
            return False
        return risk_level == "safe" or risk_level.endswith("/read") or risk_level.endswith("-readonly")

    def _recovery_recommendation(self, error: str, retryable: bool) -> str:
        normalized = error.lower()
        if "timeout" in normalized or "timed out" in normalized:
            return "The tool timed out. Try a narrower request or run it again when the dependency is responsive."
        if retryable:
            return "The failure looks transient. Wait for the dependency or network to stabilize before retrying."
        return "The failure is not classified as retryable. Review the input or tool policy before retrying."
