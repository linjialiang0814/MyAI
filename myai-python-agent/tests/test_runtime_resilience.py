import unittest
import threading
import time

from app.model.base import BaseLLM
from app.model.factory import CircuitProtectedLLM, FallbackLLM
from app.runtime.error_model import AppError, ErrorCode, classify_exception, error_info_from_message
from app.runtime.resilience import (
    BackoffPolicy,
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitProtectedEmbeddingClient,
    CircuitState,
    Deadline,
    bounded_exponential_backoff,
)
from app.task.plan.executor import ToolExecutor
from app.task.tool.tool import Tool, ToolPolicy, ToolResult
from app.task.tool.tool_registry import ToolRegistry


class FakeClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class IdempotentFlakyTool(Tool):
    name = "idempotent_flaky"
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=1.0, retry_count=1)

    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs) -> ToolResult:
        self.calls += 1
        if self.calls == 1:
            return ToolResult(success=False, error="temporary network timeout")
        return ToolResult(success=True, data={"calls": self.calls})


class UnsafeFlakyTool(IdempotentFlakyTool):
    name = "unsafe_flaky"
    idempotent = False


class SlowIdempotentTool(Tool):
    name = "slow_idempotent"
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=0.01, retry_count=1)

    def __init__(self, release: threading.Event | None = None) -> None:
        self.calls = 0
        self.started = threading.Event()
        self.release = release

    def run(self, **kwargs) -> ToolResult:
        self.calls += 1
        self.started.set()
        if self.release is not None:
            self.release.wait(timeout=1.0)
        else:
            time.sleep(0.05)
        return ToolResult(success=True, data={"calls": self.calls})


class ExplodingTool(Tool):
    name = "exploding"
    policy = ToolPolicy(risk_level="safe", timeout_seconds=1.0, retry_count=0)

    def run(self, **kwargs) -> ToolResult:
        raise RuntimeError("provider token=TOPSECRET path=C:\\Users\\MYAI_TEST_USER\\secret.txt")


class ConnectionThenSuccessTool(Tool):
    name = "connection_then_success"
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=1.0, retry_count=1)

    def __init__(self) -> None:
        self.calls = 0

    def run(self, **kwargs) -> ToolResult:
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("private endpoint failed")
        return ToolResult(success=True, data={"calls": self.calls})


class ScriptedTool(Tool):
    name = "scripted_tool"
    idempotent = True
    policy = ToolPolicy(risk_level="network", timeout_seconds=1.0, retry_count=0)

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def run(self, **kwargs) -> ToolResult:
        del kwargs
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return ToolResult(success=True, data={"value": outcome})


class ScriptedLLM(BaseLLM):
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        del prompt
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return str(outcome)


class RuntimeResilienceTest(unittest.TestCase):
    def test_error_model_classifies_timeout_without_exposing_internal_exception(self):
        timeout = classify_exception(TimeoutError("provider secret"), operation="llm.chat")
        internal = classify_exception(RuntimeError("token=secret"), operation="llm.chat")

        self.assertEqual(timeout.code, ErrorCode.OPERATION_TIMEOUT)
        self.assertTrue(timeout.retryable)
        self.assertNotIn("secret", timeout.message)
        self.assertEqual(internal.code, ErrorCode.INTERNAL_ERROR)
        self.assertNotIn("secret", internal.message)
        self.assertEqual(error_info_from_message("HTTP 429 rate limit").code, ErrorCode.RATE_LIMITED)

    def test_bounded_backoff_and_deadline_are_deterministic_with_injected_time(self):
        policy = BackoffPolicy(
            max_attempts=4,
            base_delay_seconds=0.5,
            max_delay_seconds=1.5,
            jitter_ratio=0,
        )
        self.assertEqual([bounded_exponential_backoff(i, policy) for i in (1, 2, 3)], [0.5, 1.0, 1.5])

        clock = FakeClock()
        deadline = Deadline.after(2.0, clock=clock)
        clock.advance(2.0)
        with self.assertRaises(AppError) as raised:
            deadline.raise_if_expired(operation="tool.test")
        self.assertEqual(raised.exception.info.code, ErrorCode.OPERATION_TIMEOUT)

    def test_circuit_breaker_allows_only_one_half_open_probe(self):
        clock = FakeClock()
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=5.0, clock=clock)
        breaker.record_failure()
        breaker.record_failure()
        self.assertEqual(breaker.state, CircuitState.OPEN)
        with self.assertRaises(AppError):
            breaker.before_call(operation="dependency.test")

        clock.advance(5.0)
        breaker.before_call(operation="dependency.test")
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)
        with self.assertRaises(AppError):
            breaker.before_call(operation="dependency.test")
        breaker.record_success()
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_late_success_cannot_close_a_newly_opened_circuit(self):
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=5.0)
        late_permit = breaker.before_call()
        first_failure = breaker.before_call()
        breaker.record_failure(first_failure)
        second_failure = breaker.before_call()
        breaker.record_failure(second_failure)

        self.assertEqual(breaker.state, CircuitState.OPEN)
        self.assertFalse(breaker.record_success(late_permit))
        self.assertEqual(breaker.state, CircuitState.OPEN)

    def test_half_open_non_transient_error_releases_probe(self):
        class Client:
            def __init__(self):
                self.calls = 0

            def embed(self, _text):
                self.calls += 1
                if self.calls == 1:
                    raise ConnectionError("offline")
                raise ValueError("bad local input")

        clock = FakeClock()
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=5.0,
            clock=clock,
        )
        client = Client()
        protected = CircuitProtectedEmbeddingClient(client, breaker, "embedding")
        with self.assertRaises(ConnectionError):
            protected.embed("first")
        clock.advance(5.0)
        with self.assertRaises(ValueError):
            protected.embed("second")
        with self.assertRaises(ValueError):
            protected.embed("third")

        self.assertEqual(client.calls, 3)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

    def test_llm_half_open_non_transient_error_releases_probe(self):
        clock = FakeClock()
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=5.0,
            clock=clock,
        )
        client = ScriptedLLM(
            [ConnectionError("offline"), ValueError("bad local input"), "recovered"]
        )
        protected = CircuitProtectedLLM(client, breaker, role="chat")

        with self.assertRaises(ConnectionError):
            protected.generate("first")
        clock.advance(5.0)
        with self.assertRaises(ValueError):
            protected.generate("second")
        response = protected.generate("third")

        self.assertEqual(response, "recovered")
        self.assertEqual(client.calls, 3)
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_fallback_llm_half_open_non_transient_error_releases_probe(self):
        clock = FakeClock()
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=5.0,
            clock=clock,
        )
        primary = ScriptedLLM(
            [ConnectionError("offline"), ValueError("bad local input"), "recovered"]
        )
        fallback = ScriptedLLM(["fallback-1", "fallback-2"])
        protected = FallbackLLM(primary, fallback, role="chat", breaker=breaker)

        with self.assertLogs("app.model.factory", level="WARNING"):
            self.assertEqual(protected.generate("first"), "fallback-1")
        clock.advance(5.0)
        with self.assertLogs("app.model.factory", level="WARNING"):
            self.assertEqual(protected.generate("second"), "fallback-2")
        response = protected.generate("third")

        self.assertEqual(response, "recovered")
        self.assertEqual(primary.calls, 3)
        self.assertEqual(fallback.calls, 2)
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    def test_tool_executor_backs_off_for_idempotent_transient_failure(self):
        registry = ToolRegistry()
        tool = IdempotentFlakyTool()
        registry.register(tool)
        delays: list[float] = []
        executor = ToolExecutor(
            registry,
            sleep_fn=delays.append,
            random_source=lambda: 1.0,
            retry_backoff=BackoffPolicy(
                max_attempts=2,
                base_delay_seconds=0.25,
                max_delay_seconds=1.0,
                jitter_ratio=0,
            ),
        )

        result, _ = executor.execute(tool.name, {})

        self.assertTrue(result.success)
        self.assertEqual(tool.calls, 2)
        self.assertEqual(delays, [0.25])
        self.assertEqual(result.metadata["backoff_delays_seconds"], [0.25])
        self.assertEqual(result.metadata["error_infos"][0]["code"], ErrorCode.OPERATION_TIMEOUT.value)

    def test_tool_executor_suppresses_retry_for_non_idempotent_operation(self):
        registry = ToolRegistry()
        tool = UnsafeFlakyTool()
        registry.register(tool)
        delays: list[float] = []
        executor = ToolExecutor(registry, sleep_fn=delays.append)

        result, _ = executor.execute(tool.name, {})

        self.assertFalse(result.success)
        self.assertEqual(tool.calls, 1)
        self.assertEqual(delays, [])
        self.assertEqual(result.metadata["max_attempts"], 1)
        self.assertIn("not declared safe or idempotent", result.metadata["retry_suppressed_reason"])
        self.assertEqual(result.metadata["error_info"]["code"], ErrorCode.OPERATION_TIMEOUT.value)

    def test_caller_side_timeout_is_outcome_unknown_and_never_retried(self):
        registry = ToolRegistry()
        tool = SlowIdempotentTool()
        registry.register(tool)
        executor = ToolExecutor(registry, sleep_fn=lambda _delay: None)
        self.addCleanup(executor.close)

        result, _ = executor.execute(tool.name, {})
        time.sleep(0.08)

        self.assertFalse(result.success)
        self.assertEqual(tool.calls, 1)
        self.assertTrue(result.metadata["outcome_unknown"])
        self.assertFalse(result.metadata["retryable"])
        self.assertIn("cannot prove", result.metadata["retry_suppressed_reason"])

    def test_hung_tool_does_not_starve_a_different_tool_pool(self):
        release = threading.Event()
        registry = ToolRegistry()
        slow = SlowIdempotentTool(release)
        healthy = IdempotentFlakyTool()
        healthy.name = "healthy_isolated"
        healthy.calls = 1
        registry.register(slow)
        registry.register(healthy)
        executor = ToolExecutor(registry)
        self.addCleanup(executor.close)

        slow_result, _ = executor.execute(slow.name, {})
        healthy_result, _ = executor.execute(healthy.name, {})
        release.set()

        self.assertFalse(slow_result.success)
        self.assertTrue(healthy_result.success)

    def test_tool_executor_refuses_clean_shutdown_while_timed_out_call_is_running(self):
        release = threading.Event()
        registry = ToolRegistry()
        slow = SlowIdempotentTool(release)
        registry.register(slow)
        executor = ToolExecutor(registry)
        self.addCleanup(release.set)

        result, _ = executor.execute(slow.name, {})

        self.assertFalse(result.success)
        self.assertTrue(result.metadata["execution_may_continue"])
        self.assertFalse(executor.close(timeout_seconds=0.01))
        release.set()
        self.assertTrue(executor.close(timeout_seconds=1.0))

    def test_untrusted_tool_exception_is_not_exposed(self):
        registry = ToolRegistry()
        registry.register(ExplodingTool())
        executor = ToolExecutor(registry)
        self.addCleanup(executor.close)

        result, _ = executor.execute("exploding", {})

        self.assertFalse(result.success)
        self.assertEqual(result.error, "The operation failed unexpectedly.")
        self.assertNotIn("TOPSECRET", str(result.model_dump()))

    def test_typed_connection_error_is_retried_without_reclassification(self):
        registry = ToolRegistry()
        tool = ConnectionThenSuccessTool()
        registry.register(tool)
        executor = ToolExecutor(
            registry,
            sleep_fn=lambda _delay: None,
            retry_backoff=BackoffPolicy(max_attempts=2, jitter_ratio=0),
        )
        self.addCleanup(executor.close)

        result, _ = executor.execute(tool.name, {})

        self.assertTrue(result.success)
        self.assertEqual(tool.calls, 2)
        self.assertEqual(
            result.metadata["error_infos"][0]["code"],
            ErrorCode.DEPENDENCY_UNAVAILABLE.value,
        )

    def test_tool_half_open_business_error_releases_probe(self):
        clock = FakeClock()
        registry = ToolRegistry()
        tool = ScriptedTool(
            [ConnectionError("offline"), ValueError("bad local input"), "recovered"]
        )
        registry.register(tool)
        circuits = CircuitBreakerRegistry(
            failure_threshold=1,
            recovery_timeout_seconds=1.0,
            clock=clock,
        )
        executor = ToolExecutor(registry, circuit_registry=circuits)
        self.addCleanup(executor.close)

        first, _ = executor.execute(tool.name, {})
        clock.advance(1.0)
        second, _ = executor.execute(tool.name, {})
        third, _ = executor.execute(tool.name, {})

        self.assertEqual(first.metadata["error_info"]["code"], ErrorCode.DEPENDENCY_UNAVAILABLE.value)
        self.assertEqual(second.metadata["error_info"]["code"], ErrorCode.INVALID_ARGUMENT.value)
        self.assertTrue(third.success)
        self.assertEqual(tool.calls, 3)
        self.assertEqual(circuits.get(f"tool:{tool.name}").state, CircuitState.CLOSED)

    def test_embedding_client_uses_shared_circuit_and_closes_owner(self):
        class BrokenEmbedding:
            def __init__(self):
                self.calls = 0
                self.closed = False

            def embed(self, _text):
                self.calls += 1
                raise ConnectionError("offline")

            def close(self):
                self.closed = True

        client = BrokenEmbedding()
        protected = CircuitProtectedEmbeddingClient(
            client,
            CircuitBreaker(failure_threshold=1, recovery_timeout_seconds=30),
            dependency="local-embedding",
        )

        with self.assertRaises(ConnectionError):
            protected.embed("hello")
        with self.assertRaises(AppError) as raised:
            protected.embed("hello again")
        protected.close()
        protected.close()

        self.assertEqual(client.calls, 1)
        self.assertEqual(raised.exception.info.code, ErrorCode.CIRCUIT_OPEN)
        self.assertTrue(client.closed)


if __name__ == "__main__":
    unittest.main()
