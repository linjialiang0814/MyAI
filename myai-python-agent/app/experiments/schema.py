from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse


MEMORY_VARIANTS = ("none", "basic", "governed")
RAG_VARIANTS = ("vector", "hybrid", "hybrid_rerank")
ARTIFACT_FORMATS = ("json", "jsonl", "csv", "markdown", "sha256")
SAFE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")


@dataclass(frozen=True)
class ExperimentSpec:
    path: Path
    raw: dict[str, Any]
    dataset_path: Path
    output_root: Path

    @property
    def experiment_id(self) -> str:
        return str(self.raw["experiment_id"])

    @property
    def execution(self) -> dict[str, Any]:
        return dict(self.raw.get("execution") or {})

    @property
    def model(self) -> dict[str, Any]:
        return dict(self.raw.get("model") or {})

    @property
    def embedding(self) -> dict[str, Any]:
        return dict(self.raw.get("embedding") or {})

    @property
    def retrieval(self) -> dict[str, Any]:
        return dict(self.raw.get("retrieval") or {})


def load_experiment_spec(path: str | Path) -> ExperimentSpec:
    resolved = Path(path).resolve()
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    _validate_spec(raw)
    dataset_path = (resolved.parent / str(raw["dataset"]["path"])).resolve()
    if not dataset_path.is_file():
        raise ValueError(f"Experiment dataset does not exist: {dataset_path}")
    expected_hash = str(raw["dataset"].get("sha256") or "").strip().lower()
    actual_hash = sha256_file(dataset_path)
    if expected_hash and expected_hash != actual_hash:
        raise ValueError(
            f"Dataset SHA-256 mismatch: expected={expected_hash} actual={actual_hash}"
        )
    output_root = (resolved.parent / str(raw["artifacts"]["output_root"])).resolve()
    return ExperimentSpec(
        path=resolved,
        raw=raw,
        dataset_path=dataset_path,
        output_root=output_root,
    )


def load_dataset(spec: ExperimentSpec) -> dict[str, Any]:
    payload = json.loads(spec.dataset_path.read_text(encoding="utf-8"))
    _validate_dataset(payload)
    return payload


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_loopback_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _validate_spec(raw: dict[str, Any]) -> None:
    if int(raw.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported experiment spec schema_version")
    for key in ("experiment_id", "model", "embedding", "dataset", "execution", "retrieval", "artifacts"):
        if not raw.get(key):
            raise ValueError(f"Experiment spec is missing required section: {key}")

    model = raw["model"]
    embedding = raw["embedding"]
    execution = raw["execution"]
    retrieval = raw["retrieval"]
    dataset = raw["dataset"]
    artifacts = raw["artifacts"]
    hardware = raw.get("hardware") or {}
    if not SAFE_ID_PATTERN.fullmatch(str(raw.get("experiment_id") or "")):
        raise ValueError("experiment_id must be a safe lowercase slug")
    _require_fields(
        model,
        (
            "runtime", "runtime_version", "compute_backend", "model_id", "digest_prefix", "base_url", "api_key_env",
            "temperature", "seed", "max_tokens", "context_budget_tokens",
            "timeout_seconds", "max_retries", "fallback_to_stub",
        ),
        "model",
    )
    _require_fields(
        embedding,
        (
            "runtime", "runtime_version", "compute_backend", "model_id", "digest_prefix", "base_url", "api_key_env",
            "dimensions", "timeout_seconds", "max_retries", "fallback_to_stub",
        ),
        "embedding",
    )
    _require_fields(
        retrieval,
        (
            "top_k", "candidate_multiplier", "chunk_size_chars", "chunk_overlap_chars",
            "selection_context_budget_tokens", "reranker",
        ),
        "retrieval",
    )
    _require_fields(
        execution,
        (
            "repeats", "warmup_requests", "case_order_seed", "concurrency",
            "resource_sample_interval_ms", "require_loopback",
        ),
        "execution",
    )
    _require_fields(
        hardware,
        (
            "os_contains", "cpu_contains", "cpu_physical_cores", "cpu_logical_processors",
            "ram_gib_min", "gpu_contains", "gpu_memory_mib", "nvidia_driver", "python",
        ),
        "hardware",
    )
    _require_fields(dataset, ("path", "sha256"), "dataset")
    _require_fields(artifacts, ("output_root", "formats"), "artifacts")
    if tuple(artifacts.get("formats") or ()) != ARTIFACT_FORMATS:
        raise ValueError(f"artifacts.formats must be exactly {list(ARTIFACT_FORMATS)}")
    if model.get("provider") != "openai_compatible":
        raise ValueError("Thesis baseline requires model provider=openai_compatible")
    if embedding.get("provider") != "openai_compatible":
        raise ValueError("Thesis baseline requires embedding provider=openai_compatible")
    if bool(model.get("fallback_to_stub", True)) or bool(embedding.get("fallback_to_stub", True)):
        raise ValueError("Thesis experiments require all Stub fallback to be disabled")
    if str(model.get("runtime")) != "ollama" or str(embedding.get("runtime")) != "ollama":
        raise ValueError("Thesis baseline requires runtime=ollama")
    if model.get("runtime_version") != embedding.get("runtime_version"):
        raise ValueError("Model and embedding must use the same frozen runtime_version")
    if model.get("compute_backend") != "cpu_only" or embedding.get("compute_backend") != "cpu_only":
        raise ValueError("Thesis baseline requires compute_backend=cpu_only")
    if float(model.get("temperature")) != 0.0:
        raise ValueError("Thesis baseline requires model.temperature=0")
    if int(model.get("seed")) != 42:
        raise ValueError("Thesis baseline requires model.seed=42")
    if int(model.get("max_retries")) != 0 or int(embedding.get("max_retries")) != 0:
        raise ValueError("Thesis baseline requires provider max_retries=0")
    if int(embedding.get("dimensions")) != 1024:
        raise ValueError("Thesis baseline requires embedding.dimensions=1024")
    for label, config in (("model", model), ("embedding", embedding)):
        digest = str(config.get("digest_prefix") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{12,64}", digest):
            raise ValueError(f"{label}.digest_prefix must contain 12-64 lowercase hexadecimal characters")
        timeout = float(config.get("timeout_seconds") or 0)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError(f"{label}.timeout_seconds must be finite and > 0")
    dataset_hash = str(dataset.get("sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", dataset_hash):
        raise ValueError("dataset.sha256 must be a complete SHA-256 digest")
    if bool(execution.get("require_loopback", True)):
        for label, endpoint in (
            ("model", str(model.get("base_url") or "")),
            ("embedding", str(embedding.get("base_url") or "")),
        ):
            if not is_loopback_url(endpoint):
                raise ValueError(f"{label} endpoint must be loopback for the frozen local baseline")
    if int(execution.get("repeats") or 0) != 3:
        raise ValueError("Thesis baseline requires execution.repeats=3")
    if int(execution.get("warmup_requests") or 0) != 1:
        raise ValueError("Thesis baseline requires execution.warmup_requests=1")
    if int(execution.get("case_order_seed") or 0) != 42:
        raise ValueError("Thesis baseline requires execution.case_order_seed=42")
    if int(execution.get("concurrency") or 0) != 1:
        raise ValueError("Thesis experiments require execution.concurrency=1")
    if int(retrieval.get("top_k") or 0) < 1:
        raise ValueError("retrieval.top_k must be >= 1")
    if int(retrieval.get("candidate_multiplier") or 0) < 1:
        raise ValueError("retrieval.candidate_multiplier must be >= 1")
    chunk_size = int(retrieval.get("chunk_size_chars") or 0)
    chunk_overlap = int(retrieval.get("chunk_overlap_chars"))
    if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("retrieval chunk size/overlap contract is invalid")
    if int(retrieval.get("selection_context_budget_tokens") or 0) < 1:
        raise ValueError("retrieval.selection_context_budget_tokens must be >= 1")
    if retrieval.get("reranker") != "lightweight_rule_v1":
        raise ValueError("Thesis baseline requires reranker=lightweight_rule_v1")
    if int(model.get("max_tokens") or 0) < 1 or int(model.get("context_budget_tokens") or 0) < 1:
        raise ValueError("model token budgets must be >= 1")
    if int(execution.get("resource_sample_interval_ms") or 0) < 1:
        raise ValueError("execution.resource_sample_interval_ms must be >= 1")
    if not bool(execution.get("require_loopback")):
        raise ValueError("Thesis baseline requires execution.require_loopback=true")
    if tuple(raw.get("memory_variants") or ()) != MEMORY_VARIANTS:
        raise ValueError(f"memory_variants must be exactly {list(MEMORY_VARIANTS)}")
    if tuple(raw.get("rag_variants") or ()) != RAG_VARIANTS:
        raise ValueError(f"rag_variants must be exactly {list(RAG_VARIANTS)}")


def _validate_dataset(payload: dict[str, Any]) -> None:
    if int(payload.get("schema_version") or 0) != 1:
        raise ValueError("Unsupported experiment dataset schema_version")
    memory_cases = list(payload.get("memory_cases") or [])
    rag_documents = list(payload.get("rag_documents") or [])
    rag_cases = list(payload.get("rag_cases") or [])
    if not memory_cases or not rag_documents or not rag_cases:
        raise ValueError("Dataset must contain memory_cases, rag_documents, and rag_cases")

    case_ids = [str(case.get("id") or "") for case in [*memory_cases, *rag_cases]]
    if any(not SAFE_ID_PATTERN.fullmatch(case_id) for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
        raise ValueError("Experiment case ids must be non-empty and unique")
    aliases = [str(document.get("alias") or "") for document in rag_documents]
    if any(not SAFE_ID_PATTERN.fullmatch(alias) for alias in aliases) or len(aliases) != len(set(aliases)):
        raise ValueError("RAG document aliases must be non-empty and unique")
    documents_by_alias = {
        str(document["alias"]): str(document.get("content") or "")
        for document in rag_documents
    }
    if any(not content.strip() for content in documents_by_alias.values()):
        raise ValueError("RAG document content must be non-empty")

    observation_ids: set[str] = set()
    for case in memory_cases:
        _validate_case_rubric(case)
        _validate_language(case)
        observations = list(case.get("observations") or [])
        if not observations:
            raise ValueError(f"Memory case {case['id']} has no observations")
        local_ids = {str(item.get("id") or "") for item in observations}
        if "" in local_ids or len(local_ids) != len(observations):
            raise ValueError(f"Memory case {case['id']} has invalid observation ids")
        if observation_ids & local_ids:
            raise ValueError(f"Memory observation ids must be globally unique: {case['id']}")
        observation_ids.update(local_ids)
        expected = dict(case.get("expected") or {})
        referenced = {
            str(item)
            for group in expected.get("evidence_groups") or []
            for item in group
        } | {str(item) for item in expected.get("forbidden_evidence_ids") or []}
        if not referenced <= local_ids:
            raise ValueError(f"Memory case {case['id']} references an unknown observation id")

    for case in rag_cases:
        _validate_case_rubric(case)
        _validate_language(case)
        gold_aliases = [str(item) for item in case.get("gold_file_aliases") or []]
        if not set(gold_aliases) <= set(documents_by_alias):
            raise ValueError(f"RAG case {case['id']} references an unknown file alias")
        explicit = list(case.get("gold_evidence") or [])
        if explicit:
            explicit_aliases = [str(item.get("file_alias") or "") for item in explicit]
            if set(explicit_aliases) != set(gold_aliases):
                raise ValueError(f"RAG case {case['id']} gold_evidence aliases do not match gold_file_aliases")
            for item in explicit:
                alias = str(item.get("file_alias") or "")
                anchors = [str(anchor) for anchor in item.get("anchors") or []]
                if item.get("match", "all") not in {"all", "any"} or not anchors:
                    raise ValueError(f"RAG case {case['id']} has an invalid gold_evidence group")
                if not all(anchor.casefold() in documents_by_alias[alias].casefold() for anchor in anchors):
                    raise ValueError(f"RAG case {case['id']} has a gold anchor absent from its document")
        else:
            anchors = [str(item) for item in case.get("gold_content_anchors") or []]
            if gold_aliases and not anchors:
                raise ValueError(f"RAG case {case['id']} requires gold content anchors")
            if anchors and not all(
                any(anchor.casefold() in documents_by_alias[alias].casefold() for alias in gold_aliases)
                for anchor in anchors
            ):
                raise ValueError(f"RAG case {case['id']} gold anchors do not match a gold document")
        if not gold_aliases and not bool((case.get("expected") or {}).get("abstain")):
            raise ValueError(f"RAG case {case['id']} without gold evidence must require abstention")


def _validate_case_rubric(case: dict[str, Any]) -> None:
    if not str(case.get("query") or "").strip():
        raise ValueError(f"Experiment case {case.get('id', '<unknown>')} has an empty query")
    expected = dict(case.get("expected") or {})
    term_groups = list(expected.get("required_term_groups") or [])
    if term_groups and any(
        not isinstance(group, list)
        or not group
        or any(not str(candidate).strip() for candidate in group)
        for group in term_groups
    ):
        raise ValueError(
            f"Experiment case {case.get('id', '<unknown>')} has invalid required_term_groups"
        )
    has_positive_rubric = bool(
        expected.get("accepted_answers")
        or expected.get("required_terms")
        or term_groups
    )
    if not has_positive_rubric:
        raise ValueError(f"Experiment case {case.get('id', '<unknown>')} has no answer rubric")
    if bool(expected.get("abstain")) and not expected.get("accepted_answers"):
        raise ValueError(f"Abstention case {case.get('id', '<unknown>')} requires accepted_answers")


def _validate_language(case: dict[str, Any]) -> None:
    if case.get("language") not in {"en", "zh"}:
        raise ValueError(f"Experiment case {case.get('id', '<unknown>')} requires language=en or zh")


def _require_fields(section: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in section or section[field] in (None, "")]
    if missing:
        raise ValueError(f"Experiment spec section {label} is missing frozen fields: {', '.join(missing)}")
