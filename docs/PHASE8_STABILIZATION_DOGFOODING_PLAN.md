# Phase 8 Stabilization, Testing And Dogfooding Plan

## Goal

Turn the current local product baseline into something that feels reliable in daily use.

Phase 1-7 made MyAI capable, observable, product-shaped, and releasable as a local snapshot. Phase 8 should avoid large new feature expansion and instead focus on:

- real usage
- regression prevention
- friction removal
- startup/runtime reliability
- local data control
- deployment readiness assessment

The core shift is:

- from "feature-complete local product baseline"
- to "stable enough for repeated daily use and informed deployment decisions"

## Current Foundation

MyAI now has:

- release marker and release smoke command
- local-first startup and diagnostics
- Chat Page 2.0 agent cockpit
- governed memory module
- citation-aware knowledge workbench
- observable task workflows
- MCP-style read-only connectors
- unified observability and eval history
- privacy/safety review and default redaction
- release-quality documentation

The most important unknown is no longer "can the system do the thing?" but:

- which workflows actually feel good after repeated use?
- which failures happen often enough to matter?
- which UI surfaces confuse or slow the user?
- which evals catch real regressions?
- what must be hardened before any public/network deployment?

## Product Principles

- Dogfooding before deployment.
- Stability before new features.
- Fix repeated pain before optimizing rare edge cases.
- Every bug should produce either a test, an eval fixture, a diagnostic, or a product simplification.
- User trust remains local-first: memory, knowledge files, traces, connector paths, and logs are private by default.
- Deployment is a decision after evidence, not a default next step.

## Phase 8 Artifacts

Planned docs/artifacts:

- `docs/PHASE8_STABILIZATION_DOGFOODING_PLAN.md`
- `docs/DOGFOODING_LOG.md`
- `docs/PAIN_POINT_TRACKER.md`
- optional expanded smoke/e2e scripts after 8.2

## 8.1 Dogfooding Log And Pain Point Tracker

Purpose: create a disciplined loop for real usage.

Add:

- dogfooding log template
- pain point tracker
- severity and frequency fields
- workflow labels:
  - startup
  - chat
  - memory
  - knowledge
  - task
  - connector
  - observability
  - settings
  - docs
- decision rules for what to fix first

Acceptance criteria:

- [x] Real usage issues can be captured without interrupting work.
- [x] Every repeated issue can be traced to a fix/test/doc decision.
- [x] Phase 8 work is driven by observed pain, not speculation.

Implemented baseline:

- `docs/DOGFOODING_LOG.md` now includes:
  - workflow labels
  - severity/frequency definitions
  - a compact session template
  - initial real-use findings from recent stabilization debugging
- `docs/PAIN_POINT_TRACKER.md` now includes:
  - decision rules
  - rough priority formula
  - status/workflow vocabulary
  - initial tracker rows for startup, settings, memory, task, and model-runtime visibility issues
  - a priority queue for 8.2 smoke expansion

## 8.2 End-To-End Local Smoke Expansion

Purpose: move beyond static release smoke into basic product-path verification.

Add or improve:

- local startup smoke:
  - doctor
  - start local mode
  - wait for Java/Python readiness
  - stop and verify ports are released
- API smoke:
  - chat endpoint
  - memory settings/list endpoint
  - knowledge files endpoint
  - task tools endpoint
  - observability summary endpoint
- UI smoke where practical:
  - login/local auth reaches home
  - main tabs render
  - health center loads
- failure output that points to logs and likely fix.

Acceptance criteria:

- [x] A single command can verify the most important local product paths.
- [x] Smoke failures are actionable.
- [x] Smoke does not require real API keys or personal data.

Implemented baseline:

- Added root command:
  - `local-smoke.cmd`
- Added implementation:
  - `scripts/local-smoke.ps1`
- Default smoke covers:
  - `doctor -LocalMode`
  - clean stop before start
  - LocalMode start
  - Python readiness via `/observability/summary`
  - Java readiness via `/home`
  - frontend session and CSRF discovery
  - observability summary
  - memory settings/list/query
  - knowledge files
  - task tools/runs
  - chat submit with Stub fallback allowed
  - task execution
  - stop and port release verification
- Optional flags:
  - `-KeepRunning`
  - `-SkipStartStop`
  - `-IncludeLiveModelProbe`
  - `-SkipChatSmoke`
  - `-SkipTaskSmoke`
- Failure output points to:
  - `scripts/logs/python-service.log`
  - `scripts/logs/java-service.log`

Usage:

```powershell
.\local-smoke.cmd
.\local-smoke.cmd -KeepRunning
.\local-smoke.cmd -SkipStartStop
.\local-smoke.cmd -IncludeLiveModelProbe
```

## 8.3 UI/UX Friction Fixes

Purpose: make repeated use smoother without redesigning the whole app.

Focus areas:

- confusing labels
- overloaded panels
- too-noisy trace or metadata
- missing loading/error states
- mobile/responsive rough edges
- page sections that require too much scrolling
- buttons that are hard to distinguish
- settings that are technically correct but not user-comprehensible

Acceptance criteria:

- Fixes are tied to dogfooding findings.
- Everyday actions become faster or clearer.
- Advanced metadata remains available but less intrusive.

## 8.4 Real-Use Regression Tests

Purpose: turn painful real-world failures into permanent checks.

Targets:

- memory:
  - accidental writes
  - wrong pending behavior
  - correction/history regressions
  - sensitive memory handling
- knowledge:
  - citation absence
  - wrong document selection
  - maintenance/rebuild regressions
- task:
  - missing trace events
  - permission policy mistakes
  - background task state regressions
  - connector redaction regressions
- startup:
  - local mode failures
  - port cleanup failures
  - missing dependency diagnostics

Acceptance criteria:

- High-frequency/high-severity pain points gain tests or eval cases.
- The release smoke remains fast enough for routine use.
- Heavier checks are separated from quick smoke if needed.

## 8.5 Performance And Startup Time Review

Purpose: make MyAI feel responsive enough for daily local use.

Measure:

- doctor duration
- local startup duration
- first page load
- first chat response
- knowledge upload/index time for small files
- task execution latency
- health center load time

Potential fixes:

- reduce repeated frontend fetches
- cache stable health/config data
- lazy-load heavy panels
- trim noisy startup work
- separate eval/report calls from everyday page load

Acceptance criteria:

- Baseline timings are documented.
- Obvious slow paths have owners or fixes.
- Product startup does not feel mysterious when slow.

## 8.6 Local Data Management MVP

Purpose: make local-first trust operational, not only documented.

Add:

- local data inventory UI/API or report
- clear storage locations:
  - Java DB
  - Python runtime
  - Chroma stores
  - knowledge uploads
  - logs
  - eval history
- safe delete/reset controls where appropriate:
  - eval history
  - knowledge files
  - conversations
  - memory items
  - runtime task history
- redaction preview for diagnostics if export is added

Acceptance criteria:

- User can understand what local data exists.
- User has a safe way to clean common local artifacts.
- Destructive actions are explicit and scoped.

## 8.7 Deployment Readiness Assessment

Purpose: decide whether the next phase should be public deployment, local distribution, or more stabilization.

Assess:

- auth/security model
- HTTPS requirement
- secrets management
- file upload security
- connector sandboxing
- hosted-mode blockers
- user data isolation
- backups and restore
- logs and redaction
- rate limits and model cost
- deployment target options:
  - localhost only
  - LAN/NAS
  - personal VPS
  - Docker
  - public web deployment

Acceptance criteria:

- A deployment recommendation exists with risks and prerequisites.
- Public deployment is not attempted unless security/data boundaries are credible.
- If deployment is deferred, the next hardening actions are clear.

## Recommended Implementation Order

1. 8.1 Dogfooding Log And Pain Point Tracker
2. 8.2 End-To-End Local Smoke Expansion
3. 8.3 UI/UX Friction Fixes
4. 8.4 Real-Use Regression Tests
5. 8.5 Performance And Startup Time Review
6. 8.6 Local Data Management MVP
7. 8.7 Deployment Readiness Assessment

## Phase 8 MVP Definition

Phase 8 can be considered complete when:

- there is a dogfooding record with real usage findings
- the most common pain points are triaged
- the release smoke or e2e smoke covers core local paths
- at least several real-use regressions are locked into tests/evals
- local data storage and cleanup are visible enough for safe daily use
- a deployment readiness recommendation is documented

## Non-Goals

- Public cloud deployment.
- Multi-tenant hosting.
- Paid product infrastructure.
- Write-capable external connectors.
- Large frontend rewrite.
- New major agent capability modules.

These should wait until stabilization evidence shows the current product baseline is reliable.
