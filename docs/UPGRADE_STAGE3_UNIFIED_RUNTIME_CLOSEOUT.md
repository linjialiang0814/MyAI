# Stage 3 Unified Runtime MVP Closeout

Date: 2026-08-11

Release target: `0.10.0-local`

Status: completed for the supported single Python application runtime. Focused review,
integrated regression, release smoke, and artifact-scope verification are recorded
below.

## Decision

Stage 2 is complete as a reproducible graduation-design engineering evidence
baseline. It is not a thesis manuscript, although the frozen artifacts and reviewed
negative findings can support a broader paper later.

Stage 3 satisfies its MVP objective: one FastAPI lifespan now owns the Python service
graph, runtime runs are durable, Java/Python ownership references are explicit,
consolidation and decay execute in a background scheduler, and common resilience and
error contracts cover the main chat/task path.

## Delivered Scope

- FastAPI lifespan plus dependency injection for shared Agent, Memory, Knowledge, and
  Task instances
- separate Python SQLite persistence for AgentRun, AgentStep, TaskRun, task events,
  recovery state, and idempotency records
- `user -> conversation -> agent_run -> task_run` linkage with owner-filtered queries
- startup recovery that terminates interrupted runs without replaying tool side effects
- process-local, bounded, coalesced memory-maintenance scheduling with two workers by
  default and a 60-second cooperative per-batch deadline
- shared deadlines, circuit breakers, bounded backoff, idempotency, safe errors, and
  correlation identifiers
- task admission backpressure and idempotent replay of an already accepted run
- concurrent knowledge-index protection and atomic local index/file replacement
- shutdown ordering that refuses to release dependencies while task, tool, or
  maintenance work is still running

## Ownership And API Contract

Java is authoritative for authentication, users, conversations, ownership checks, and
chat messages. Python receives Java-validated identifiers and stores them as logical
references; the two services use separate databases.

Synchronous `POST /task` returns HTTP 200 when it can return a task business-result
envelope. That envelope may describe a failed or cancelled task. Callers must inspect
`status`, `success`, `error_code`, and `retryable` rather than equating HTTP 200 with
successful execution.

## Verification Record

Focused Stage 3 suites have passed for lifespan/DI ownership, SQLite persistence and
recovery, relationship and idempotency contracts, concurrent upload safety,
backpressure, chat/task deadlines, API compatibility, and blocked-worker shutdown.
Independent runtime and maintenance reviews were also performed.

Authoritative final gate:

- Python full regression: **307/307 passed**.
- Java full regression: **23 total, 22 passed, 1 skipped, 0 failed**.
- release smoke, compile/static checks, and artifact review: **passed at `0.10.0-local`**; startup diagnostics had 0 failures and no runtime database, model, Chroma, or generated experiment artifact was added.

## Accepted MVP Limits

- This is one Python application runtime, not a multi-worker deployment model.
- Deadlines are cooperative boundary checks; they cannot forcibly stop arbitrary
  blocking Python threads. A timed-out side effect is outcome-unknown and is not
  automatically retried.
- Background maintenance still contends for the same per-user memory lock used by
  foreground chat/task operations. Admission is non-blocking: the losing side records
  deferred/skipped work instead of waiting, and skipped foreground memory work is not
  durably replayed.
- One blocking maintenance call can still hang one worker beyond its cooperative
  deadline. The second default worker reduces cross-user impact, but enough blocking
  calls can exhaust the pool and prevent clean shutdown until they return.
- Task admission and maintenance queues are process-local and not persisted for
  restart recovery.
- Python runtime SQLite is unencrypted. Retention, secure deletion, and user export are
  not automated.
- Deleting a Java conversation does not cascade to Python AgentRun/TaskRun rows.
- External tool side effects are not exactly-once.

## Next Hardening Priorities

1. Add durable maintenance jobs or dirty revisions, bounded batches, hard
   transport-level cancellation, and replay/compensation for deferred foreground work.
2. Define a supported multi-worker strategy with transactional metadata or leases.
3. Add retention/export/purge coordination and encryption-at-rest options.
4. Expand long-running live-model and failure-injection validation before any public
   deployment claim.
