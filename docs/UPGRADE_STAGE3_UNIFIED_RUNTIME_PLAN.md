# Upgrade Stage 3: Unified Runtime And Durable Runs

Status: single-Python-runtime MVP implementation and focused review completed on
2026-08-11. The final integrated Python, Java, and release-smoke result is owned by
the root checkpoint and remains to be recorded.

Release target: `0.10.0-local`

Closeout: [Stage 3 Unified Runtime MVP Closeout](UPGRADE_STAGE3_UNIFIED_RUNTIME_CLOSEOUT.md)

## 1. Objective

Stage 3 turns the Python agent layer from a set of import-time singletons into one
explicit, lifespan-owned application runtime. The delivered target is a locally
deployable, restart-aware MVP for one Python application worker, not a distributed
workflow engine.

The implementation provides:

- one FastAPI lifespan-owned `AppRuntime`
- dependency-injected Memory, Knowledge, Task, and Agent services
- SQLite persistence for AgentRun, TaskRun, events, and idempotency state
- the logical chain `user -> conversation -> agent_run -> task_run`
- consolidation and decay execution outside the synchronous chat call sequence
- consistent deadline, circuit-breaker, backoff, idempotency, and error semantics

## 2. Stage 2 Entry Decision

Stage 2 is complete as a reproducible graduation-design engineering evidence
baseline. It includes a real local open-source model provider, frozen
model/embedding/data/hardware contracts, paired memory and RAG ablations, resource
and failure measurements, and a checksummed final artifact.

Stage 2 is not a thesis manuscript and the project does not currently claim to have
produced a paper. Its measured conclusions are deliberately narrow:

- governed memory mainly improves safe abstention and forbidden-evidence isolation
- all three RAG variants saturate Support Hit@3 on the frozen dataset
- the evidence does not establish that hybrid retrieval or reranking is universally
  better than vector retrieval

The artifact can support a later paper after broader datasets, stronger baselines,
and additional external-validity work. A manuscript was not a prerequisite for
starting Stage 3.

## 3. Architecture And Authority

```text
Java service (authority)                 Python service (one AppRuntime)

user -> conversation -> chat message     AgentService
          |                              |-- MemoryService
          +---- Java-validated IDs ----> |-- KnowledgeService
                                         |-- TaskService
                                         |-- AgentRunStore
                                         `-- TaskRunStore

Logical runtime chain:
user -> conversation -> agent_run -> task_run
```

Java remains authoritative for authentication, user ownership, conversations, and
chat messages. Python stores Java-validated identifiers as logical references in its
own `.runtime/runtime.db`. Java and Python use separate databases and must not share a
SQLite file. Python does not independently recreate the Java ownership model.

## 4. Data Contract

The Python SQLite schema stores runtime data:

- `schema_migrations`
- `agent_runs` and `agent_steps`
- `task_runs` and task events/step snapshots
- `idempotency_records`

Connections are short-lived and use foreign keys, WAL, `busy_timeout`, and
`synchronous=NORMAL`. Transactions do not span LLM, embedding, retrieval, or tool
execution.

The runtime persists operational task content, assistant responses needed for
idempotent replay, and bounded structured status snapshots. Common secret-like
values, absolute local paths, large body fields, and raw evidence bodies are redacted
or replaced with references before persistence. The database is local and
unencrypted; it must be treated as sensitive application data.

## 5. Runtime And Failure Semantics

- Importing `app.main` is side-effect free; resources are created by FastAPI lifespan.
- API routes resolve the shared service graph through FastAPI dependencies.
- Shutdown stops admission, waits for task/tool and maintenance workers, and only then
  releases providers and repositories. If a worker does not stop within the budget,
  shutdown reports incomplete and keeps shared dependencies open.
- Interrupted non-terminal runs recover to `RUNTIME_RESTART`; potentially
  side-effecting tools are not automatically replayed.
- Deadlines are cooperative caller-side budgets. They bound waits and are checked at
  orchestration boundaries, but they cannot forcibly terminate arbitrary blocking
  Python code or prove that a timed-out thread stopped.
- Retries use bounded exponential backoff and are allowed only for classified
  transient failures on operations declared safe/read-only/idempotent.
- Same user/scope/idempotency key plus the same request hash replays the existing
  resource; a different request hash is a conflict. Existing background runs can be
  replayed even while admission backpressure rejects new work.
- Public failures use one safe structured model with code, message, retryability,
  operation, and correlation/run identifier.
- Synchronous `POST /task` uses HTTP 200 for a completed business-result envelope,
  including task planning/tool failure. Clients must inspect `status`, `success`,
  `error_code`, and `retryable`; transport status alone is not task success.

## 6. Memory Maintenance

Chat no longer invokes consolidation and decay synchronously. It schedules a bounded,
coalesced per-user request, and a lifespan-owned worker pool executes maintenance.
The default pool has two workers (`MYAI_MEMORY_MAINTENANCE_WORKER_COUNT=2`) and each
batch receives a 60-second cooperative budget
(`MYAI_MEMORY_MAINTENANCE_DEADLINE_SECONDS=60`). Decay is based on elapsed maintenance
time rather than message count.

This changes execution placement, but it is not complete latency isolation:

- candidate extraction, memory write/retrieval, and maintenance scheduling still run
  synchronously when the per-user memory lock is available
- foreground chat/task memory operations and background maintenance use non-blocking
  lock admission; the losing side records `deferred`/skipped work instead of waiting
- skipped foreground memory work is not durably queued for later replay
- one blocking maintenance call can still hang one worker beyond its cooperative
  deadline; the second default worker limits cross-user impact, but enough blocking
  calls can exhaust the pool and prevent clean shutdown until they return
- scheduler state and pending maintenance requests are process-local and are not
  recovered after restart

Durable jobs, cross-process leases, hard transport-level cancellation, and replay of
deferred foreground memory work remain production-hardening items.

## 7. Execution Path

1. Introduced `AppRuntime`, FastAPI lifespan, dependency functions, and explicit
   constructors.
2. Added SQLite migrations/repository and persisted AgentRun/TaskRun transitions.
3. Propagated `user_id`, `conversation_id`, and `agent_run_id` across chat and task.
4. Moved consolidation/decay execution to the scheduler and made decay elapsed-time
   based.
5. Applied common resilience and error policies at provider, tool, and API boundaries.
6. Added focused concurrency, lifecycle, persistence, ownership, deadline,
   backpressure, idempotency, and compatibility tests plus independent review.

## 8. Acceptance Review

Verified during Stage 3 implementation and focused review:

- lifespan creates one shared service graph; import does not eagerly construct it
- partial startup and repeated shutdown preserve ownership and close order
- AgentRun/TaskRun relationships, restart recovery, ownership filtering, and
  idempotent replay are persisted
- concurrent knowledge uploads in the supported process do not lose JSON index entries
- task admission applies bounded backpressure without creating a rejected run
- chat/task deadlines propagate through orchestration and include conversation-lock
  waiting
- foreground memory operations do not wait behind maintenance; contention produces an
  explicit deferred/skipped result, while maintenance contention is rescheduled
- timed-out tool work is outcome-unknown and prevents premature dependency closure
- a blocked task worker or maintenance scheduler prevents unsafe runtime teardown and
  permits a later close retry after the work returns

Final integrated checkpoint gate:

- Python full regression: **307/307 passed**.
- Java full regression: **23 total, 22 passed, 1 skipped, 0 failed**.
- root release smoke and repository artifact check: **passed at `0.10.0-local`** with 0 blocking startup diagnostics and no runtime database, model, Chroma, or generated experiment artifact in scope.

## 9. Explicit MVP Limits

- one Python application worker; no multi-process coordination
- no durable distributed task or maintenance queue, lease, or dead-letter recovery
- no automatic replay of side-effecting work after restart
- no exactly-once guarantee for external tool side effects
- no cross-service database foreign key or cascade between Java and Python
- no SQLite encryption, retention automation, or secure-delete guarantee
- deleting a Java conversation does not purge related Python runtime rows
- cooperative deadlines cannot kill arbitrary blocking providers, tools, or maintenance
- background maintenance still contends with foreground memory access, but lock
  admission is non-blocking; skipped foreground work is not durably replayed
- a blocking maintenance call can hang one worker despite the cooperative deadline;
  enough hung calls can exhaust the configured worker pool
- memory/knowledge filesystem coordination is process-local
- synchronous `/task` HTTP 200 represents receipt of a business result, not guaranteed
  task success

## 10. Checkpoint Decision

The requested Stage 3 engineering scope is implemented for the documented
single-runtime MVP. It is ready for the root checkpoint after the final integrated
gate above is recorded. The explicit limits are accepted MVP boundaries, not claims of
multi-worker or production-grade distributed execution.
