# Dogfooding Log

This log captures real MyAI usage sessions and the friction found during those sessions.

Keep entries short enough to write while working. The pain point tracker decides priority later.

## How To Use

1. Start a session before real use or debugging.
2. Record what workflow was attempted and what happened.
3. Link concrete evidence when possible:
   - UI message
   - endpoint
   - log file
   - test name
   - screenshot path
   - related tracker ID
4. If the same issue appears again, add a new observation and increment frequency in `docs/PAIN_POINT_TRACKER.md`.

## Workflow Labels

- `startup`
- `chat`
- `memory`
- `knowledge`
- `task`
- `connector`
- `observability`
- `settings`
- `docs`
- `release`

## Severity

- `low`: annoyance or unclear copy; does not block work.
- `medium`: feature still usable, but requires workaround or debugging.
- `high`: a core local workflow fails for normal use.
- `blocker`: startup, login, data safety, or destructive behavior prevents use.

## Frequency

- `once`: observed once.
- `repeated`: observed more than once or in more than one related path.
- `frequent`: expected to affect routine daily use.

## Entry Template

```text
### YYYY-MM-DD HH:mm - Short Title

Workflow:
Scenario:
Expected:
Actual:
Severity:
Frequency:
Evidence:
Tracker:
Follow-up:
```

## Sessions

### 2026-07-02 15:45 - Frontend Main Path Validation Before 8.2

Workflow: chat, memory, knowledge, task, observability, settings
Scenario: Before freezing 8.2 smoke commands, validate whether the current frontend main paths actually work.
Expected: Browser/frontend paths should submit through Java, reach Python where needed, and return usable UI/API results.
Actual: Found and fixed chat provider fallback failure, slow repeated provider failures, memory query drift, and settings health memory-setting binding. Browser automation later became unavailable, so remaining checks used Java frontend-equivalent HTTP session calls with CSRF.
Severity: high
Frequency: repeated
Evidence: frontend browser chat returned `System error`; Java/Python smoke later passed for chat, memory, knowledge, task, observability, settings.
Tracker: P8-007, P8-008, P8-009, P8-010
Follow-up: 8.2 should turn these checks into a repeatable local smoke command and repair Python startup ready false warnings.

### 2026-07-02 10:10 - Phase 8.1 Dogfooding Loop Setup

Workflow: docs
Scenario: Begin Phase 8 stabilization with a durable dogfooding and pain point loop.
Expected: Real-use findings can be captured, triaged, and converted into tests, smoke checks, docs, or product fixes.
Actual: Upgraded dogfooding log and pain point tracker from placeholders into working Phase 8 artifacts.
Severity: low
Frequency: once
Evidence: `docs/DOGFOODING_LOG.md`, `docs/PAIN_POINT_TRACKER.md`
Tracker: P8-001
Follow-up: Use the tracker priority queue to drive 8.2 local smoke expansion.

### 2026-07-02 09:55 - Model Runtime Mode Was Not Visible

Workflow: settings
Scenario: User wanted to know whether the current model was a real provider model or Stub.
Expected: System Health should show effective model mode without exposing secrets.
Actual: Health center only said model keys are managed by Python Agent environment variables.
Severity: medium
Frequency: repeated
Evidence: `GET /observability/summary`, Settings > System Health
Tracker: P8-002
Follow-up: Added model runtime status to observability summary and Settings health card.

### 2026-07-02 09:20 - Task Workbench Failed Through Java Proxy

Workflow: task
Scenario: Frontend task list and task execution failed in LocalMode.
Expected: Java frontend task APIs should proxy Python task service and return JSON.
Actual: Task list loaded as failure and execution showed "任务执行错误，请稍后重试".
Severity: high
Frequency: repeated
Evidence: `/task/runs`, `/task/tools`, `/task`, LocalMode auth behavior
Tracker: P8-003
Follow-up: Fixed async/local auth dispatch and added Java local mode task controller coverage.

### 2026-07-02 08:50 - Memory Write Succeeded But Profile/Query Failed

Workflow: memory
Scenario: Manual memory write displayed success, but profile did not show the memory and query errored.
Expected: Manual write, profile list, and query should agree through Java -> Python.
Actual: Manual write path and Java error boundaries were inconsistent.
Severity: high
Frequency: repeated
Evidence: `/memory/write`, `/memory/profile`, `/memory/query`
Tracker: P8-004
Follow-up: Fixed Python manual write fallback and Java memory JSON/error handling.

### 2026-06-30 22:30 - Double-Click Startup Appeared Stuck

Workflow: startup
Scenario: Starting through `start-myai.cmd` by double-click appeared stuck on Java startup.
Expected: Default startup should reach LocalMode or fail with actionable output.
Actual: No-argument startup used MySQL mode and Java failed while the script waited.
Severity: blocker
Frequency: repeated
Evidence: `scripts/logs/java-service.log`, `start-myai.cmd`, `scripts/start-myai.ps1`
Tracker: P8-005
Follow-up: Default double-click path now starts LocalMode; startup failure exits non-zero with cleanup.

### 2026-06-30 21:40 - System Health Could Not Read Python Observability

Workflow: settings
Scenario: Settings health center said Python observability API could not be read.
Expected: LocalMode should still expose Python observability through Java.
Actual: Java endpoint returned login/home HTML instead of JSON.
Severity: high
Frequency: repeated
Evidence: `/observability/summary`, local auth/security config
Tracker: P8-006
Follow-up: Fixed LocalMode auth/security access for health/catalog endpoints.
