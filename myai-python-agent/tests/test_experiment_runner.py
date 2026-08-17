import hashlib
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

import numpy as np

from app.experiments.runner import (
    REQUIRED_ARTIFACTS,
    ProviderCircuitOpen,
    _balanced_variant_orders,
    _completion_gate,
    _create_clients,
    _dependency_snapshot,
    _failed_case,
    _ollama_loaded_backend_snapshot,
    _ollama_server_process_snapshot,
    _paired_rubric_deltas,
    _warm_up,
    _write_checksums,
    run_experiment,
    validate_experiment,
    verify_checksums,
)
from app.experiments.schema import load_experiment_spec
from tests import TEST_DATA_ROOT


BASE_DIR = Path(__file__).resolve().parents[1]
SPEC = BASE_DIR / "experiments" / "specs" / "thesis_core_v1.json"


class FakeLLM:
    def generate(self, prompt: str) -> str:
        return "UNKNOWN"


class FakeEmbedding:
    def embed(self, text: str):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = np.array([byte + 1 for byte in digest[:16]], dtype=np.float32)
        return vector / np.linalg.norm(vector)


class CountingEmbedding(FakeEmbedding):
    def __init__(self):
        self.calls = 0

    def embed(self, text: str):
        self.calls += 1
        return super().embed(text)


class CountingLLM(FakeLLM):
    def __init__(self):
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        return super().generate(prompt)


class CloseableFakeLLM(FakeLLM):
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class CloseableFakeEmbedding(FakeEmbedding):
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FailAfterWarmupLLM:
    def __init__(self, exception_factory):
        self.calls = 0
        self.exception_factory = exception_factory

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return "WARMUP_OK"
        raise self.exception_factory()


class FakeServerError(RuntimeError):
    status_code = 500


class ExperimentRunnerTest(unittest.TestCase):
    def test_frozen_spec_and_dataset_validate(self):
        payload = validate_experiment(SPEC)

        self.assertTrue(payload["valid"])
        self.assertEqual(payload["memory_cases"], 18)
        self.assertEqual(payload["rag_documents"], 10)
        self.assertEqual(payload["rag_cases"], 30)

    def test_dependency_snapshot_checks_every_pinned_requirement(self):
        pinned_count = sum(
            1
            for line in (BASE_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "==" in line
        )

        snapshot = _dependency_snapshot()

        self.assertEqual(len(snapshot["checks"]), pinned_count)
        self.assertEqual(len(snapshot["observed"]), pinned_count)
        self.assertIn("annotated-doc", snapshot["observed"])
        self.assertTrue(snapshot["passed"])

    def test_injected_clients_create_non_publishable_complete_artifacts(self):
        output = TEST_DATA_ROOT / f"experiment-run-{uuid4()}"
        result = run_experiment(
            SPEC,
            suite="all",
            output_dir=output,
            repeats=1,
            max_cases=1,
            exploratory=True,
            llm=FakeLLM(),
            embedding_client=FakeEmbedding(),
        )

        self.assertEqual(result["status"]["status"], "completed")
        self.assertFalse(result["manifest"]["publishable"])
        self.assertTrue((output / "manifest.json").is_file())
        self.assertTrue((output / "cases.jsonl").is_file())
        self.assertTrue((output / "comparison.csv").is_file())
        self.assertTrue((output / "report.md").is_file())
        self.assertTrue((output / "CHECKSUMS.sha256").is_file())
        status = json.loads((output / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["status"], "completed")
        self.assertEqual(result["metrics"]["summary"]["attempts"], 6)
        self.assertTrue(verify_checksums(output)["valid"])
        report = (output / "report.md").read_text(encoding="utf-8")
        self.assertIn("DIAGNOSTIC / NOT FOR THESIS CITATION", report)
        self.assertIn("Requested max cases per suite: `1`", report)
        self.assertIn("`memory`: 1 unique cases x 1 technical repeats x 3 arms = 3 attempts", report)
        self.assertIn("N/A", report)
        self.assertIn("governed_vs_basic", report)
        self.assertIn("hybrid_rerank_vs_hybrid", report)
        self.assertIn("Forbidden-evidence exposure", report)
        self.assertIn("must not be read as privacy disclosure alone", report)
        for name in REQUIRED_ARTIFACTS | {"CHECKSUMS.sha256"}:
            self.assertNotIn(b"\r\n", (output / name).read_bytes())

    def test_runner_closes_clients_that_it_creates(self):
        output = TEST_DATA_ROOT / f"experiment-owned-clients-{uuid4()}"
        llm = CloseableFakeLLM()
        embedding = CloseableFakeEmbedding()
        with patch(
            "app.experiments.runner._create_clients",
            return_value=(llm, embedding),
        ), patch(
            "app.experiments.runner._preflight",
            return_value={"git": {"dirty": True, "commit": "test", "branch": "test"}, "provider": {}},
        ), patch(
            "app.experiments.runner._ollama_loaded_backend_snapshot",
            return_value={"passed": True, "models": {}, "checks": []},
        ):
            run_experiment(
                SPEC,
                suite="memory",
                output_dir=output,
                repeats=1,
                max_cases=1,
                exploratory=True,
            )

        self.assertTrue(llm.closed)
        self.assertTrue(embedding.closed)

    def test_live_validation_closes_clients_that_it_creates(self):
        llm = CloseableFakeLLM()
        embedding = CloseableFakeEmbedding()
        with patch(
            "app.experiments.runner._create_clients",
            return_value=(llm, embedding),
        ), patch(
            "app.experiments.runner._preflight",
            return_value={"git": {"dirty": True, "commit": "test", "branch": "test"}},
        ):
            validate_experiment(SPEC, live=True, exploratory=True)

        self.assertTrue(llm.closed)
        self.assertTrue(embedding.closed)

    def test_balanced_variant_order_rotates_every_arm_through_each_position(self):
        orders = _balanced_variant_orders(("a", "b", "c"), 3)

        self.assertEqual(orders, [["a", "b", "c"], ["b", "c", "a"], ["c", "a", "b"]])
        for position in range(3):
            self.assertEqual({order[position] for order in orders}, {"a", "b", "c"})

    def test_embedding_validation_probe_is_reused_as_the_single_warmup(self):
        llm = CountingLLM()
        embedding = CountingEmbedding()

        result = _warm_up(
            llm,
            embedding,
            1,
            embedding_probe={"latency_ms": 12.5, "used_as_warmup": True},
        )

        self.assertEqual(embedding.calls, 0)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(result["embedding"]["requests"], 1)
        self.assertEqual(result["embedding"]["source"], "preflight_validation_probe")
        self.assertEqual(result["embedding"]["latency_ms"], 12.5)
        self.assertFalse(result["included_in_case_latency"])

    def test_generation_failure_preserves_successful_retrieval_evidence(self):
        evidence_score = {
            "applicable": True,
            "recall_at_k": 1.0,
            "precision_at_k": 0.5,
            "mrr": 1.0,
            "hit_at_k": True,
            "leakage": False,
            "leakage_applicable": False,
            "forbidden_hits": [],
        }
        evidence = [{"label": "C1", "file_alias": "doc-a"}]

        payload = _failed_case(
            suite="rag",
            variant="hybrid",
            repeat=1,
            order_position=1,
            case={"id": "case-a", "gold_file_aliases": ["doc-a"], "expected": {}},
            started=time.perf_counter(),
            write_latency_ms=None,
            retrieval_latency_ms=4.0,
            generation_latency_ms=None,
            candidate_count=2,
            selected_context_count=1,
            failure_stage="generation",
            exc=TimeoutError("generation timed out"),
            evidence_score=evidence_score,
            selected_evidence=evidence,
        )

        self.assertFalse(payload["execution_ok"])
        self.assertEqual(payload["failure_stage"], "generation")
        self.assertEqual(payload["evidence_score"], evidence_score)
        self.assertEqual(payload["selected_evidence"], evidence)
        self.assertTrue(payload["support_hit_at_k"])
        self.assertEqual(payload["support_recall_at_k"], 1.0)

    def test_paired_deltas_include_baseline_and_adjacent_core_comparisons(self):
        cases = []
        for variant, correctness in {
            "none": (False, False),
            "basic": (True, False),
            "governed": (True, True),
        }.items():
            for index, correct in enumerate(correctness, start=1):
                cases.append(
                    {
                        "variant": variant,
                        "case_id": f"case-{index}",
                        "answer_score": {"correct": correct},
                    }
                )

        result = _paired_rubric_deltas(cases, ("none", "basic", "governed"))

        self.assertEqual(
            set(result["comparisons"]),
            {"basic_vs_none", "governed_vs_none", "governed_vs_basic"},
        )
        self.assertEqual(result["comparisons"]["governed_vs_basic"]["mean_delta"], 0.5)

    def test_timeout_and_5xx_open_provider_circuit_after_three_cases(self):
        for label, factory in (
            ("timeout", lambda: TimeoutError("provider timed out")),
            ("5xx", lambda: FakeServerError("provider returned 500")),
        ):
            with self.subTest(label=label):
                output = TEST_DATA_ROOT / f"experiment-circuit-{label}-{uuid4()}"
                with self.assertRaises(ProviderCircuitOpen):
                    run_experiment(
                        SPEC,
                        suite="memory",
                        output_dir=output,
                        repeats=1,
                        max_cases=3,
                        exploratory=True,
                        llm=FailAfterWarmupLLM(factory),
                        embedding_client=FakeEmbedding(),
                    )
                status = json.loads((output / "status.json").read_text(encoding="utf-8"))
                self.assertEqual(status["status"], "failed")
                self.assertEqual(status["error_type"], "provider_circuit_open")
                self.assertNotIn("completed", status.values())

    def test_completion_gate_rejects_internal_runtime_errors_but_records_model_failure(self):
        internal = _completion_gate(
            [{"execution_ok": False, "failure_category": "runtime_error"}],
            planned_attempts=1,
            actual_attempts=1,
            backend_verified=True,
        )
        observed = _completion_gate(
            [{"execution_ok": False, "failure_category": "timeout"}],
            planned_attempts=1,
            actual_attempts=1,
            backend_verified=True,
        )

        self.assertFalse(internal["passed"])
        self.assertEqual(internal["infrastructure_failures"], 1)
        self.assertTrue(observed["passed"])
        self.assertEqual(observed["observed_model_failures"], 1)

    def test_strict_preflight_observes_tree_before_output_directory_is_created(self):
        output = TEST_DATA_ROOT / f"experiment-preflight-order-{uuid4()}"

        def assert_output_absent(*args, **kwargs):
            self.assertFalse(output.exists())
            return {
                "git": {"dirty": True, "commit": "test", "branch": "test"},
                "provider": {"skipped": True},
                "hardware": {},
                "hardware_checks": [],
                "dependencies": {"checks": [], "passed": True},
            }

        with patch("app.experiments.runner._preflight", side_effect=assert_output_absent):
            run_experiment(
                SPEC,
                suite="memory",
                output_dir=output,
                repeats=1,
                max_cases=1,
                exploratory=True,
                llm=FakeLLM(),
                embedding_client=FakeEmbedding(),
            )

    def test_native_ollama_backend_snapshot_requires_cpu_and_context(self):
        spec = load_experiment_spec(SPEC)
        response = MagicMock()
        response.json.return_value = {
            "models": [
                {"name": spec.model["model_id"], "digest": "a", "size": 1, "size_vram": 0, "context_length": 4096},
                {"name": spec.embedding["model_id"], "digest": "b", "size": 1, "size_vram": 0, "context_length": 4096},
            ]
        }
        response.raise_for_status.return_value = None
        client = MagicMock()
        client.get.return_value = response
        context = MagicMock()
        context.__enter__.return_value = client
        context.__exit__.return_value = False

        with patch("app.experiments.runner.httpx.Client", return_value=context):
            result = _ollama_loaded_backend_snapshot(spec, exploratory=False)

        self.assertTrue(result["passed"])
        self.assertTrue(all(item["processor"] == "100% CPU" for item in result["models"].values()))

    def test_ollama_listener_snapshot_identifies_the_dedicated_port_process(self):
        connection = SimpleNamespace(
            laddr=SimpleNamespace(port=11435),
            status="LISTEN",
            pid=4321,
        )
        process = MagicMock()
        process.name.return_value = "ollama.exe"
        process.create_time.return_value = 1_700_000_000.0
        with patch(
            "app.experiments.runner.psutil.net_connections",
            return_value=[connection],
        ), patch(
            "app.experiments.runner.psutil.Process",
            return_value=process,
        ):
            result = _ollama_server_process_snapshot("http://127.0.0.1:11435")

        self.assertEqual(result["pid"], 4321)
        self.assertEqual(result["listener_port"], 11435)
        self.assertEqual(result["resource_scope"], "root process and recursive children")

    def test_checksum_verifier_rejects_status_tampering_empty_manifest_and_residual_work(self):
        def artifact_root() -> Path:
            root = TEST_DATA_ROOT / f"checksum-{uuid4()}"
            root.mkdir()
            for name in REQUIRED_ARTIFACTS:
                (root / name).write_text(f"{name}\n", encoding="utf-8", newline="\n")
            _write_checksums(root)
            return root

        tampered = artifact_root()
        (tampered / "status.json").write_text("tampered\n", encoding="utf-8", newline="\n")
        self.assertFalse(verify_checksums(tampered)["valid"])

        empty = artifact_root()
        (empty / "CHECKSUMS.sha256").write_text("", encoding="utf-8", newline="\n")
        self.assertFalse(verify_checksums(empty)["valid"])

        missing = artifact_root()
        (missing / "metrics.json").unlink()
        self.assertFalse(verify_checksums(missing)["valid"])

        residual = artifact_root()
        (residual / "work").mkdir()
        result = verify_checksums(residual)
        self.assertFalse(result["valid"])
        self.assertEqual(result["unexpected_directories"], ["work"])

        duplicate = artifact_root()
        first_line = (duplicate / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()[0]
        with (duplicate / "CHECKSUMS.sha256").open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(first_line + "\n")
        self.assertFalse(verify_checksums(duplicate)["valid"])

    def test_client_factory_closes_llm_when_embedding_initialization_fails(self):
        llm = CloseableFakeLLM()
        spec = load_experiment_spec(SPEC)
        with patch(
            "app.model.openai_compatible_llm.OpenAICompatibleLLM",
            return_value=llm,
        ), patch(
            "app.memory.embedding.openai_compatible_embedding.OpenAICompatibleEmbedding",
            side_effect=RuntimeError("embedding initialization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "embedding initialization failed"):
                _create_clients(spec)

        self.assertTrue(llm.closed)

    def test_client_factory_does_not_send_chat_key_to_a_distinct_embedding_endpoint(self):
        spec = SimpleNamespace(
            model={
                "model_id": "chat-model",
                "base_url": "http://127.0.0.1:11435/v1",
                "api_key_env": "CHAT_KEY",
            },
            embedding={
                "model_id": "embedding-model",
                "base_url": "http://127.0.0.1:11436/v1",
                "api_key_env": "EMBEDDING_KEY",
                "dimensions": 3,
            },
        )
        llm = CloseableFakeLLM()
        embedder = CloseableFakeEmbedding()
        with patch.dict(
            os.environ,
            {"CHAT_KEY": "chat-secret", "EMBEDDING_KEY": ""},
            clear=False,
        ), patch(
            "app.model.openai_compatible_llm.OpenAICompatibleLLM",
            return_value=llm,
        ) as llm_class, patch(
            "app.memory.embedding.openai_compatible_embedding.OpenAICompatibleEmbedding",
            return_value=embedder,
        ) as embedding_class:
            _create_clients(spec)

        self.assertEqual(llm_class.call_args.kwargs["api_key"], "chat-secret")
        self.assertEqual(embedding_class.call_args.kwargs["api_key"], "ollama")


if __name__ == "__main__":
    unittest.main()
