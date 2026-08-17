# Pain Point Tracker

This tracker converts dogfooding observations into prioritized Phase 8 work.

Use `docs/DOGFOODING_LOG.md` for chronological observations. Use this file for triage, ownership, and fix decisions.

## Decision Rules

- Fix blockers immediately.
- Prioritize repeated medium/high issues over one-off edge cases.
- A fixed bug should produce at least one durable artifact:
  - regression test
  - eval fixture
  - smoke check
  - diagnostic
  - documentation update
- Product friction must be tied to a concrete workflow.
- If a fix only improves internal elegance and does not reduce observed pain, defer it.
- If an issue is caused by unclear product state, prefer making the state visible before adding more configuration.

## Priority Formula

Use this rough score when ordering Phase 8 work:

```text
priority = severity_weight + frequency_weight + workflow_weight - mitigation_weight
```

Severity weight:

- blocker = 5
- high = 4
- medium = 2
- low = 1

Frequency weight:

- frequent = 3
- repeated = 2
- once = 0

Workflow weight:

- startup, memory, task, chat = 2
- knowledge, settings, observability = 1
- docs, release, connector = 0

Mitigation weight:

- no workaround = 0
- workaround exists = 1
- already fixed and verified = 3

The score is guidance, not bureaucracy. Use judgment.

## Status Values

- `open`
- `triaged`
- `in_progress`
- `fixed`
- `deferred`
- `won't_fix`

## Workflow Labels

- startup
- chat
- memory
- knowledge
- task
- connector
- observability
- settings
- docs
- release

## Tracker

| ID | Status | Workflow | Severity | Frequency | Score | Summary | Evidence | Decision | Durable Artifact | Follow-up |
| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |
| P8-001 | fixed | docs | low | once | 0 | Start Phase 8 stabilization loop | `docs/PHASE8_STABILIZATION_DOGFOODING_PLAN.md` | Build a lightweight dogfooding loop before more feature work | `docs/DOGFOODING_LOG.md`, `docs/PAIN_POINT_TRACKER.md` | Drive 8.2 from this queue |
| P8-002 | fixed | settings | medium | repeated | 2 | User could not tell whether model runtime was real or Stub | `/observability/summary`, Settings health center | Expose effective model mode without exposing secrets | `tests.test_model_status`, `tests.test_observability_summary`, health UI card | Consider a future live provider probe button |
| P8-003 | fixed | task | high | repeated | 5 | Task workbench failed through Java proxy in LocalMode | `/task/runs`, `/task/tools`, `/task` | Fix LocalMode async auth and JSON error boundaries | `TaskControllerLocalModeTest`, API verification | Add to 8.2 product-path smoke |
| P8-004 | fixed | memory | high | repeated | 5 | Manual memory write/profile/query disagreed through Java/Python path | `/memory/write`, `/memory/profile`, `/memory/query` | Fix manual write fallback and Java memory proxy behavior | `test_memory_manual_write`, `MemoryControllerLocalModeTest` | Add memory write/list/query to 8.2 smoke where safe |
| P8-005 | fixed | startup | blocker | repeated | 6 | Double-click startup appeared stuck on Java service | `start-myai.cmd`, `scripts/start-myai.ps1`, `scripts/logs/java-service.log` | Default no-arg startup should use LocalMode and fail fast on Java startup errors | startup diagnostics, script verification | Add start/stop/port-release check to 8.2 smoke |
| P8-006 | fixed | settings | high | repeated | 4 | System Health could not read Python observability in LocalMode | `/observability/summary`, local auth config | Allow read-only health/catalog endpoints and keep LocalMode auth active | Java tests, endpoint verification | Add health center API check to 8.2 smoke |
| P8-007 | fixed | chat | high | repeated | 5 | Frontend chat returned system error when real provider was unreachable | Browser chat submit, Python `/chat` 500 | Apply runtime LLM fallback, not only initialization fallback | `tests.test_model_fallback`, Java/Python chat smoke | Add chat smoke to 8.2 |
| P8-008 | fixed | memory | medium | repeated | 3 | Newly written memory appeared in profile but query did not retrieve it | Memory write/profile/query smoke | Add lexical boost for exact/keyword memory retrieval candidates | `tests.test_memory_retrieval_lexical`, memory query smoke | Add memory write/query smoke to 8.2 |
| P8-009 | fixed | startup | medium | repeated | 2 | Startup script sometimes warns Python did not become ready within 60s although API is reachable shortly after | `scripts/start-myai.ps1 -LocalMode -NoPause`, `/observability/summary` 200 after warning | Add independent HTTP readiness polling in 8.2 smoke so false negatives are caught and timed | `scripts/local-smoke.ps1` readiness checks | Consider tuning startup script timeout separately if this recurs |
| P8-010 | fixed | settings | medium | once | 0 | System Health memory policy card read nested memory settings as top-level fields | `/memory/settings`, health center payload | Normalize memory settings payload before rendering health center | frontend script syntax check | Include health-center data checks in 8.2 |

## Priority Queue For Phase 8.2

Status: implemented as `local-smoke.cmd` / `scripts/local-smoke.ps1`.

1. Local startup smoke: doctor, LocalMode start, readiness, stop, port release.
2. Java-to-Python API smoke: observability, memory, task, knowledge, and settings paths.
3. UI reachability smoke: LocalMode `/home`, main template markers, CSRF, and health-center data availability.
4. Failure guidance: smoke output points to `scripts/logs/python-service.log` and `scripts/logs/java-service.log`.
5. Chat fallback smoke: provider unavailable should degrade to Stub response instead of 500.
6. Memory query smoke: memory settings/list/query must not fail through Java/Python.

Deferred from default smoke:

- Stateful memory write/profile verification is still better as a targeted regression test because repeated smoke runs would pollute the local memory profile.

## Fix Decision Template

```text
ID:
Root cause:
Chosen fix:
Durable artifact:
Verification:
Deferred follow-up:
```
