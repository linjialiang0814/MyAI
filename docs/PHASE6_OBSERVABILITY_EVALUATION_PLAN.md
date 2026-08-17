# Phase 6 Observability And Evaluation Plan

## Goal

Make MyAI measurable as an agent platform: quality, latency, failures, retrieval behavior, tool behavior, connector health, and regressions should be visible through repeatable reports and eventually through a unified dashboard.

Phase 6 is not just "more logs". The goal is to turn existing traces and eval fixtures into operational signals that can guide real maintenance and production-like iteration.

## Current Foundation

The previous phases already created useful observability primitives:

- Phase 1: chat execution trace.
- Phase 2: memory governance eval, calibration report, retrieval explanations, citations, maintenance metadata.
- Phase 3: task runtime events, task reports, retry/timeout/recovery metadata, workflow registry.
- Phase 4: knowledge eval/report, citation-first retrieval, maintenance reports.
- Phase 5: MCP connector inspection, MCP execution events, connector health, MCP eval/report.

Phase 6 should unify these rather than replace them.

## 6.1 Unified Evaluation Registry

Purpose: make every eval/report discoverable through one stable interface.

Status: baseline implemented.

Add:

- Python-side eval registry.
- Registry entries for:
  - memory governance report
  - memory calibration report
  - task runtime report
  - knowledge eval report
  - MCP eval report
- Common report metadata:
  - id
  - name
  - domain
  - command/module
  - strict support
  - last run placeholder
  - coverage summary placeholder

Acceptance criteria:

- `GET /eval/reports` or task/admin tool can list available reports.
- Each report has stable id and description.
- Existing individual report runners still work.

Implemented baseline:

- Added Python evaluation registry:
  - `app.evaluation.registry`
- Registered reports:
  - `memory_governance`
  - `memory_llm_calibration`
  - `task_runtime`
  - `knowledge_retrieval`
  - `mcp_tool_ecosystem`
- Common report metadata includes:
  - report id
  - name
  - domain
  - description
  - module
  - command
  - fixture path
  - strict support
  - supported formats
  - deterministic/live-LLM flags
  - coverage summary
  - last-run placeholder
- Added Python API endpoints:
  - `GET /eval/reports`
  - `GET /eval/reports/{report_id}`
- Existing individual report runners remain unchanged.
- Added regression coverage for registry discovery and API lookup.

## 6.2 Unified Local Eval Runner

Purpose: run all or selected eval suites with one command.

Status: baseline implemented.

Add:

- `python -m app.evaluation.run --suite all --format markdown --strict`
- Selective suites:
  - `memory`
  - `task`
  - `knowledge`
  - `mcp`
- Common normalized result:
  - total
  - passed
  - failed
  - pass rate
  - duration
  - suite status
  - report path/content

Acceptance criteria:

- All current eval fixtures can be run from one command.
- Strict mode exits non-zero when any suite fails.
- Markdown summary links or embeds per-suite summaries.

Implemented baseline:

- Added unified local eval runner:
  - `app.evaluation.run`
- Supported command:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --strict`
- Supported suite selection:
  - `all`
  - `memory`
  - `task`
  - `knowledge`
  - `mcp`
  - individual report id
- Default `all` skips live-LLM reports for deterministic local runs.
- Live reports can be included with:
  - `--include-live`
- Normalized result includes:
  - report count
  - passed/failed/skipped reports
  - total/passed/failed cases
  - pass rate
  - duration
  - suite status
  - per-report rendered content
- Markdown and JSON output are supported.
- Strict mode exits non-zero when any selected report fails.
- Added regression coverage for all deterministic suites, domain filtering, report-id filtering, and Markdown rendering.

## 6.3 Metrics Snapshot And Runtime Counters

Purpose: expose lightweight operational metrics without introducing heavy infrastructure.

Status: baseline implemented.

Add in-memory or SQLite-backed snapshot for:

- chat runs
- task runs
- tool calls
- MCP calls
- memory writes/retrievals
- knowledge queries
- eval runs

Metrics:

- count
- success/failure count
- average latency
- recent error categories
- top tools/connectors/workflows
- pass rate for latest evals

Acceptance criteria:

- `GET /observability/summary` returns a compact metrics snapshot.
- Snapshot can be rendered by Java frontend without schema-specific DTO churn.
- Metrics are useful after local quick-start without external services.

Implemented baseline:

- Added lightweight in-memory observability store:
  - `app.observability.store`
- Unified eval runner now records eval run summaries.
- Added eval run API:
  - `POST /eval/runs?suite=...`
  - `GET /eval/runs`
- Added observability summary API:
  - `GET /observability/summary`
- Summary currently includes:
  - task run count and status counts
  - planner counters
  - tool call/success/latency stats
  - tool failure list
  - connector health summary
  - latest eval run and eval run counts
- Persistence is intentionally deferred to 6.6 Evaluation History Persistence.
- Added regression coverage for eval run recording and observability summary.

## 6.4 Trace And Event Normalization

Purpose: make chat trace, task runtime events, MCP events, memory retrieval, and knowledge retrieval easier to compare.

Status: baseline implemented.

Add a normalized event shape:

- source
- domain
- type
- status
- started/finished/latency where available
- user/conversation/task ids where available
- step/tool/connector ids where available
- error category
- citations/evidence count

Acceptance criteria:

- Existing task events can be converted to normalized events.
- Chat trace steps can be converted to normalized events.
- The frontend can render a unified timeline without knowing every backend-specific field.

Implemented baseline:

- Added normalized event conversion module:
  - `app.observability.events`
- Added conversion for:
  - task runtime events
  - MCP call events
  - memory retrieval task events
  - chat/agent trace steps
  - knowledge retrieval trace steps
- Normalized event shape includes:
  - event id
  - source
  - domain
  - type
  - status
  - started/finished time
  - latency
  - user/conversation/run/task/step ids
  - tool name
  - connector id
  - error/error category
  - evidence count
  - message
  - original metadata
- `GET /observability/summary` now includes recent normalized events.
- Added event listing endpoint:
  - `GET /observability/events`
- Added regression coverage for task event normalization, chat trace normalization, and events endpoint.

## 6.5 Observability Workbench UI

Purpose: give users a single place to inspect health, reports, and recent failures.

Status: baseline implemented.

Add frontend page/section for:

- eval report list
- run summary cards
- latest pass/fail status
- runtime metrics
- recent task/tool/MCP failures
- connector health
- links to task timeline and memory/knowledge reports

Acceptance criteria:

- User can see whether the system is healthy without running commands.
- User can identify the failing domain quickly.
- UI stays operational and compact, not a decorative dashboard.

Implemented baseline:

- Added Java proxy service for observability and eval APIs:
  - `PythonObservabilityService`
- Added Java proxy controllers:
  - `GET /observability/summary`
  - `GET /observability/events`
  - `GET /eval/reports`
  - `GET /eval/runs`
  - `POST /eval/runs`
- Added frontend sidebar tab:
  - `观测`
- Added observability workbench section showing:
  - task runtime metrics
  - planner counters
  - connector health summary
  - latest eval status
  - eval report catalog
  - recent normalized events
- Added frontend actions:
  - refresh observability workbench
  - run MCP eval
  - run all deterministic evals
- UI uses existing task/workbench visual primitives and avoids a decorative dashboard layout.

## 6.6 Evaluation History Persistence

Purpose: compare runs over time.

Status: baseline implemented.

Add local persistence for eval run records:

- suite id
- started/finished time
- status
- pass/fail counts
- duration
- report format/content or report file path
- git commit/hash when available

Acceptance criteria:

- Last N eval runs can be listed.
- Latest report is available after service restart.
- Regression deltas can be computed later.

Implemented baseline:

- Extended `app.observability.store` from in-memory-only history to local JSONL-backed history.
- Eval run records are appended to:
  - `myai-python-agent/.runtime/observability/eval_runs.jsonl`
- The store reloads the latest retained records on startup, so:
  - `GET /eval/runs`
  - `GET /observability/summary`
  can still show recent reports after service restart.
- `eval_summary()` now includes:
  - latest run
  - previous run
  - storage metadata
  - simple latest-vs-previous delta fields for pass rate, failures, total cases, duration, and status change.
- Persistence remains local-first and dependency-free.
- `.runtime/` is ignored by git.
- Added regression coverage for persisted reload and delta calculation.

Deferred:

- Git commit/hash capture.
- Full report artifact path/content retention.
- Regression gate thresholds based on historical deltas.

## 6.7 Quality Gates And Maintenance Reports

Purpose: turn reports into engineering guardrails.

Status: baseline implemented.

Add:

- quality gate config
- minimum pass rate per suite
- max latency threshold per suite/tool where meaningful
- connector health requirement
- optional `--ci` style command

Acceptance criteria:

- Local quality gate can fail fast before larger changes.
- Gate output explains which suite/domain failed and why.

Implemented baseline:

- Added reusable quality gate module:
  - `app.evaluation.quality`
- Default quality gate policy:
  - suite status must be passed
  - suite pass rate must be 100%
  - failed reports must be 0
  - failed cases must be 0
  - failed case delta must not increase
  - pass rate must not drop from the previous persisted run
- Gate config supports:
  - global minimum pass rate
  - maximum failed reports
  - maximum failed cases
  - maximum failed case delta
  - maximum pass-rate drop
  - per-report or per-domain minimum pass rates
- Added CLI gate mode:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --quality-gate --strict`
- Added Python API endpoints:
  - `GET /eval/gates/config`
  - `POST /eval/gates/run`
  - `POST /eval/maintenance-report`
- Maintenance report includes:
  - eval summary
  - quality gate checks
  - persisted history summary
  - actionable maintenance recommendations
- Added regression coverage for:
  - passing deterministic gate
  - threshold failure explanations
  - maintenance report API structure

Deferred:

- External config file for gate thresholds.
- Java frontend buttons/cards for quality gate and maintenance report.
- CI profile with stricter command presets.
- Connector health requirements folded directly into gate checks.

## 6.8 Production-Oriented Follow-Up

Purpose: define what would be needed beyond local MVP.

Status: baseline planned and closed.

Deferred until after MVP:

- OpenTelemetry integration.
- Prometheus/Grafana metrics.
- distributed trace ids across Java/Python.
- persisted event store for all traces.
- alerting/notifications.
- per-user privacy controls for observability data.

Production follow-up baseline:

- Phase 6 should close at the local observability/evaluation MVP boundary.
- The current system already has:
  - unified eval registry
  - unified local eval runner
  - runtime metrics snapshot
  - normalized event shape
  - observability workbench UI
  - persisted eval history
  - local quality gates and maintenance reports
- Production-oriented work should become a later hardening/productization stream, not more Phase 6 scope.

Recommended production hardening sequence:

1. Add cross-service trace ids across Java and Python.
2. Persist normalized events beyond task/eval summaries.
3. Add privacy controls and redaction for observability payloads.
4. Export metrics through OpenTelemetry or Prometheus-compatible adapters.
5. Add alerting only after stable thresholds and real usage signals exist.
6. Add CI profile once the local quality gate has been used during several development cycles.

Closeout:

- Phase 6 can be closed as baseline completed.
- Closeout document:
  - `docs/PHASE6_OBSERVABILITY_EVALUATION_CLOSEOUT.md`

## MVP Recommendation

Start with **6.1 Unified Evaluation Registry**.

Why:

- Existing phases already have several independent reports.
- A registry is small, low-risk, and immediately useful.
- It creates a stable base for CLI runner, API endpoint, frontend report list, and later history persistence.
- It avoids jumping straight to a dashboard before the report model is unified.

Suggested implementation order:

1. Add Python eval registry model and default registry.
2. Register task, knowledge, memory, and MCP reports.
3. Add a lightweight API endpoint or admin task tool operation to inspect report metadata.
4. Add tests for report discovery.
5. Update execution log and roadmap.

## Engineering Principles

- Prefer structured reports over log scraping.
- Keep local-first operation; no external observability stack required for MVP.
- Preserve existing individual report commands.
- Avoid collecting sensitive content unless explicitly needed for debugging.
- Make failures actionable: domain, case id, expected/actual, and next diagnostic step.
- Treat latency and reliability as first-class quality signals, not only correctness.

## Open Questions

- Should eval history persist in SQLite, JSONL files, or both?
- Should report execution be synchronous initially or run as background task workflow?
- Should Java trigger eval runs, or only display Python-generated report history?
- How much trace content should be shown by default to avoid leaking memory/knowledge contents?
- Should Phase 6 include first CI-like quality gate, or leave that for a later release hardening phase?
