from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
import platform
from pathlib import Path
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlparse

try:
    import winreg
except ImportError:  # pragma: no cover - only relevant to non-Windows analysis hosts
    winreg = None

import httpx
import chromadb
import psutil

from app.experiments.memory_ablation import build_memory_prompt, retrieve_memory_evidence
from app.experiments.rag_ablation import (
    build_rag_prompt,
    ingest_rag_corpus,
    retrieve_rag_evidence,
    score_rag_citations,
)
from app.experiments.resources import ResourceSampler, summarize_resources
from app.experiments.schema import (
    MEMORY_VARIANTS,
    RAG_VARIANTS,
    ExperimentSpec,
    load_dataset,
    load_experiment_spec,
    sha256_file,
)
from app.experiments.scoring import aggregate_cases, score_answer, score_ranked_evidence
from app.knowledge.service import KnowledgeService


BASE_DIR = Path(__file__).resolve().parents[2]
PROVIDER_CIRCUIT_THRESHOLD = 3
PROVIDER_FAILURE_CATEGORIES = frozenset(
    {"timeout", "network", "rate_limit", "provider_error", "model_not_found", "embedding_dimension", "empty_response"}
)
OBSERVED_MODEL_FAILURE_CATEGORIES = frozenset(
    {"timeout", "network", "rate_limit", "provider_error", "empty_response"}
)
REQUIRED_ARTIFACTS = frozenset(
    {
        "manifest.json",
        "cases.jsonl",
        "resource_samples.jsonl",
        "metrics.json",
        "comparison.csv",
        "report.md",
        "status.json",
    }
)


class ProviderCircuitOpen(RuntimeError):
    pass


@dataclass
class ConsecutiveProviderFailureCircuit:
    threshold: int = PROVIDER_CIRCUIT_THRESHOLD
    consecutive_failures: int = 0

    def observe(self, case: dict[str, Any]) -> None:
        if case.get("execution_ok"):
            self.consecutive_failures = 0
            return
        category = str(case.get("failure_category") or "")
        if category not in PROVIDER_FAILURE_CATEGORIES:
            self.consecutive_failures = 0
            return
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.threshold:
            raise ProviderCircuitOpen(
                f"provider circuit opened after {self.consecutive_failures} consecutive {category} failures"
            )


def run_experiment(
    spec_path: str | Path,
    *,
    suite: str = "all",
    output_dir: str | Path | None = None,
    repeats: int | None = None,
    max_cases: int | None = None,
    exploratory: bool = False,
    llm=None,
    embedding_client=None,
) -> dict[str, Any]:
    spec = load_experiment_spec(spec_path)
    dataset = load_dataset(spec)
    selected_suites = _selected_suites(suite)
    configured_repeats = int(spec.execution.get("repeats") or 1)
    actual_repeats = int(repeats if repeats is not None else configured_repeats)
    if actual_repeats < 1:
        raise ValueError("repeats must be >= 1")

    clients_injected = llm is not None or embedding_client is not None
    if clients_injected and (llm is None or embedding_client is None):
        raise ValueError("llm and embedding_client must be injected together")

    run_id = _run_id(spec.experiment_id)
    target = Path(output_dir).resolve() if output_dir else spec.output_root / run_id
    status_path = target / "status.json"
    target_created = False

    try:
        if not clients_injected:
            llm, embedding_client = _create_clients(spec)
        if target.exists():
            raise FileExistsError(f"Experiment output already exists: {target}")
        # Strict cleanliness must be observed before a tracked evidence directory
        # is created; otherwise the run would fail on its own output files.
        preflight = _preflight(
            spec,
            embedding_client=embedding_client,
            exploratory=exploratory,
            skip_provider_runtime=clients_injected,
        )
        seed = int(spec.execution.get("case_order_seed") or 42)
        selected_cases: dict[str, list[dict[str, Any]]] = {}
        variant_orders: dict[str, list[list[str]]] = {}
        if "memory" in selected_suites:
            selected_cases["memory"] = _ordered_cases(
                list(dataset["memory_cases"]), seed=seed, max_cases=max_cases
            )
            variant_orders["memory"] = _balanced_variant_orders(MEMORY_VARIANTS, actual_repeats)
        if "rag" in selected_suites:
            selected_cases["rag"] = _ordered_cases(
                list(dataset["rag_cases"]), seed=seed, max_cases=max_cases
            )
            variant_orders["rag"] = _balanced_variant_orders(RAG_VARIANTS, actual_repeats)
        planned_attempts = sum(
            len(selected_cases[name])
            * actual_repeats
            * len(MEMORY_VARIANTS if name == "memory" else RAG_VARIANTS)
            for name in selected_suites
        )
        manifest = _build_manifest(
            spec,
            dataset,
            run_id=run_id,
            selected_suites=selected_suites,
            repeats=actual_repeats,
            max_cases=max_cases,
            exploratory=exploratory,
            preflight=preflight,
            clients_injected=clients_injected,
            planned_attempts=planned_attempts,
            variant_orders=variant_orders,
        )

        target.mkdir(parents=True, exist_ok=False)
        target_created = True
        _write_json(status_path, {"run_id": run_id, "status": "running", "started_at": _now()})
        _write_json(target / "manifest.json", manifest)

        embedding_probe = (
            manifest.get("preflight", {}).get("provider", {}).get("embedding_probe")
            if not clients_injected
            else None
        )
        manifest["warmup"] = _warm_up(
            llm,
            embedding_client,
            int(spec.execution.get("warmup_requests") or 1),
            embedding_probe=embedding_probe,
        )
        _write_json(target / "manifest.json", manifest)
        if not clients_injected:
            loaded_backend = _ollama_loaded_backend_snapshot(spec, exploratory=exploratory)
            manifest.setdefault("preflight", {}).setdefault("provider", {})["loaded_backend"] = loaded_backend
            _write_json(target / "manifest.json", manifest)
        all_cases: list[dict[str, Any]] = []
        metrics: dict[str, Any] = {
            "run_id": run_id,
            "experiment_id": spec.experiment_id,
            "suites": {},
        }
        resource_records: list[dict[str, Any]] = []
        top_k = int(spec.retrieval.get("top_k") or 3)
        sample_interval = float(spec.execution.get("resource_sample_interval_ms") or 500) / 1000.0
        ollama_root_pid = None
        if not clients_injected:
            ollama_root_pid = int(
                manifest.get("preflight", {}).get("provider", {}).get("server_process", {}).get("pid") or 0
            ) or None
        circuit = ConsecutiveProviderFailureCircuit()

        temp_root = target / "work"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            if "memory" in selected_suites:
                memory_results, memory_metrics, memory_resources = _run_memory_suite(
                    selected_cases["memory"],
                    repeats=actual_repeats,
                    variants=MEMORY_VARIANTS,
                    variant_orders=variant_orders["memory"],
                    llm=llm,
                    embedding_client=embedding_client,
                    top_k=top_k,
                    temp_root=temp_root,
                    sample_interval=sample_interval,
                    ollama_root_pid=ollama_root_pid,
                    circuit=circuit,
                )
                all_cases.extend(memory_results)
                metrics["suites"]["memory"] = memory_metrics
                resource_records.extend(memory_resources)

            if "rag" in selected_suites:
                rag_results, rag_metrics, rag_resources = _run_rag_suite(
                    documents=list(dataset["rag_documents"]),
                    cases=selected_cases["rag"],
                    repeats=actual_repeats,
                    variants=RAG_VARIANTS,
                    variant_orders=variant_orders["rag"],
                    llm=llm,
                    embedding_client=embedding_client,
                    top_k=top_k,
                    temp_root=temp_root,
                    sample_interval=sample_interval,
                    collection_name=_collection_name(spec),
                    retrieval_config={
                        **spec.retrieval,
                        "embedding_provider": spec.embedding["provider"],
                        "embedding_model_id": spec.embedding["model_id"],
                    },
                    ollama_root_pid=ollama_root_pid,
                    circuit=circuit,
                )
                all_cases.extend(rag_results)
                metrics["suites"]["rag"] = rag_metrics
                resource_records.extend(rag_resources)
        finally:
            _remove_work_dir(temp_root)

        actual_attempts = len(all_cases)
        if actual_attempts != planned_attempts:
            raise RuntimeError(
                f"Experiment attempt count mismatch: planned={planned_attempts} actual={actual_attempts}"
            )
        manifest["execution"]["actual_attempts"] = actual_attempts
        backend_verified = bool(
            clients_injected
            or (manifest.get("preflight", {}).get("provider", {}).get("loaded_backend") or {}).get("passed")
        )
        manifest["completion_gate"] = _completion_gate(
            all_cases,
            planned_attempts=planned_attempts,
            actual_attempts=actual_attempts,
            backend_verified=backend_verified,
        )
        manifest["publishable"] = bool(
            manifest.get("publishable_candidate")
            and manifest["completion_gate"]["passed"]
        )
        _write_json(target / "manifest.json", manifest)
        metrics["summary"] = _overall_summary(all_cases)
        metrics["finished_at"] = _now()
        _write_jsonl(target / "cases.jsonl", all_cases)
        _write_jsonl(target / "resource_samples.jsonl", resource_records)
        _write_json(target / "metrics.json", metrics)
        _write_comparison_csv(target / "comparison.csv", metrics)
        with (target / "report.md").open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(_render_report(manifest, metrics))
        final_status = {
            "run_id": run_id,
            "status": "completed",
            "started_at": manifest["started_at"],
            "finished_at": metrics["finished_at"],
            "publishable": bool(manifest["publishable"]),
            "planned_attempts": planned_attempts,
            "actual_attempts": actual_attempts,
            "checksums_verified": True,
            "output_dir": _portable_path(target),
        }
        _write_json(status_path, final_status)
        _write_checksums(target)
        checksum_verification = verify_checksums(target)
        if not checksum_verification["valid"]:
            raise RuntimeError("Experiment artifact checksum verification failed")
        return {"status": final_status, "manifest": manifest, "metrics": metrics, "output_dir": _portable_path(target)}
    except Exception as exc:
        if target_created:
            _write_json(
                status_path,
                {
                    "run_id": run_id,
                    "status": "failed",
                    "finished_at": _now(),
                    "error_type": _classify_error(exc),
                    "error": _safe_error(exc),
                },
            )
        raise
    finally:
        if not clients_injected:
            _close_client(embedding_client)
            _close_client(llm)


def validate_experiment(spec_path: str | Path, *, live: bool = False, exploratory: bool = False) -> dict[str, Any]:
    spec = load_experiment_spec(spec_path)
    dataset = load_dataset(spec)
    result = {
        "valid": True,
        "experiment_id": spec.experiment_id,
        "spec_sha256": sha256_file(spec.path),
        "dataset_sha256": sha256_file(spec.dataset_path),
        "memory_cases": len(dataset["memory_cases"]),
        "rag_documents": len(dataset["rag_documents"]),
        "rag_cases": len(dataset["rag_cases"]),
        "live_preflight": None,
    }
    if live:
        llm = None
        embedding = None
        try:
            llm, embedding = _create_clients(spec)
            result["live_preflight"] = _preflight(
                spec,
                embedding_client=embedding,
                exploratory=exploratory,
                skip_provider_runtime=False,
            )
        finally:
            _close_client(embedding)
            _close_client(llm)
    return result


def _run_memory_suite(
    cases: list[dict[str, Any]],
    *,
    repeats: int,
    variants: tuple[str, ...],
    variant_orders: list[list[str]],
    llm,
    embedding_client,
    top_k: int,
    temp_root: Path,
    sample_interval: float,
    ollama_root_pid: int | None,
    circuit: ConsecutiveProviderFailureCircuit,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in variants}
    samples_by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in variants}
    resources: list[dict[str, Any]] = []
    for repeat, order in enumerate(variant_orders, start=1):
        for order_position, variant in enumerate(order, start=1):
            sampler = ResourceSampler(sample_interval, ollama_root_pid=ollama_root_pid).start()
            try:
                for case in cases:
                    started = time.perf_counter()
                    generation_latency_ms = None
                    retrieval_latency_ms = None
                    write_latency_ms = None
                    candidate_count = 0
                    selected_context_count = 0
                    selected_evidence: list[dict[str, Any]] = []
                    evidence_score: dict[str, Any] | None = None
                    failure_stage = "retrieval"
                    try:
                        retrieval = retrieve_memory_evidence(
                            variant=variant,
                            case=case,
                            embedding_client=embedding_client,
                            top_k=top_k,
                            settings_dir=temp_root / "memory_settings" / variant / f"r{repeat}" / case["id"],
                        )
                        write_latency_ms = retrieval["write_latency_ms"]
                        retrieval_latency_ms = retrieval["retrieval_latency_ms"]
                        candidate_count = int(retrieval.get("candidate_count") or 0)
                        selected_context_count = int(retrieval.get("selected_count") or 0)
                        selected_evidence = list(retrieval["evidence"])
                        expected = dict(case.get("expected") or {})
                        evidence_score = score_ranked_evidence(
                            [
                                item.get("observation_id", "")
                                for item in selected_evidence
                                if item.get("observation_id")
                            ],
                            expected.get("evidence_groups") or [],
                            expected.get("forbidden_evidence_ids") or [],
                        )
                        prompt = build_memory_prompt(case, selected_evidence)
                        failure_stage = "generation"
                        generation_started = time.perf_counter()
                        answer = llm.generate(prompt)
                        generation_latency_ms = _elapsed_ms(generation_started)
                        failure_stage = "response_validation"
                        if not str(answer).strip():
                            raise RuntimeError("model returned an empty response")
                        payload = {
                            "suite": "memory",
                            "variant": variant,
                            "repeat": repeat,
                            "variant_order_position": order_position,
                            "case_id": case["id"],
                            "category": case.get("category", ""),
                            "language": case.get("language", ""),
                            "answerability": _answerability(case),
                            "execution_ok": True,
                            "answer": answer,
                            "answer_score": score_answer(answer, expected),
                            "evidence_score": evidence_score,
                            "selected_evidence": selected_evidence,
                            "write_actions": [item.get("action") for item in retrieval["write_results"]],
                            "candidate_count": candidate_count,
                            "selected_context_count": selected_context_count,
                            "write_latency_ms": write_latency_ms,
                            "retrieval_latency_ms": retrieval_latency_ms,
                            "generation_latency_ms": generation_latency_ms,
                            "end_to_end_latency_ms": _elapsed_ms(started),
                            "failure_elapsed_ms": None,
                            "citation_applicable": False,
                            "citation_hit": False,
                            "citation_precision": 0.0,
                        }
                    except Exception as exc:
                        payload = _failed_case(
                            suite="memory",
                            variant=variant,
                            repeat=repeat,
                            order_position=order_position,
                            case=case,
                            started=started,
                            write_latency_ms=write_latency_ms,
                            retrieval_latency_ms=retrieval_latency_ms,
                            generation_latency_ms=generation_latency_ms,
                            candidate_count=candidate_count,
                            selected_context_count=selected_context_count,
                            failure_stage=failure_stage,
                            exc=exc,
                            evidence_score=evidence_score,
                            selected_evidence=selected_evidence,
                        )
                    by_variant[variant].append(payload)
                    results.append(payload)
                    circuit.observe(payload)
            finally:
                _stop_sampler_preserving_active_error(sampler)
                samples_by_variant[variant].extend(sampler.samples)
                resources.extend(
                    {
                        "suite": "memory",
                        "variant": variant,
                        "repeat": repeat,
                        "variant_order_position": order_position,
                        **sample,
                    }
                    for sample in sampler.samples
                )
    summaries = {
        variant: {
            **aggregate_cases(by_variant[variant]),
            "resources": summarize_resources(samples_by_variant[variant]),
        }
        for variant in variants
    }
    return results, {
        "variants": summaries,
        "case_count": len(cases),
        "repeats": repeats,
        "variant_order_by_repeat": _order_records(variant_orders),
        "paired_rubric_accuracy": _paired_rubric_deltas(results, variants),
    }, resources


def _run_rag_suite(
    *,
    documents: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    repeats: int,
    variants: tuple[str, ...],
    variant_orders: list[list[str]],
    llm,
    embedding_client,
    top_k: int,
    temp_root: Path,
    sample_interval: float,
    collection_name: str,
    retrieval_config: dict[str, Any],
    ollama_root_pid: int | None,
    circuit: ConsecutiveProviderFailureCircuit,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    user_id = "thesis-rag-v1"
    chroma_client = chromadb.EphemeralClient(
        settings=chromadb.config.Settings(anonymized_telemetry=False)
    )
    service = KnowledgeService(
        base_dir=str(temp_root / "rag_documents"),
        embedding_client=embedding_client,
        collection_name=collection_name,
        chroma_client=chroma_client,
        embedding_provider=str(retrieval_config["embedding_provider"]),
        embedding_model_id=str(retrieval_config["embedding_model_id"]),
        chunk_size_chars=int(retrieval_config["chunk_size_chars"]),
        chunk_overlap_chars=int(retrieval_config["chunk_overlap_chars"]),
        candidate_multiplier=int(retrieval_config["candidate_multiplier"]),
        selection_context_budget_tokens=int(retrieval_config["selection_context_budget_tokens"]),
        reranker_version=str(retrieval_config["reranker"]),
    )
    corpus_sampler = ResourceSampler(sample_interval, ollama_root_pid=ollama_root_pid).start()
    try:
        ingestion = ingest_rag_corpus(service, documents, user_id)
    finally:
        ingestion_resources = _stop_sampler_preserving_active_error(corpus_sampler)
    resources: list[dict[str, Any]] = [
        {"suite": "rag_indexing", "variant": "shared", **sample}
        for sample in corpus_sampler.samples
    ]
    results: list[dict[str, Any]] = []
    by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in variants}
    samples_by_variant: dict[str, list[dict[str, Any]]] = {variant: [] for variant in variants}
    for repeat, order in enumerate(variant_orders, start=1):
        for order_position, variant in enumerate(order, start=1):
            sampler = ResourceSampler(sample_interval, ollama_root_pid=ollama_root_pid).start()
            try:
                for case in cases:
                    started = time.perf_counter()
                    generation_latency_ms = None
                    retrieval_latency_ms = None
                    candidate_count = 0
                    selected_context_count = 0
                    selected_evidence: list[dict[str, Any]] = []
                    evidence_score: dict[str, Any] | None = None
                    failure_stage = "retrieval"
                    try:
                        retrieval = retrieve_rag_evidence(
                            service=service,
                            user_id=user_id,
                            variant=variant,
                            case=case,
                            aliases_by_file_id=ingestion["aliases_by_file_id"],
                            top_k=top_k,
                        )
                        retrieval_latency_ms = retrieval["retrieval_latency_ms"]
                        candidate_count = int(retrieval.get("candidate_count") or 0)
                        selected_evidence = list(retrieval["evidence"])
                        selected_context_count = len(selected_evidence)
                        retrieval_citation = score_rag_citations(case, selected_evidence, "")
                        evidence_score = {
                            "applicable": bool(retrieval_citation["citation_applicable"]),
                            "recall_at_k": retrieval_citation["support_recall_at_k"],
                            "precision_at_k": retrieval_citation["support_precision_at_k"],
                            "mrr": retrieval_citation["support_mrr"],
                            "hit_at_k": retrieval_citation["support_hit_at_k"],
                            "leakage": False,
                            "leakage_applicable": False,
                            "forbidden_hits": [],
                        }
                        prompt = build_rag_prompt(case, selected_evidence)
                        failure_stage = "generation"
                        generation_started = time.perf_counter()
                        answer = llm.generate(prompt)
                        generation_latency_ms = _elapsed_ms(generation_started)
                        failure_stage = "response_validation"
                        if not str(answer).strip():
                            raise RuntimeError("model returned an empty response")
                        expected = dict(case.get("expected") or {})
                        citation = score_rag_citations(case, selected_evidence, answer)
                        payload = {
                            "suite": "rag",
                            "variant": variant,
                            "repeat": repeat,
                            "variant_order_position": order_position,
                            "case_id": case["id"],
                            "category": case.get("category", ""),
                            "language": case.get("language", ""),
                            "answerability": _answerability(case),
                            "execution_ok": True,
                            "answer": answer,
                            "answer_score": score_answer(answer, expected),
                            "evidence_score": evidence_score,
                            "selected_evidence": selected_evidence,
                            "candidate_count": candidate_count,
                            "selected_context_count": selected_context_count,
                            "write_latency_ms": None,
                            "retrieval_latency_ms": retrieval_latency_ms,
                            "generation_latency_ms": generation_latency_ms,
                            "end_to_end_latency_ms": _elapsed_ms(started),
                            "failure_elapsed_ms": None,
                            **citation,
                        }
                    except Exception as exc:
                        payload = _failed_case(
                            suite="rag",
                            variant=variant,
                            repeat=repeat,
                            order_position=order_position,
                            case=case,
                            started=started,
                            write_latency_ms=None,
                            retrieval_latency_ms=retrieval_latency_ms,
                            generation_latency_ms=generation_latency_ms,
                            candidate_count=candidate_count,
                            selected_context_count=selected_context_count,
                            failure_stage=failure_stage,
                            exc=exc,
                            evidence_score=evidence_score,
                            selected_evidence=selected_evidence,
                        )
                    by_variant[variant].append(payload)
                    results.append(payload)
                    circuit.observe(payload)
            finally:
                _stop_sampler_preserving_active_error(sampler)
                samples_by_variant[variant].extend(sampler.samples)
                resources.extend(
                    {
                        "suite": "rag",
                        "variant": variant,
                        "repeat": repeat,
                        "variant_order_position": order_position,
                        **sample,
                    }
                    for sample in sampler.samples
                )
    summaries = {
        variant: {
            **aggregate_cases(by_variant[variant]),
            "resources": summarize_resources(samples_by_variant[variant]),
        }
        for variant in variants
    }
    return (
        results,
        {
            "variants": summaries,
            "case_count": len(cases),
            "repeats": repeats,
            "variant_order_by_repeat": _order_records(variant_orders),
            "paired_rubric_accuracy": _paired_rubric_deltas(results, variants),
            "index_isolation": "one shared immutable ephemeral Chroma index across all RAG arms",
            "shared_indexing_latency_ms": ingestion["indexing_latency_ms"],
            "shared_indexing_resources": ingestion_resources,
            "documents": ingestion["uploads"],
        },
        resources,
    )


def _create_clients(spec: ExperimentSpec):
    from app.memory.embedding.openai_compatible_embedding import OpenAICompatibleEmbedding
    from app.model.openai_compatible_llm import OpenAICompatibleLLM

    model = spec.model
    embedding = spec.embedding
    api_key = os.getenv(str(model.get("api_key_env") or ""), "") or "ollama"
    embedding_api_key = os.getenv(str(embedding.get("api_key_env") or ""), "").strip()
    same_endpoint = str(model["base_url"]).rstrip("/").casefold() == str(
        embedding["base_url"]
    ).rstrip("/").casefold()
    if not embedding_api_key:
        embedding_api_key = api_key if same_endpoint else "ollama"
    llm = OpenAICompatibleLLM(
        model_id=str(model["model_id"]),
        temperature=float(model.get("temperature", 0.0)),
        base_url=str(model["base_url"]),
        api_key=api_key,
        timeout_seconds=float(model.get("timeout_seconds", 120)),
        max_retries=int(model.get("max_retries", 0)),
        seed=int(model.get("seed", 42)),
        max_tokens=int(model.get("max_tokens", 128)),
        trust_env_proxy=False,
    )
    try:
        embedder = OpenAICompatibleEmbedding(
            model=str(embedding["model_id"]),
            base_url=str(embedding["base_url"]),
            api_key=embedding_api_key,
            timeout_seconds=float(embedding.get("timeout_seconds", 60)),
            max_retries=int(embedding.get("max_retries", 0)),
            expected_dimensions=int(embedding.get("dimensions", 0)),
            trust_env_proxy=False,
        )
    except Exception:
        _close_client(llm)
        raise
    return llm, embedder


def _close_client(client) -> None:
    close = getattr(client, "close", None)
    if not callable(close):
        return
    try:
        close()
    except Exception:
        # Artifact status should reflect experiment execution, not cleanup noise.
        return


def _preflight(
    spec: ExperimentSpec,
    *,
    embedding_client,
    exploratory: bool,
    skip_provider_runtime: bool,
) -> dict[str, Any]:
    observed_hardware = _hardware_snapshot()
    hardware_checks = _hardware_checks(spec.raw.get("hardware") or {}, observed_hardware)
    failed_hardware = [check for check in hardware_checks if not check["passed"]]
    dependencies = _dependency_snapshot()
    failed_dependencies = [check for check in dependencies["checks"] if not check["passed"]]
    git = _git_snapshot()
    provider = {"skipped": skip_provider_runtime}
    if not skip_provider_runtime:
        provider = _ollama_snapshot(spec)
        expected_backend = str(spec.model.get("compute_backend") or "")
        declared_backend = str(os.getenv("MYAI_EXPERIMENT_COMPUTE_BACKEND") or "")
        provider["compute_backend_contract"] = {
            "expected": expected_backend,
            "operator_declared": declared_backend,
            "operator_declaration_matches": bool(declared_backend and declared_backend == expected_backend),
            "verification_scope": "optional operator declaration; the strict gate uses Ollama /api/ps after warm-up",
        }
        probe_started = time.perf_counter()
        vector = embedding_client.embed("MyAI reproducibility probe: ORBIT-2048")
        probe_latency_ms = _elapsed_ms(probe_started)
        vector_bytes = vector.astype("float32").tobytes()
        provider["embedding_probe"] = {
            "dimensions": int(vector.shape[0]),
            "sha256": hashlib.sha256(vector_bytes).hexdigest(),
            "latency_ms": probe_latency_ms,
            "used_as_warmup": True,
        }
        expected_dimensions = int(spec.embedding.get("dimensions") or 0)
        if expected_dimensions and int(vector.shape[0]) != expected_dimensions:
            raise RuntimeError(
                f"Embedding dimension mismatch: expected={expected_dimensions} actual={vector.shape[0]}"
            )
    if not exploratory:
        if failed_hardware:
            raise RuntimeError("Hardware baseline mismatch: " + "; ".join(item["message"] for item in failed_hardware))
        if failed_dependencies:
            raise RuntimeError(
                "Python dependency baseline mismatch: "
                + "; ".join(item["message"] for item in failed_dependencies)
            )
        if git["dirty"]:
            raise RuntimeError("Publishable experiment requires a clean Git working tree")
    return {
        "hardware": observed_hardware,
        "hardware_checks": hardware_checks,
        "dependencies": dependencies,
        "git": git,
        "provider": provider,
    }


def _dependency_snapshot() -> dict[str, Any]:
    requirements = BASE_DIR / "requirements.txt"
    pinned: dict[str, str] = {}
    # The committed Windows lock file carries a UTF-8 BOM.  Using utf-8-sig
    # keeps the first distribution name canonical for importlib.metadata.
    for line in requirements.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "==" not in stripped:
            continue
        name, version = stripped.split("==", 1)
        pinned[name.lower()] = version
    checks = []
    observed = {}
    for package, expected in sorted(pinned.items()):
        try:
            actual = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            actual = "missing"
        observed[package] = actual
        checks.append(
            {
                "package": package,
                "passed": bool(expected and actual == expected),
                "message": f"{package}: expected {expected or '<unpinned>'}; actual {actual}",
            }
        )
    return {
        "requirements_sha256": sha256_file(requirements),
        "observed": observed,
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
    }


def _ollama_snapshot(spec: ExperimentSpec) -> dict[str, Any]:
    base_url = str(spec.model["base_url"]).rstrip("/")
    root = re.sub(r"/v1$", "", base_url)
    with httpx.Client(timeout=5.0, trust_env=False) as client:
        version_response = client.get(f"{root}/api/version")
        version_response.raise_for_status()
        tags_response = client.get(f"{root}/api/tags")
        tags_response.raise_for_status()
    models = tags_response.json().get("models") or []
    indexed = {
        str(item.get("name") or item.get("model") or ""): {
            "name": item.get("name") or item.get("model"),
            "digest": item.get("digest", ""),
            "size": item.get("size", 0),
            "details": item.get("details") or {},
        }
        for item in models
    }
    required = [spec.model["model_id"], spec.embedding["model_id"]]
    missing = [model_id for model_id in required if model_id not in indexed]
    if missing:
        raise RuntimeError(f"Required Ollama models are missing: {', '.join(missing)}")
    for config in (spec.model, spec.embedding):
        expected = str(config.get("digest_prefix") or "").lower()
        actual = str(indexed[str(config["model_id"])].get("digest") or "").lower()
        comparable_digest = actual.removeprefix("sha256:")
        if expected and not comparable_digest.startswith(expected.removeprefix("sha256:")):
            raise RuntimeError(
                f"Model digest mismatch for {config['model_id']}: expected prefix={expected} actual={actual}"
            )
    actual_version = str(version_response.json().get("version", ""))
    expected_version = str(spec.model.get("runtime_version") or "")
    if expected_version and actual_version != expected_version:
        raise RuntimeError(
            f"Ollama runtime version mismatch: expected={expected_version} actual={actual_version}"
        )
    return {
        "runtime": "ollama",
        "version": actual_version,
        "endpoint": root,
        "server_process": _ollama_server_process_snapshot(root),
        "models": {model_id: indexed[model_id] for model_id in required},
    }


def _ollama_server_process_snapshot(base_url: str) -> dict[str, Any]:
    parsed = urlparse(str(base_url))
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    listener_pids: set[int] = set()
    try:
        connections = psutil.net_connections(kind="tcp")
    except psutil.Error as exc:
        raise RuntimeError(f"Could not identify the dedicated Ollama listener on port {port}: {exc}") from exc
    for connection in connections:
        local_address = connection.laddr
        local_port = getattr(local_address, "port", None)
        if local_port is None and isinstance(local_address, tuple) and len(local_address) >= 2:
            local_port = local_address[1]
        if connection.status == psutil.CONN_LISTEN and local_port == port and connection.pid:
            listener_pids.add(int(connection.pid))
    if len(listener_pids) != 1:
        raise RuntimeError(
            f"Expected exactly one Ollama listener process on port {port}; found {sorted(listener_pids)}"
        )
    pid = next(iter(listener_pids))
    try:
        process = psutil.Process(pid)
        name = process.name()
        created_at = datetime.fromtimestamp(process.create_time(), tz=timezone.utc).isoformat()
    except psutil.Error as exc:
        raise RuntimeError(f"Could not inspect Ollama listener process {pid}: {exc}") from exc
    if "ollama" not in str(name).lower():
        raise RuntimeError(f"Listener on port {port} is not an Ollama process: pid={pid} name={name!r}")
    return {
        "pid": pid,
        "name": name,
        "created_at": created_at,
        "listener_port": port,
        "resource_scope": "root process and recursive children",
    }


def _ollama_loaded_backend_snapshot(
    spec: ExperimentSpec,
    *,
    exploratory: bool,
) -> dict[str, Any]:
    base_url = str(spec.model["base_url"]).rstrip("/")
    root = re.sub(r"/v1$", "", base_url)
    with httpx.Client(timeout=5.0, trust_env=False) as client:
        response = client.get(f"{root}/api/ps")
        response.raise_for_status()
    indexed = {
        str(item.get("name") or item.get("model") or ""): item
        for item in response.json().get("models") or []
    }
    required = [str(spec.model["model_id"]), str(spec.embedding["model_id"])]
    expected_context = int(spec.model["context_budget_tokens"])
    checks: list[dict[str, Any]] = []
    observed: dict[str, Any] = {}
    for model_id in required:
        item = indexed.get(model_id)
        if item is None:
            checks.append({"model_id": model_id, "passed": False, "reason": "model is not loaded"})
            continue
        size_vram = int(item.get("size_vram") or 0)
        context_length = int(item.get("context_length") or 0)
        passed = size_vram == 0 and context_length == expected_context
        checks.append(
            {
                "model_id": model_id,
                "passed": passed,
                "reason": (
                    f"expected size_vram=0 and context_length={expected_context}; "
                    f"actual size_vram={size_vram}, context_length={context_length}"
                ),
            }
        )
        observed[model_id] = {
            "digest": item.get("digest", ""),
            "size": int(item.get("size") or 0),
            "size_vram": size_vram,
            "context_length": context_length,
            "processor": "100% CPU" if size_vram == 0 else "GPU or mixed",
            "details": item.get("details") or {},
        }
    passed = len(observed) == len(required) and all(check["passed"] for check in checks)
    if not exploratory and not passed:
        raise RuntimeError(
            "Loaded Ollama backend mismatch: "
            + "; ".join(check["reason"] for check in checks if not check["passed"])
        )
    return {
        "passed": passed,
        "verification_source": "Ollama /api/ps after warm-up",
        "expected_compute_backend": str(spec.model.get("compute_backend") or ""),
        "expected_context_length": expected_context,
        "models": observed,
        "checks": checks,
    }


def _build_manifest(
    spec: ExperimentSpec,
    dataset: dict[str, Any],
    *,
    run_id: str,
    selected_suites: list[str],
    repeats: int,
    max_cases: int | None,
    exploratory: bool,
    preflight: dict[str, Any],
    clients_injected: bool,
    planned_attempts: int,
    variant_orders: dict[str, list[list[str]]],
) -> dict[str, Any]:
    full_dataset = max_cases is None
    configured_repeats = int(spec.execution.get("repeats") or 1)
    publishable_candidate = (
        not exploratory
        and not clients_injected
        and not preflight["git"]["dirty"]
        and full_dataset
        and repeats == configured_repeats
        and set(selected_suites) == {"memory", "rag"}
    )
    requirements = BASE_DIR / "requirements.txt"
    return {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_id": spec.experiment_id,
        "started_at": _now(),
        "publishable": False,
        "publishable_candidate": publishable_candidate,
        "exploratory": exploratory,
        "clients_injected": clients_injected,
        "spec_path": _portable_path(spec.path),
        "spec_sha256": sha256_file(spec.path),
        "dataset": {
            "id": dataset.get("dataset_id", ""),
            "path": _portable_path(spec.dataset_path),
            "sha256": sha256_file(spec.dataset_path),
            "memory_cases": len(dataset["memory_cases"]),
            "rag_documents": len(dataset["rag_documents"]),
            "rag_cases": len(dataset["rag_cases"]),
        },
        "requirements_sha256": sha256_file(requirements),
        "selected_suites": selected_suites,
        "memory_variants": list(MEMORY_VARIANTS),
        "rag_variants": list(RAG_VARIANTS),
        "execution": {
            **spec.execution,
            "actual_repeats": repeats,
            "max_cases": max_cases,
            "planned_attempts": planned_attempts,
            "actual_attempts": None,
            "variant_order_by_suite": {
                name: _order_records(orders) for name, orders in variant_orders.items()
            },
        },
        "retrieval": spec.retrieval,
        "model": _redacted_provider_config(spec.model),
        "embedding": _redacted_provider_config(spec.embedding),
        "preflight": preflight,
        "state_isolation": {
            "memory": "fresh in-memory store per case/arm/repeat",
            "rag": "one shared immutable ephemeral Chroma index across all RAG arms",
            "personal_runtime_data_accessed": False,
        },
    }


def _hardware_snapshot() -> dict[str, Any]:
    memory = psutil.virtual_memory()
    gpu = _gpu_info()
    return {
        "os": platform.platform(),
        "os_version": platform.version(),
        "python": platform.python_version(),
        "cpu": _cpu_name(),
        "cpu_physical_cores": psutil.cpu_count(logical=False),
        "cpu_logical_processors": psutil.cpu_count(logical=True),
        "ram_gib": round(memory.total / (1024**3), 2),
        "gpu": gpu,
    }


def _hardware_checks(expected: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    comparisons = [
        ("os_contains", str(expected.get("os_contains") or ""), str(actual.get("os") or "")),
        ("cpu_contains", str(expected.get("cpu_contains") or ""), str(actual.get("cpu") or "")),
        ("gpu_contains", str(expected.get("gpu_contains") or ""), str((actual.get("gpu") or {}).get("name") or "")),
        ("python", str(expected.get("python") or ""), str(actual.get("python") or "")),
    ]
    for check_id, wanted, observed in comparisons:
        if not wanted:
            continue
        passed = wanted.lower() in observed.lower()
        checks.append({"id": check_id, "passed": passed, "message": f"expected {wanted!r}; actual {observed!r}"})
    for key, actual_key in (("cpu_physical_cores", "cpu_physical_cores"), ("cpu_logical_processors", "cpu_logical_processors")):
        if expected.get(key) is not None:
            passed = int(actual.get(actual_key) or 0) == int(expected[key])
            checks.append({"id": key, "passed": passed, "message": f"expected {expected[key]}; actual {actual.get(actual_key)}"})
    if expected.get("ram_gib_min") is not None:
        passed = float(actual.get("ram_gib") or 0) >= float(expected["ram_gib_min"])
        checks.append({"id": "ram_gib_min", "passed": passed, "message": f"expected >= {expected['ram_gib_min']}; actual {actual.get('ram_gib')}"})
    if expected.get("gpu_memory_mib") is not None:
        actual_memory = int((actual.get("gpu") or {}).get("memory_total_mib") or 0)
        passed = actual_memory == int(expected["gpu_memory_mib"])
        checks.append({"id": "gpu_memory_mib", "passed": passed, "message": f"expected {expected['gpu_memory_mib']}; actual {actual_memory}"})
    if expected.get("nvidia_driver") is not None:
        actual_driver = str((actual.get("gpu") or {}).get("driver_version") or "")
        passed = actual_driver == str(expected["nvidia_driver"])
        checks.append({"id": "nvidia_driver", "passed": passed, "message": f"expected {expected['nvidia_driver']}; actual {actual_driver}"})
    return checks


def _git_snapshot() -> dict[str, Any]:
    def command(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=BASE_DIR.parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return completed.stdout.strip()
    try:
        status = command("status", "--porcelain")
        return {
            "commit": command("rev-parse", "HEAD"),
            "branch": command("branch", "--show-current"),
            "dirty": bool(status),
            "dirty_file_count": len(status.splitlines()) if status else 0,
        }
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unknown", "branch": "unknown", "dirty": True, "dirty_file_count": -1}


def _gpu_info() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "reason": "nvidia-smi not found"}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
            creationflags=creationflags,
        )
        row = next(csv.reader([completed.stdout.strip().splitlines()[0]]))
        return {
            "available": True,
            "name": row[0].strip(),
            "memory_total_mib": int(float(row[1].strip())),
            "driver_version": row[2].strip(),
        }
    except (OSError, subprocess.SubprocessError, StopIteration, ValueError, IndexError):
        return {"available": False, "reason": "nvidia-smi query failed"}


def _cpu_name() -> str:
    if winreg is None:
        return platform.processor()
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    except OSError:
        return platform.processor()


def _warm_up(llm, embedding_client, count: int, *, embedding_probe: dict[str, Any] | None = None) -> dict[str, Any]:
    requests = max(1, count)
    embedding_latencies: list[float] = []
    llm_latencies: list[float] = []
    if embedding_probe is None:
        for _ in range(requests):
            started = time.perf_counter()
            vector = embedding_client.embed("MyAI local embedding warm-up")
            embedding_latencies.append(_elapsed_ms(started))
            if getattr(vector, "size", 0) <= 0:
                raise RuntimeError("embedding warm-up returned an empty vector")
    for _ in range(requests):
        started = time.perf_counter()
        reply = llm.generate("Reply exactly WARMUP_OK")
        llm_latencies.append(_elapsed_ms(started))
        if not str(reply).strip():
            raise RuntimeError("LLM warm-up returned an empty response")
    probe_latency = embedding_probe.get("latency_ms") if embedding_probe else None
    return {
        "contract": "one untimed warm-up request per model before measured cases",
        "included_in_case_latency": False,
        "embedding": {
            "requests": requests,
            "source": "preflight_validation_probe" if embedding_probe is not None else "dedicated_warmup",
            "latency_ms": probe_latency if embedding_probe is not None else round(sum(embedding_latencies), 3),
        },
        "llm": {
            "requests": requests,
            "source": "dedicated_warmup",
            "latency_ms": round(sum(llm_latencies), 3),
        },
    }


def _ordered_cases(cases: list[dict[str, Any]], *, seed: int, max_cases: int | None) -> list[dict[str, Any]]:
    ordered = list(cases)
    random.Random(seed).shuffle(ordered)
    return ordered[:max_cases] if max_cases is not None else ordered


def _remove_work_dir(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path)
    if path.exists():
        raise RuntimeError(f"Experiment work directory cleanup failed: {path}")


def _stop_sampler_preserving_active_error(sampler: ResourceSampler) -> dict[str, Any]:
    active_error = sys.exc_info()[0] is not None
    try:
        return sampler.stop()
    except RuntimeError:
        # Resource collection must fail a successful run, but it must not hide
        # the provider/runtime exception that already made the run fail.
        if not active_error:
            raise
        return summarize_resources(sampler.samples)


def _balanced_variant_orders(variants: tuple[str, ...], repeats: int) -> list[list[str]]:
    values = list(variants)
    return [values[offset % len(values):] + values[:offset % len(values)] for offset in range(repeats)]


def _order_records(orders: list[list[str]]) -> list[dict[str, Any]]:
    return [
        {"repeat": repeat, "order": list(order)}
        for repeat, order in enumerate(orders, start=1)
    ]


def _answerability(case: dict[str, Any]) -> str:
    return "abstention" if bool((case.get("expected") or {}).get("abstain")) else "answerable"


def _paired_rubric_deltas(
    cases: list[dict[str, Any]],
    variants: tuple[str, ...],
) -> dict[str, Any]:
    baseline = variants[0]
    by_variant_case: dict[str, dict[str, list[float]]] = {
        variant: {} for variant in variants
    }
    for case in cases:
        variant = str(case.get("variant") or "")
        case_id = str(case.get("case_id") or "")
        if variant not in by_variant_case:
            continue
        by_variant_case[variant].setdefault(case_id, []).append(
            1.0 if case.get("answer_score", {}).get("correct") else 0.0
        )
    comparisons: dict[str, Any] = {}
    for reference_index, reference in enumerate(variants[:-1]):
        reference_cases = by_variant_case[reference]
        for variant in variants[reference_index + 1:]:
            common = sorted(set(reference_cases) & set(by_variant_case[variant]))
            deltas = [
                statistics.fmean(by_variant_case[variant][case_id])
                - statistics.fmean(reference_cases[case_id])
                for case_id in common
            ]
            comparisons[f"{variant}_vs_{reference}"] = {
                "paired_unique_cases": len(common),
                "mean_delta": round(statistics.fmean(deltas), 4) if deltas else 0.0,
                "bootstrap_95_ci": _bootstrap_mean_ci(deltas, seed=42),
                "wins": sum(1 for value in deltas if value > 0),
                "ties": sum(1 for value in deltas if value == 0),
                "losses": sum(1 for value in deltas if value < 0),
            }
    return {
        "baseline": baseline,
        "comparison_policy": "all forward arm pairs in the preregistered arm order",
        "statistical_unit": "unique_case",
        "technical_repeats_expand_sample_size": False,
        "comparisons": comparisons,
    }


def _bootstrap_mean_ci(values: list[float], *, seed: int, samples: int = 2000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    if len(values) == 1:
        value = round(float(values[0]), 4)
        return [value, value]
    generator = random.Random(seed)
    observed = sorted(
        statistics.fmean(generator.choice(values) for _ in values)
        for _ in range(samples)
    )
    return [round(_percentile(observed, 0.025), 4), round(_percentile(observed, 0.975), 4)]


def _percentile(values: list[float], quantile: float) -> float:
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(len(values) - 1, lower + 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _selected_suites(suite: str) -> list[str]:
    normalized = str(suite or "all").strip().lower()
    if normalized == "all":
        return ["memory", "rag"]
    if normalized in {"memory", "rag"}:
        return [normalized]
    raise ValueError("suite must be one of: all, memory, rag")


def _failed_case(
    *,
    suite: str,
    variant: str,
    repeat: int,
    order_position: int,
    case: dict[str, Any],
    started: float,
    write_latency_ms: float | None,
    retrieval_latency_ms: float | None,
    generation_latency_ms: float | None,
    candidate_count: int,
    selected_context_count: int,
    failure_stage: str,
    exc: Exception,
    evidence_score: dict[str, Any] | None = None,
    selected_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    elapsed_ms = _elapsed_ms(started)
    citation_applicable = bool(case.get("gold_file_aliases") or case.get("gold_evidence"))
    expected = dict(case.get("expected") or {})
    evidence_applicable = (
        bool(case.get("gold_file_aliases") or case.get("gold_evidence"))
        if suite == "rag"
        else bool(expected.get("evidence_groups"))
    )
    preserved_evidence_score = evidence_score or {
        "applicable": evidence_applicable,
        "recall_at_k": 0.0 if evidence_applicable else None,
        "precision_at_k": 0.0 if evidence_applicable else None,
        "mrr": 0.0 if evidence_applicable else None,
        "hit_at_k": False if evidence_applicable else None,
        "leakage": False,
        "leakage_applicable": suite == "memory",
        "forbidden_hits": [],
    }
    payload = {
        "suite": suite,
        "variant": variant,
        "repeat": repeat,
        "variant_order_position": order_position,
        "case_id": case["id"],
        "category": case.get("category", ""),
        "language": case.get("language", ""),
        "answerability": _answerability(case),
        "execution_ok": False,
        "failure_category": _classify_error(exc),
        "failure_stage": failure_stage,
        "error": _safe_error(exc),
        "answer": "",
        "answer_score": {
            "correct": False,
            "normalized_answer": "",
            "abstain_expected": _answerability(case) == "abstention",
        },
        "evidence_score": preserved_evidence_score,
        "selected_evidence": list(selected_evidence or []),
        "candidate_count": candidate_count,
        "selected_context_count": selected_context_count,
        "write_latency_ms": write_latency_ms,
        "retrieval_latency_ms": retrieval_latency_ms,
        "generation_latency_ms": generation_latency_ms,
        "end_to_end_latency_ms": elapsed_ms,
        "failure_elapsed_ms": elapsed_ms,
        "citation_applicable": citation_applicable,
        "support_hit_at_k": (
            preserved_evidence_score.get("hit_at_k") if suite == "rag" else None
        ),
        "support_recall_at_k": (
            preserved_evidence_score.get("recall_at_k") if suite == "rag" else None
        ),
        "support_precision_at_k": (
            preserved_evidence_score.get("precision_at_k") if suite == "rag" else None
        ),
        "support_mrr": preserved_evidence_score.get("mrr") if suite == "rag" else None,
        "citation_hit": False,
        "citation_precision": 0.0,
    }
    if suite == "rag":
        payload.update(
            {
                "generated_citation_count": 0,
                "generated_citation_hit": False,
                "generated_citation_precision": 0.0,
                "invalid_citation": False,
                "no_answer_citation_hallucination": False,
            }
        )
    return payload


def _overall_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "attempts": len(cases),
        "successful_attempts": sum(1 for case in cases if case.get("execution_ok")),
        "failed_attempts": sum(1 for case in cases if not case.get("execution_ok")),
        "failure_rate": round(
            sum(1 for case in cases if not case.get("execution_ok")) / len(cases), 4
        ) if cases else 0.0,
    }


def _completion_gate(
    cases: list[dict[str, Any]],
    *,
    planned_attempts: int,
    actual_attempts: int,
    backend_verified: bool,
) -> dict[str, Any]:
    observed_failures = [case for case in cases if not case.get("execution_ok")]
    infrastructure_failures = [
        case
        for case in observed_failures
        if case.get("failure_category") not in OBSERVED_MODEL_FAILURE_CATEGORIES
    ]
    passed = (
        actual_attempts == planned_attempts
        and not infrastructure_failures
        and backend_verified
    )
    return {
        "passed": passed,
        "planned_attempts": planned_attempts,
        "actual_attempts": actual_attempts,
        "observed_model_failures": len(observed_failures) - len(infrastructure_failures),
        "infrastructure_failures": len(infrastructure_failures),
        "infrastructure_failure_categories": sorted(
            {str(case.get("failure_category") or "unknown") for case in infrastructure_failures}
        ),
        "backend_verified": backend_verified,
        "work_directory_cleaned": True,
        "checksum_verification_required": True,
    }


def _write_comparison_csv(path: Path, metrics: dict[str, Any]) -> None:
    fields = [
        "suite", "variant", "cases", "unique_cases", "rubric_accuracy", "answer_accuracy",
        "answerable_rubric_accuracy", "abstention_rubric_accuracy", "support_hit_at_k",
        "support_applicable_cases", "evidence_recall_at_k", "evidence_precision_at_k",
        "evidence_applicable_cases", "mrr", "citation_hit_rate", "citation_precision",
        "citation_applicable_cases", "grounded_rubric_accuracy", "invalid_citation_rate",
        "leakage_rate", "leakage_applicable_cases", "no_answer_empty_retrieval_rate",
        "no_answer_forbidden_leakage_rate", "failure_rate",
        "candidate_count_mean", "selected_context_count_mean", "write_mean_ms",
        "retrieval_mean_ms", "generation_mean_ms", "end_to_end_p95_ms",
        "all_attempt_end_to_end_p95_ms", "peak_gpu_memory_mib", "peak_ollama_rss_mib",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for suite, suite_payload in metrics.get("suites", {}).items():
            for variant, item in suite_payload.get("variants", {}).items():
                resources = item.get("resources") or {}
                writer.writerow(
                    {
                        "suite": suite,
                        "variant": variant,
                        "cases": item.get("cases", 0),
                        "unique_cases": item.get("unique_cases", 0),
                        "rubric_accuracy": item.get("rubric_accuracy", 0),
                        "answer_accuracy": item.get("answer_accuracy", 0),
                        "answerable_rubric_accuracy": item.get("answerable_rubric_accuracy", 0),
                        "abstention_rubric_accuracy": item.get("abstention_rubric_accuracy", 0),
                        "support_hit_at_k": item.get("support_hit_at_k", 0),
                        "support_applicable_cases": item.get("support_applicable_cases", 0),
                        "evidence_recall_at_k": item.get("evidence_recall_at_k", 0),
                        "evidence_precision_at_k": item.get("evidence_precision_at_k", 0),
                        "evidence_applicable_cases": item.get("evidence_applicable_cases", 0),
                        "mrr": item.get("mrr", 0),
                        "citation_hit_rate": item.get("citation_hit_rate", 0),
                        "citation_precision": item.get("citation_precision", 0),
                        "citation_applicable_cases": item.get("citation_applicable_cases", 0),
                        "grounded_rubric_accuracy": item.get("grounded_rubric_accuracy", 0),
                        "invalid_citation_rate": item.get("invalid_citation_rate", 0),
                        "leakage_rate": item.get("leakage_rate", 0),
                        "leakage_applicable_cases": item.get("leakage_applicable_cases", 0),
                        "no_answer_empty_retrieval_rate": item.get("no_answer_empty_retrieval_rate", 0),
                        "no_answer_forbidden_leakage_rate": item.get("no_answer_forbidden_leakage_rate", 0),
                        "failure_rate": item.get("failure_rate", 0),
                        "candidate_count_mean": item.get("candidate_count_mean", 0),
                        "selected_context_count_mean": item.get("selected_context_count_mean", 0),
                        "write_mean_ms": (item.get("write_latency_ms") or {}).get("mean", 0),
                        "retrieval_mean_ms": (item.get("retrieval_latency_ms") or {}).get("mean", 0),
                        "generation_mean_ms": (item.get("generation_latency_ms") or {}).get("mean", 0),
                        "end_to_end_p95_ms": (item.get("end_to_end_latency_ms") or {}).get("p95", 0),
                        "all_attempt_end_to_end_p95_ms": (
                            item.get("all_attempt_end_to_end_latency_ms") or {}
                        ).get("p95", 0),
                        "peak_gpu_memory_mib": ((resources.get("gpu_memory_used_mib") or {}).get("peak", "")),
                        "peak_ollama_rss_mib": ((resources.get("ollama_rss_mib") or {}).get("peak", "")),
                    }
                )


def _render_report(manifest: dict[str, Any], metrics: dict[str, Any]) -> str:
    evidence_class = (
        "PUBLISHABLE THESIS EVIDENCE"
        if manifest["publishable"]
        else "DIAGNOSTIC / NOT FOR THESIS CITATION"
    )
    suite_samples = []
    for suite, payload in metrics.get("suites", {}).items():
        case_count = int(payload.get("case_count") or 0)
        repeats = int(payload.get("repeats") or 0)
        attempts = case_count * repeats * len((payload.get("variants") or {}).keys())
        suite_samples.append(
            f"`{suite}`: {case_count} unique cases x {repeats} technical repeats "
            f"x {len((payload.get('variants') or {}).keys())} arms = {attempts} attempts"
        )
    lines = [
        f"# MyAI Thesis Core Experiment - {evidence_class}",
        "",
        f"- Run: `{manifest['run_id']}`",
        f"- Evidence class: **{evidence_class}**",
        f"- Dataset: `{manifest['dataset']['id']}` / `{manifest['dataset']['sha256']}`",
        f"- Publishable: `{str(manifest['publishable']).lower()}`",
        f"- Planned/actual attempts: `{manifest['execution']['planned_attempts']}` / "
        f"`{manifest['execution'].get('actual_attempts')}`",
        f"- Requested max cases per suite: `{manifest['execution'].get('max_cases')}`",
        f"- Samples: {'; '.join(suite_samples)}",
        f"- Git: `{manifest['preflight']['git']['commit']}` on `{manifest['preflight']['git']['branch']}`",
        f"- LLM: `{manifest['model']['model_id']}`",
        f"- Embedding: `{manifest['embedding']['model_id']}`",
        "",
        "## Results",
        "",
        "| Suite | Variant | n (unique) | Rubric accuracy | Evidence Recall@K (n) | Support Hit@K (n) | Gold-source citation hit (n) | Grounded answer + citation | Forbidden-evidence exposure (n) | Failure | Retrieval mean ms | Generation mean ms | End-to-end P95 ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for suite, suite_payload in metrics.get("suites", {}).items():
        for variant, item in suite_payload.get("variants", {}).items():
            lines.append(
                "| {suite} | {variant} | {cases} ({unique}) | {accuracy} | {recall} ({evidence_n}) | {support} ({support_n}) | {citation} ({citation_n}) | {grounded} | {leakage} ({leakage_n}) | {failure} | {retrieval:.2f} | {generation:.2f} | {p95:.2f} |".format(
                    suite=suite,
                    variant=variant,
                    cases=int(item.get("cases") or 0),
                    unique=int(item.get("unique_cases") or 0),
                    accuracy=_format_rate(item.get("rubric_accuracy")),
                    support=_format_rate(item.get("support_hit_at_k")),
                    support_n=int(item.get("support_applicable_cases") or 0),
                    recall=_format_rate(item.get("evidence_recall_at_k")),
                    evidence_n=int(item.get("evidence_applicable_cases") or 0),
                    citation=_format_rate(item.get("citation_hit_rate")),
                    citation_n=int(item.get("citation_applicable_cases") or 0),
                    grounded=_format_rate(item.get("grounded_rubric_accuracy")),
                    leakage=_format_rate(item.get("leakage_rate")),
                    leakage_n=int(item.get("leakage_applicable_cases") or 0),
                    failure=_format_rate(item.get("failure_rate")),
                    retrieval=float((item.get("retrieval_latency_ms") or {}).get("mean") or 0),
                    generation=float((item.get("generation_latency_ms") or {}).get("mean") or 0),
                    p95=float((item.get("end_to_end_latency_ms") or {}).get("p95") or 0),
                )
            )
    lines.extend(
        [
            "",
            "## Paired Rubric Accuracy Deltas",
            "",
            "| Suite | Comparison | Paired unique n | Mean delta | Bootstrap 95% CI | Wins / ties / losses |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for suite, suite_payload in metrics.get("suites", {}).items():
        paired = suite_payload.get("paired_rubric_accuracy") or {}
        for comparison, item in (paired.get("comparisons") or {}).items():
            interval = list(item.get("bootstrap_95_ci") or [0.0, 0.0])
            lines.append(
                f"| {suite} | {comparison} | {int(item.get('paired_unique_cases') or 0)} | "
                f"{_format_delta(item.get('mean_delta'))} | "
                f"[{_format_delta(interval[0])}, {_format_delta(interval[1])}] | "
                f"{int(item.get('wins') or 0)} / {int(item.get('ties') or 0)} / "
                f"{int(item.get('losses') or 0)} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- The memory comparison is governed full-stack memory versus a naive vector baseline; it does not attribute gains to one governance mechanism.",
            "- Support Hit@K measures retrieved answer-bearing evidence; generated citation hit separately requires the model to cite such evidence.",
            "- Gold-source citation hit alone does not imply a correct answer; grounded answer + citation requires both the answer rubric and a gold-bearing citation.",
            "- Forbidden-evidence exposure is the historical `leakage_rate` field. It covers every case-declared forbidden context item (for example stale, sensitive, scoped, revoked, or irrelevant evidence) and must not be read as privacy disclosure alone.",
            "- `N/A` means the metric is outside that suite/case contract; it is never converted to a zero. Parenthesized `n` is the metric denominator.",
            "- Rubric accuracy uses deterministic accepted-answer/required-term rules. Raw outputs require manual audit before thesis interpretation.",
            "- Repetitions are technical repeats and never expand the unique-case statistical sample size.",
            "- `hybrid_rerank` uses the project's deterministic lightweight rule reranker, not a cross-encoder.",
            "- Provider validation/warm-up requests are excluded from measured case latency and recorded in `manifest.json`; shared corpus indexing is reported separately.",
            "- The verified compute placement is CPU-only; detected GPU utilization is observational and is not attributed to model inference. The launcher requests `cpu_avx2`, but Ollama does not expose the selected CPU library through `/api/ps`.",
            "- A non-publishable run is diagnostic evidence only and must not be quoted as the final thesis result.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_rate(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.2%}"


def _format_delta(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):+.2%}"


def _write_checksums(root: Path) -> None:
    targets = sorted(
        path for path in root.iterdir()
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    )
    actual_names = {path.name for path in targets}
    if actual_names != REQUIRED_ARTIFACTS:
        raise RuntimeError(
            "Experiment artifact set is incomplete before checksum creation: "
            f"missing={sorted(REQUIRED_ARTIFACTS - actual_names)} "
            f"unexpected={sorted(actual_names - REQUIRED_ARTIFACTS)}"
        )
    content = "\n".join(f"{sha256_file(path)}  {path.name}" for path in targets) + "\n"
    with (root / "CHECKSUMS.sha256").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def verify_checksums(root: str | Path) -> dict[str, Any]:
    resolved = Path(root).resolve()
    checksum_path = resolved / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        return {"valid": False, "checked": 0, "missing": ["CHECKSUMS.sha256"], "mismatched": [], "unexpected": []}
    expected: dict[str, str] = {}
    malformed: list[str] = []
    duplicate_entries: list[str] = []
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if not match:
            malformed.append(line)
            continue
        name = match.group(2)
        if name in expected:
            duplicate_entries.append(name)
            continue
        expected[name] = match.group(1)
    actual_names = {
        path.name
        for path in resolved.iterdir()
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    }
    directories = sorted(path.name for path in resolved.iterdir() if path.is_dir())
    missing = sorted(REQUIRED_ARTIFACTS - actual_names)
    unexpected = sorted(actual_names - REQUIRED_ARTIFACTS)
    mismatched = sorted(
        name
        for name, digest in expected.items()
        if (resolved / name).is_file() and sha256_file(resolved / name) != digest
    )
    return {
        "valid": bool(expected) and not malformed and not duplicate_entries and not missing and not unexpected and not mismatched and not directories and set(expected) == REQUIRED_ARTIFACTS,
        "checked": len(expected),
        "missing": missing,
        "mismatched": mismatched,
        "unexpected": unexpected,
        "malformed": malformed,
        "duplicate_entries": sorted(set(duplicate_entries)),
        "unexpected_directories": directories,
    }


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for payload in payloads:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def _redacted_provider_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in config.items()
        if "key" not in key.lower() and "token" not in key.lower() and "secret" not in key.lower()
    }


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(BASE_DIR.parent).as_posix()
    except ValueError:
        return f"<external>/{path.name}"


def _collection_name(spec: ExperimentSpec) -> str:
    raw = f"thesis_{spec.embedding['provider']}_{spec.embedding['model_id']}"
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", raw).strip("_").lower()


def _run_id(experiment_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{experiment_id}-{stamp}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 3)


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, ProviderCircuitOpen):
        return "provider_circuit_open"
    text = f"{exc.__class__.__name__}: {exc}".lower()
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "connect" in text or "network" in text or "dns" in text:
        return "network"
    if status_code == 429:
        return "rate_limit"
    if "model" in text and ("missing" in text or "not found" in text or "404" in text):
        return "model_not_found"
    if isinstance(status_code, int) and status_code >= 500:
        return "provider_error"
    if "apistatuserror" in text or re.search(r"\b5\d\d\b", text):
        return "provider_error"
    if "embedding" in text and "dimension" in text:
        return "embedding_dimension"
    if "empty" in text:
        return "empty_response"
    return "runtime_error"


def _safe_error(exc: Exception) -> str:
    return (str(exc).strip() or exc.__class__.__name__)[:300]
