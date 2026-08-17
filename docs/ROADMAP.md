# MyAI Evolution Roadmap

## Background

MyAI originated as an undergraduate graduation project. Its core design,
implementation, experimental evidence, unified-runtime, and local App Demo scope are
now complete; future work can treat it as a longer-term personal agent platform
rather than extending the graduation checkpoint without a product decision.

The current system already includes:

- Java service layer for users, pages, sessions, chat history, and Python service proxying.
- Python agent layer for chat, short-term context, long-term memory, personal knowledge base, RAG, task planning, and tool execution.
- SQLite/local authentication as the recommended single-user path, with optional
  MySQL mode for users and conversations.
- A separate Python SQLite runtime database plus ChromaDB-based vector stores for
  memory and knowledge chunks.

## North Star

Build MyAI into a personal intelligent agent that can understand user context, manage memory transparently, use knowledge with citations, plan and execute recoverable tasks, and expose its reasoning process through an inspectable execution trace.

## Phase 1: Agent Runtime And Execution Trace

Goal: turn the current linear chat pipeline into an observable agent run.

Status: completed and closed.

Closeout: `docs/PHASE1_AGENT_TRACE_CLOSEOUT.md`

Planned capabilities:

- Create an `AgentRun` concept for each assistant execution.
- Create `AgentStep` records for task detection, memory write, memory retrieval, knowledge retrieval, maintenance, prompt construction, LLM generation, and context update.
- Return trace metadata from the Python chat API without breaking the existing `reply` field.
- Let the Java service receive and preserve the trace payload.
- Display the trace on the chat page as an expandable execution timeline.

Completed implementation scope:

- A Python trace object returned by the chat API and durably represented through the
  later Stage 3 AgentRun/AgentStep runtime repository.
- Chat response includes `run_id`, `status`, `started_at`, `finished_at`, and `steps`.
- Java DTO accepts the new fields so API compatibility is ready.
- Java service preserves and forwards the trace payload.
- Chat page renders the trace as a collapsible "本轮执行轨迹" panel.
- Stage 3 subsequently added Python SQLite persistence for AgentRun, AgentStep,
  TaskRun, events, restart recovery, and idempotency.

Deferred intentionally:

- Token usage, provider metadata, and deeper latency analytics.
- Trace search, filtering, and evaluation dashboards.

These items belong to Phase 6 unless a future phase needs a smaller subset earlier.

## Phase 2: Memory Governance 2.0

Goal: move from storing memory to managing memory responsibly.

Status: baseline completed.

Execution plan: `docs/PHASE2_MEMORY_GOVERNANCE_PLAN.md`

Planned capabilities:

- Add memory source metadata: conversation id, message id if available, and extraction reason.
- Add confidence scores for extracted memories.
- Add memory scopes: global, conversation, topic, or task.
- Add a memory confirmation queue for uncertain or sensitive memories.
- Add memory consolidation that periodically merges fragmented memories into stable profile entries.
- Show memory citations in answers when retrieved memories influence the response.

## Phase 3: Recoverable Task Workflow

Goal: evolve tool calling into durable agent workflows.

Status: baseline completed.

Execution plan: `docs/PHASE3_AGENT_RUNTIME_TASK_PLAN.md`

Planned capabilities:

- Persist task runs and step results.
- Support long-running asynchronous tasks.
- Add human confirmation before sensitive actions.
- Support retry, skip, edit parameters, and resume.
- Add a task execution page with live status and history.

## Phase 4: Knowledge Workbench

Goal: make the knowledge base useful for real personal research and document work.

Status: baseline completed and closed.

Execution plan: `docs/PHASE4_KNOWLEDGE_BASE_PLAN.md`

Closeout: `docs/PHASE4_KNOWLEDGE_CLOSEOUT.md`

Planned capabilities:

- Hybrid retrieval: vector search plus keyword search.
- Reranking after first-stage retrieval.
- Answer citations with document name, chunk, and page when available.
- Document-focused QA mode.
- Knowledge conflict detection across documents.
- Structured summaries for uploaded files.

## Phase 5: MCP Tool Ecosystem

Goal: make tool integration extensible through a standard protocol.

Status: baseline completed and closed.

Execution plan: `docs/PHASE5_MCP_TOOL_ECOSYSTEM_PLAN.md`

Closeout: `docs/PHASE5_MCP_TOOL_ECOSYSTEM_CLOSEOUT.md`

Planned capabilities:

- Add an MCP bridge in the Python agent layer.
- Register MCP tools alongside local Python tools.
- Add tool permission metadata and confirmation policies.
- Start with low-risk tools, then expand to filesystem, browser, calendar, GitHub, and database tools.

## Phase 6: Observability And Evaluation

Goal: make quality, latency, and regressions measurable.

Status: baseline completed and closed.

Execution plan: `docs/PHASE6_OBSERVABILITY_EVALUATION_PLAN.md`

Closeout: `docs/PHASE6_OBSERVABILITY_EVALUATION_CLOSEOUT.md`

Planned capabilities:

- Record LLM provider, model id, latency, token usage when available, and error details.
- Record tool latency and failure rate.
- Record RAG hit quality and memory hit usage.
- Add regression datasets for chat, memory, RAG, and task workflows.
- Add a local evaluation command for repeated quality checks.

Completed implementation scope:

- Unified evaluation registry and local runner.
- Runtime metrics snapshot and normalized events.
- Observability workbench UI.
- Persisted eval run history with restart recovery and deltas.
- Local quality gates and maintenance reports.

Deferred intentionally:

- OpenTelemetry and Prometheus exports.
- Full persisted normalized event store.
- Distributed trace ids across Java/Python.
- Alerting and scheduled monitors.
- Privacy/redaction controls for exported observability data.

These items belong to production hardening after the local observability MVP.

## Phase 7: Productization And Release Hardening

Goal: make MyAI easier to install, configure, trust, demonstrate, and maintain as a real personal agent product.

Status: baseline completed.

Execution plan: `docs/PHASE7_PRODUCTIZATION_PLAN.md`
Step 0 frontend refresh: `docs/PHASE7_STEP0_FRONTEND_REFRESH.md`

Planned capabilities:

- Chat Page 2.0 as the main agent cockpit.
- First-run setup and local environment checks.
- One-command startup with health diagnosis.
- Unified settings and health page.
- Demo scenarios covering memory, knowledge, tasks, MCP, and observability.
- Privacy and safety review for stored memory, traces, connector settings, and telemetry.
- Release-quality documentation, troubleshooting, and development workflow.

## Phase 8: Stabilization, Testing And Dogfooding

Goal: make MyAI reliable and comfortable enough for repeated daily local use before choosing a deployment direction.

Status: in progress. 8.1 dogfooding loop, 8.2 local product-path smoke, and the cross-cutting safe/reproducible baseline completed.

Execution plan: `docs/PHASE8_STABILIZATION_DOGFOODING_PLAN.md`
Dogfooding log: `docs/DOGFOODING_LOG.md`
Pain point tracker: `docs/PAIN_POINT_TRACKER.md`
Upgrade Stage 1 baseline: `docs/SAFE_REPRODUCIBLE_BASELINE_PLAN.md`

### Cross-Cutting Upgrade Stage 1: Safe And Reproducible Baseline

Status: completed on 2026-07-13.

This baseline was inserted before further Phase 8 feature and UX work without renumbering the existing historical plan. It establishes:

- loopback-only Java defaults
- non-echoing Stub fallback
- opt-in filesystem MCP with sensitive-path rejection
- task-run owner checks across Java and Python
- isolated Chroma, knowledge, and memory-settings test storage
- full-suite release smoke and a secret-free repository checkpoint gate

Planned capabilities:

- Record real usage sessions and pain points. Baseline completed in 8.1.
- Expand release smoke into local product-path smoke checks. Baseline completed in 8.2.
- Fix UI/UX friction based on repeated observed issues.
- Turn real-use regressions into tests or eval fixtures.
- Measure startup and key workflow latency.
- Add local data inventory and cleanup MVP.
- Produce a deployment readiness assessment before any public deployment.

### Cross-Cutting Upgrade Stage 2: Reproducible Core Evidence

Status: completed and evidence-checkpointed on 2026-08-10.

Execution plan: `docs/UPGRADE_STAGE2_THESIS_EVIDENCE_PLAN.md`

Formal review: `docs/STAGE2_FORMAL_EXPERIMENT_REVIEW.md`

Evidence: `reports/experiments/thesis-core-v1-r2-final/`

This is a completed graduation-design engineering evidence baseline, not a thesis
manuscript or paper. It can become source material for a later paper after broader
datasets, baselines, and external-validity work.

This stage adds:

- a loopback-safe OpenAI-compatible provider for local open-source runtimes
- a frozen Ollama/Qwen2.5/BGE-M3 model contract and recorded hardware baseline
- paired `none/basic/governed` memory ablations
- paired `vector/hybrid/hybrid_rerank` RAG ablations
- gold citation matching instead of citation-field completeness
- accuracy, evidence, latency, resource, and failure-rate artifacts with checksums
- a strict distinction between exploratory pilot runs and accepted formal engineering
  evidence

### Cross-Cutting Upgrade Stage 3: Unified Runtime And Durable Runs

Status: single-Python-runtime MVP completed and checkpoint-validated on 2026-08-11.

Execution plan: `docs/UPGRADE_STAGE3_UNIFIED_RUNTIME_PLAN.md`

Closeout: `docs/UPGRADE_STAGE3_UNIFIED_RUNTIME_CLOSEOUT.md`

This stage adds:

- one FastAPI lifespan-owned dependency graph for Agent, Memory, Knowledge, and Task in
  the supported single Python application worker
- a separate Python SQLite runtime database for AgentRun/TaskRun and idempotency state
- the logical `user -> conversation -> agent_run -> task_run` relationship while Java
  remains authoritative for users and conversations
- restart recovery that fails interrupted work without replaying side effects
- process-local, coalesced consolidation/decay execution outside the synchronous chat
  call sequence, with non-blocking foreground/maintenance lock admission, two workers
  by default, and a cooperative per-batch deadline
- shared timeout, circuit-breaker, bounded backoff, idempotency, and API error contracts

Deferred production hardening includes durable maintenance/task queues, cross-process
leases, hard cancellation for blocking dependencies, replay of deferred foreground
memory work, SQLite encryption and retention/purge workflows, and Java-to-Python
cascade deletion.

### Cross-Cutting Upgrade Stage 4: Deliverable Local App Demo

Status: completed for the selected portable Windows App Demo scope on 2026-08-12.

Plan: `docs/UPGRADE_STAGE4_LOCAL_APP_DEMO_PLAN.md`

Portable baseline closeout: `docs/UPGRADE_STAGE4_PORTABLE_APP_BASELINE_CLOSEOUT.md`

This checkpoint adds:

- a checksummed, allowlisted Windows ZIP with setup/doctor/start/stop/status/reset;
- package-local configuration, data, runtime, logs, Python environment, and process ownership;
- frontend CSS/JavaScript modularization without changing the Thymeleaf architecture;
- a Windows GitHub Actions workflow for static gates, Python, Java, package
  verification, and portable safety controls;
- synthetic demo material and a demo-only MCP-style filesystem boundary.

One real standards-compliant read-only MCP Server connection is an optional future
extension, not an unfinished acceptance item for the chosen App Demo. MSI/MSIX,
bundled runtimes/models, public deployment, and multi-instance operation also stay
deferred.

## Phase 9: Health Module And Real Model Reliability

Goal: make real-model availability explicit instead of hidden behind Stub fallback.

Status: 9.1 real model health probe MVP completed; advanced reliability metrics remain
planned.

Execution plan: `docs/PHASE9_HEALTH_MODULE_PLAN.md`

Planned capabilities:

- Manual real-model health probe for Chat, Task, Memory, and Embedding.
- Error classification for provider failures.
- Latest probe visibility in Settings > System Health.
- Runtime counters for real-provider attempts, successes, fallback events, and latency.
- Optional strict real-model mode for deployment readiness checks.
