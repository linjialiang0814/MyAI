# Release Notes

## Current Local Product Baseline

Date: 2026-08-17

Version marker:

```text
0.11.0-local
```

MyAI is currently a local-first personal agent workbench.

This baseline focuses on:

- reliable local startup
- local SQLite/auth mode in Java plus a separate Python runtime SQLite database
- chat cockpit
- governed memory
- citation-aware knowledge base
- observable task runtime
- MCP-style read-only connectors
- unified observability
- privacy redaction for routine API/UI views
- product-oriented documentation
- loopback-safe local open-source model provider support
- reproducible memory and RAG graduation-design experiments
- reviewed, checksummed formal evidence artifacts
- one lifespan-owned Python service graph with dependency injection
- durable AgentRun/TaskRun relationships and idempotency state
- coalesced background memory maintenance and shared resilience/error contracts

## Highlights

### Stage 4 Portable Local App Demo

- Added a Windows portable ZIP with verified JAR/Python payload, synthetic demo data,
  per-file manifest hashes, and a required external ZIP checksum.
- Added safe setup, human/JSON doctor, start, stop, status, and reset controls. Mutable
  data stays under the extracted package, process identity is package-scoped, and reset
  rejects filesystem links.
- Isolated inherited provider, Spring, Python-path, and JVM option variables before
  binding both services to loopback.
- Externalized the workbench stylesheet and split its JavaScript into seven ordered
  responsibility-based files without introducing an npm build or changing API behavior.
- Added a Windows GitHub Actions workflow for static gates, Python 3.12, Java 17
  `verify`, portable artifact verification, and extracted-package safety controls.
  Local parity gates are recorded as passing; remote status must be checked against
  the exact GitHub commit and is not implied by this document.
- Included a synthetic knowledge document and enabled only a demo-scoped built-in
  MCP-style read-only filesystem connector. A real standards-compliant MCP client is
  intentionally deferred beyond the selected local App Demo scope.

This is a transferable App Demo, not an MSI, signed publisher release, bundled runtime,
offline model package, or public deployment.

### Stage 2 Core Engineering Evidence

- Added a generic OpenAI-compatible provider for Ollama, llama.cpp, vLLM-style endpoints, and other compatible local runtimes.
- Added strict fail-closed real embedding, provider health/status, role-specific configuration, deterministic generation controls, and resource-safe client shutdown.
- Froze Ollama `0.32.6`, Qwen2.5 1.5B Q4_K_M, BGE-M3, model digests, hardware, dependencies, data, seed, and context settings.
- Added controlled `none/basic/governed` memory ablations and `vector/hybrid/hybrid_rerank` RAG ablations.
- Added balanced technical repeats, paired unique-case bootstrap intervals, citation/support separation, latency/resource/failure metrics, checksummed LF artifacts, and strict formal-artifact gates.
- Completed the reviewed 432-attempt run under `reports/experiments/thesis-core-v1-r2-final/` with 0 failures.
- Added `docs/STAGE2_FORMAL_EXPERIMENT_REVIEW.md` with supported claims, negative findings, and interpretation limits.

Stage 2 is complete as a reproducible graduation-design engineering evidence
baseline. It is not a thesis manuscript or paper. The frozen artifacts can support a
later paper, but current conclusions apply only to the recorded models, embeddings,
hardware, and synthetic datasets.

### Stage 3 Unified Runtime MVP

- Replaced Python import-time service singletons with one FastAPI lifespan-owned
  `AppRuntime` and dependency-injected Agent, Memory, Knowledge, and Task services.
- Added a separate Python SQLite repository for AgentRun, AgentStep, TaskRun, task
  events, restart recovery, and idempotency records.
- Established `user -> conversation -> agent_run -> task_run` links. Java remains
  authoritative for authentication, users, conversation ownership, and chat messages;
  Python stores only Java-validated logical references.
- Moved consolidation and decay execution to a bounded, process-local, coalescing
  maintenance pool with two workers by default and a 60-second cooperative batch
  deadline.
- Added non-blocking foreground/maintenance memory-lock admission. Contention is
  recorded as deferred/skipped rather than making chat wait behind maintenance.
- Added shared cooperative deadlines, circuit breakers, bounded backoff, idempotency,
  structured safe errors, and correlation identifiers.
- Added task admission backpressure, idempotent replay before capacity rejection,
  concurrent knowledge-index protection, and safe close retry when a task/tool or
  maintenance worker is still running.
- Added focused lifecycle, persistence, relationship, API compatibility, concurrency,
  deadline, backpressure, recovery, and shutdown validation.

This release is a single-Python-runtime MVP. Deadlines cannot forcibly stop arbitrary
blocking threads. Maintenance and foreground memory work still contend for a per-user
lock, but use non-blocking admission; skipped foreground memory work is not durably
replayed. One hung batch can still consume a worker beyond its cooperative deadline,
and enough hangs can exhaust the pool. Task and maintenance queues are not durable.
Python runtime SQLite is unencrypted, and deleting a Java conversation does not
cascade to Python runtime rows. Synchronous `POST /task` HTTP 200 carries a business
result and may describe failure, so clients must inspect the response status fields.

### Product Experience

- refreshed login/register pages
- Chat Page 2.0 agent cockpit
- unified settings and system health center
- first-run diagnostics through startup script
- guided demo scenarios
- screen-level polish for memory, knowledge, task, and observability workbenches

### Memory

- slot registry and policy tuning
- eval fixture and calibration report
- LLM extraction path
- temporal memory modeling
- correction-aware updates
- edit-before-accept
- dedup merge audit
- retrieval explanation
- multi-candidate extraction
- confidence-aware pending behavior
- consolidation summary and evidence chains
- user memory control MVP
- Python Agent-managed memory workflows

### Knowledge

- ingestion metadata and reports
- citation-first query results
- hybrid retrieval baseline
- reranking and final selection separation
- structured document profile
- single-document QA
- chat answer citations
- maintenance workflow
- eval/report support
- knowledge-aware task workflow integration

### Task Runtime

- state machine
- runtime timeline and trace unification
- tool policy and permission governance
- retry/timeout/recovery
- background task mode
- task workbench UI
- memory-aware planning
- outcome memory
- workflow registry
- runtime eval and reports

### MCP-Style Tool Ecosystem

- bridge MVP
- unified tool registry
- policy/permission mapping
- execution events and trace
- read-only filesystem connector
- read-only git connector
- connector settings and health UI
- eval fixture/report
- workflow integration

### Observability

- unified evaluation registry
- local eval runner
- metrics snapshot and runtime counters
- normalized trace/events
- observability workbench
- eval history persistence
- quality gates and maintenance reports
- production-oriented follow-up baseline

### Privacy And Safety

- documented local data inventory
- default path/secret-like field redaction for task and observability APIs
- visible privacy boundary in frontend health/tool/observability views
- explicit `include_sensitive=true` local troubleshooting path

## Recommended Smoke Test

```powershell
.\start-myai.cmd doctor -LocalMode
.\start-myai.cmd -LocalMode
```

Then verify:

- Chat page loads
- Demo workspace opens
- Settings health center loads
- Knowledge file list loads
- Task tool catalog loads
- Observability summary loads

## Verification Commands

```powershell
cd myai-python-agent
.\.venv\Scripts\python.exe -m unittest
```

```powershell
cd myai-java-service
$env:JAVA_HOME='<path-to-jdk-17-or-newer>'
.\mvnw.cmd -q test
```

## Release Status

`0.11.0-local` is a packaged, checksummed Windows App Demo baseline for the
documented loopback-only, single-Python-runtime scope. The audited checkpoint is
published as the unsigned GitHub prerelease `v0.11.0-local` with a Windows ZIP and
SHA-256 file. It is not a native installer, bundled runtime/model distribution, or
public deployment.

Latest recorded local source-tree checkpoint:

- Python full regression: **309/309 passed**.
- Java Stage 4 full verify: **26 tests, 0 failures, 0 errors, 1 skipped**.
- root static quality gate, documentation links, and diff-format check: **passed**.
- Stage 4 portable build, checksum/manifest verification, extracted controls, clean
  setup, local API/UI smoke, stop, and reset: **passed**.

The GitHub Actions workflow is committed as a reproducible remote gate, but this
release note does not claim that the current unpublished commit has passed remotely.
Use the Actions result attached to the exact pushed commit as the remote source of
truth.

The public checkpoint uses sanitized, functionally equivalent source history after an
older local configuration credential incident. Stage 2 formal artifacts keep their
original run commit SHA and checksums unchanged. The sanitized public SHA must not be
described as a rerun of the frozen Ollama 0.32.6 experiment; strict SHA alignment
requires a new full run and a separate evidence directory.

Before sharing a local snapshot, run:

```powershell
.\release-smoke.cmd -JavaHome "<path-to-jdk-17-or-newer>"
```

Use:

- [Release Checklist](RELEASE_CHECKLIST.md)
- [Artifact Cleanup](ARTIFACT_CLEANUP.md)
- [Project Final Audit](PROJECT_FINAL_AUDIT.md)
