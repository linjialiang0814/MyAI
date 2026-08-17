# Execution Log

## 2026-08-17 - Sanitized GitHub Publication

### Publication

- Rotated the affected local MySQL development credential without printing either the
  previous or replacement value; the replacement was verified, the previous local
  configuration no longer authenticates, and the MySQL service returned to stopped.
- Replaced public `main` with sanitized root commit
  `405404f3dc3643791796afd0bc4c59f571e38d06`; no public branch or tag points to the
  previous root history.
- GitHub Actions run
  [32010200396](https://github.com/linjialiang0814/MyAI/actions/runs/32010200396)
  passed all four jobs: static quality gates, Python 3.12 tests, Java 17 verify, and
  portable artifact build/verification/controls.
- Published prerelease
  [v0.11.0-local](https://github.com/linjialiang0814/MyAI/releases/tag/v0.11.0-local)
  with the 90,342,148-byte Windows ZIP and its SHA-256 file. GitHub reports the ZIP
  digest as `b8321035fbd6858ec24ae3f6c3cd197019a61064f23c60a0b311cf6c9aa3aa7c`.

### Repository Governance

- Added the public repository description and ten focused technology topics.
- Enabled secret scanning, push protection, Dependabot alerts/security updates, and
  private vulnerability reporting. The sanitized reachable history has zero open
  secret-scanning alerts.
- Protected `main`: pull requests, four required checks, linear history, resolved
  conversations, and admin enforcement are required; force pushes and deletion are
  disabled.
- Dependabot's first activation created duplicate branch `push` and `pull_request`
  jobs. Redundant non-main runs were cancelled, and CI now limits `push` execution to
  `main` while retaining pull-request validation.

### Remaining External Boundary

- GitHub still resolves the former commit by direct SHA even though no branch or tag
  references it. The credential is no longer valid, but GitHub Support cache cleanup
  remains the final historical-hygiene action.
- The repository remains intentionally unlicensed until the owner explicitly chooses
  MIT, Apache-2.0, or retained rights.

## 2026-08-17 - Public Repository Readiness Checkpoint

### Changes

- Added the bilingual project overview, final project audit, contribution and security
  policies, synthetic UI screenshot, GitHub templates, Dependabot configuration, and
  an original SVG application mark.
- Hardened repository gates against machine-specific paths, common credential formats,
  model weights, runtime artifacts, and mismatched documentation image formats.
- Normalized empty no-tool planner output, made the deadline propagation test use a
  deterministic clock, improved Ollama discovery for D-drive installations, and made
  portable process-tree shutdown verifiable when `taskkill` is unavailable.

### Verification

- Static repository quality gates: **passed** across 52 Markdown files, dependency pins,
  artifact/secret rules, one documentation image, and the ordered frontend bundle.
- Python full regression: **309/309 passed** on CPython 3.12; the repaired deadline case
  also passed 100 deterministic repetitions.
- Java `mvnw verify`: **26 tests, 0 failures, 0 errors, 1 skipped**; executable MyAI JAR
  rebuilt successfully.
- Release smoke: **passed**, including startup diagnostics, Python tests, Java tests,
  packaging, and local-loopback checks.
- Final portable artifact: **165 manifest files**, **90,342,148 bytes**, SHA-256
  `b8321035fbd6858ec24ae3f6c3cd197019a61064f23c60a0b311cf6c9aa3aa7c`; checksum and
  manifest verification passed. Portable controls passed, including owned root/child
  process shutdown, service-port closure, PID metadata cleanup, and invalid-port rejection.

### Publication Gate

- The current source tree is suitable for a local checkpoint.
- GitHub publication remains blocked until the exposed historical local MySQL credential
  is rotated and the public `main` history is replaced with a sanitized root. The existing
  development branch must not be pushed because it inherits the affected history.
- Stage 2 evidence retains its original commit identity and checksums. The sanitized public
  checkpoint is functionally equivalent but must not be described as a rerun of that
  frozen experiment.

## 2026-08-12 - Stage 4 Portable Local App Demo Baseline

### Context

- Stage 3 closed the single-runtime service and persistence baseline.
- Stage 4 uses two checkpoints: first a transferable Windows App Demo, then one real
  standard MCP interoperability slice.
- The first package intentionally depends on Python 3.12 x64 and Java 17+ and does not
  claim to be an installer or offline runtime bundle.

### Changes

- Added allowlisted portable build and strict checksum/manifest verification.
- Added package-local setup, human/JSON doctor, start, stop, status, and reset commands.
- Added environment isolation, package-owned process identity, loopback binding,
  link-safe reset, bytecode suppression, and dedicated observability/eval work paths.
- Added synthetic RAG data and a package-demo-only MCP-style filesystem connector.
- Split the 5,415-line workbench template into a 553-line HTML shell, external CSS,
  and seven ordered JavaScript files while preserving existing behavior.
- Added Windows CI and a reusable repository quality gate.

### Review

- Independent review covered CSRF/static resources, script order, CI false positives,
  secret/config inclusion, package inventory, environment inheritance, PID ownership,
  reset traversal through reparse points, second-start pollution, and demo routing.
- Existing MCP-style adapters are named honestly; standard MCP Server interoperability
  remains the next checkpoint.

### Verification

- Python full regression: **308/308 passed** on CPython 3.12.
- Java `mvnw verify`: **26 tests, 0 failures, 0 errors, 1 skipped**; executable
  Spring Boot JAR rebuilt successfully.
- Portable artifact: **165 manifest files**, external ZIP SHA-256 and all per-file
  hashes verified. Extracted safety controls passed, including environment isolation,
  foreign-process rejection, owned parent/child process-tree shutdown, and link-safe
  reset.
- Final local artifact `MyAI-0.11.0-local-windows-x64.zip`: **90,426,899 bytes**;
  SHA-256 `58d110551aca24f63b666e16cf07101301bc02ddbaa2e4d07738376272e84df9`.
- Fresh install completed in a new 75-character package path containing spaces using
  a new package-local Python 3.12 environment and the pinned requirements. JSON doctor
  passed all 7 checks; Python OpenAPI, Java home, CSS, and JavaScript returned HTTP 200.
  Both services bound only to `127.0.0.1`; status recognized both owned processes;
  stop removed both process trees, listeners, and PID metadata. A second doctor passed.
- Forced reset preserved `config/app.env`, removed package-local data/runtime state and
  the virtual environment, and correctly returned the package to a setup-required state.
- Static quality gates, PowerShell parsers, frontend syntax/order checks, artifact
  verification, `git diff --check`, independent P0/P1 review, and the shared release
  smoke all passed.

### Checkpoint

- Release target: `0.11.0-local`.
- Plan: `docs/UPGRADE_STAGE4_LOCAL_APP_DEMO_PLAN.md`.
- Closeout: `docs/UPGRADE_STAGE4_PORTABLE_APP_BASELINE_CLOSEOUT.md`.
- Standard read-only MCP interoperability proceeds as a separate Stage 4 checkpoint.

## 2026-08-11 - Upgrade Stage 3 Unified Runtime MVP

### Context

- Stage 2 was accepted as a reproducible graduation-design engineering evidence
  baseline. It is complete for that scope but is not a thesis manuscript or paper; its
  frozen artifacts may support broader research later.
- Stage 3 targeted a restart-aware, locally deployable runtime for one Python
  application worker, not a distributed workflow engine.
- Java remains authoritative for authentication, users, conversation ownership, and
  chat messages. Python receives validated identifiers and persists runtime references
  in a separate database.

### Changes

- Added one FastAPI lifespan-owned `AppRuntime` and dependency-injected Agent, Memory,
  Knowledge, and Task services. Importing `app.main` no longer constructs the service
  graph.
- Added Python SQLite migrations and repositories for AgentRun, AgentStep, TaskRun,
  task events, recovery, and idempotency records.
- Established the logical `user -> conversation -> agent_run -> task_run` chain and
  owner-filtered run APIs without sharing the Java database.
- Added restart recovery that terminates interrupted runs without replaying
  side-effecting tools.
- Moved consolidation and decay execution out of the synchronous chat call sequence
  into a bounded, coalescing, lifespan-owned maintenance scheduler with two workers by
  default and a 60-second cooperative batch deadline.
- Added non-blocking lock admission for foreground chat/task memory operations and
  maintenance. Contention is recorded as deferred/skipped instead of making the
  foreground request wait behind maintenance.
- Unified cooperative chat/task deadlines, circuit breakers, bounded retry/backoff,
  idempotency, safe error envelopes, and correlation identifiers.
- Added bounded background-task admission. Existing idempotent runs replay before the
  capacity check, while rejected new work creates no TaskRun.
- Protected same-user knowledge upload/index read-modify-write operations and replaced
  local file/index writes atomically.
- Hardened shutdown ownership: providers and repositories stay open when a blocking
  task, timed-out tool future, or maintenance worker has not stopped, and close can be
  retried after the work returns.
- Preserved synchronous `POST /task` compatibility: HTTP 200 is a task business-result
  envelope and may contain a failed result; callers must inspect `status`, `success`,
  `error_code`, and `retryable`.

### Review

- Focused review covered lifespan ownership, dependency-instance identity, startup
  rollback, close order, persistence/recovery, relationship integrity, concurrency,
  backpressure, idempotency, API compatibility, and deadline behavior.
- Deadline timeout is explicitly cooperative and cannot prove that arbitrary blocking
  Python work stopped. Timed-out side effects remain outcome-unknown and are not
  automatically retried.
- Background maintenance is no longer invoked synchronously by chat, but it still
  contends for the same per-user memory lock. Non-blocking admission protects request
  latency, while skipped foreground memory work is not durably replayed.
- A hung maintenance dependency can consume one worker beyond the cooperative
  deadline. The second default worker limits cross-user impact, but enough hung calls
  can exhaust the pool and prevent clean shutdown until they return.

### Verification

- The latest focused Stage 3 runtime/resilience/lifecycle acceptance set passed 31
  tests, including idempotent replay under full-queue backpressure.
- Stage 3 integration and chat API compatibility checks passed during implementation.
- Scoped diff/format checks passed during independent review.
- Final Python full regression: **307/307 passed** (`unittest discover -s tests`).
- Final Java full regression: **23 total, 22 passed, 1 skipped, 0 failed** (`mvnw.cmd test`).
- Final root release smoke and clean-artifact result: **passed at `0.10.0-local`**; startup diagnostics reported 0 failures, and the repository scope review found no runtime database, model, Chroma, or generated experiment artifact added by Stage 3.

### Explicit MVP Limits

- Supported deployment is one Python application worker; filesystem locks, context,
  and maintenance scheduling are not coordinated across processes.
- Task admission and maintenance queues are process-local and are not recovered after
  restart. There is no durable lease or dead-letter queue.
- Python runtime SQLite is unencrypted and has no automated retention, export, or
  secure-delete workflow.
- Deleting a Java conversation does not cascade to Python AgentRun/TaskRun rows.
- Java and Python have no cross-service database foreign key.
- External tool side effects are not exactly-once.

### Checkpoint

- Release target: `0.10.0-local`.
- Detailed plan: `docs/UPGRADE_STAGE3_UNIFIED_RUNTIME_PLAN.md`.
- Closeout: `docs/UPGRADE_STAGE3_UNIFIED_RUNTIME_CLOSEOUT.md`.
- The Stage 3 MVP is ready for the root checkpoint after the three final verification
  placeholders above are replaced with authoritative results.

## 2026-08-10 - Upgrade Stage 2 Reproducible Core Evidence

### Context

- Stage 1 established the safe local baseline; Stage 2 adds controlled evidence for the
  graduation design's core memory and RAG claims.
- The required workflow was plan 鈫?implement 鈫?review 鈫?checkpoint. A strict formal
  artifact is valid only from a clean, frozen Git commit.

### Changes

- Added a loopback-safe generic OpenAI-compatible provider for local chat and embeddings, with fail-closed real embeddings, deterministic parameters, model health/status, and client cleanup.
- Selected and froze the local baseline:
  - Ollama `0.32.6`
  - `qwen2.5:1.5b-instruct-q4_K_M`
  - `bge-m3:latest`, 1024 dimensions
  - CPU-only inference, context 4096, temperature 0, seed 42, retries 0, no Stub fallback
- Implemented memory arms `none/basic/governed` and RAG arms `vector/hybrid/hybrid_rerank`.
- Added 18 memory cases, 10 synthetic documents, and 30 RAG cases with frozen SHA-256 contracts.
- Added accuracy, answerability, evidence, support, generated-citation, grounded-answer, latency, resource, failure, repeat-consistency, and paired-bootstrap outputs.
- Added strict preflight, provider circuit breaking, dedicated Ollama PID-tree sampling, complete dependency verification, LF output, artifact checksum verification, and publishability gates.
- Fixed earlier evaluation defects in citation semantics, report coverage, observability deltas, no-gold denominators, failure preservation, and scorer polarity/boundary handling.

### Review And Checkpoints

- Implementation checkpoint: `7db4069` (`feat: establish reproducible thesis experiment baseline`).
- The first strict run completed 432/432 but was rejected by mandatory raw-output review because of three objective annotation defects.
- Revision-2 scoring checkpoint: `63f884e` (`fix: harden thesis benchmark annotations`).
- Revision 2 preserved all questions, prompts, observations, documents, and arm behavior; the two runs produced identical answers, selected evidence, and citation labels for all 432 attempts.
- Final r2 artifact, metric, and raw-output reviews found no P0/P1 blocker.

### Formal Result

- Run ID: `thesis-core-v1-r2-20260810T144148Z`
- Attempts: 432/432 successful; 0 model/infrastructure failures; 7/7 checksums verified.
- Memory accuracy (`none/basic/governed`): 33.33% / 50.00% / 61.11%.
- Memory forbidden-evidence exposure: 0.00% / 50.00% / 5.56%.
- RAG accuracy (`vector/hybrid/hybrid_rerank`): 76.67% / 70.00% / 70.00%.
- RAG Support Hit@3: 100% for all three arms.
- RAG citation hit: 29.49% / 24.36% / 30.77%.
- RAG grounded answer + citation: 25.64% / 20.51% / 30.77%.
- Total formal runtime: 644.494 seconds; failure rate 0%.

### Verification

- Static contract validation: 18 memory cases / 10 documents / 30 RAG cases.
- Focused experiment regression: 48 tests passed.
- Full Python regression before the formal run: 237 tests passed.
- Python compileall and `git diff --check` passed.
- Live preflight: 9/9 hardware checks and 95/95 dependency checks passed; both model digests, CPU placement, context, and embedding dimension verified.
- Independent artifact, metric, and semantic reviews passed.
- Final root `release-smoke.cmd` passed at version `0.9.0-local`, including startup diagnostics, documentation links, dependency pins, sensitive-default scan, frontend syntax, the full 237-test Python suite, and Java tests.

### Interpretation

- Governed memory improves safe abstention and reduces forbidden-context exposure, but does not improve answerable factual QA over basic memory in this dataset.
- RAG retrieval is saturated at Support Hit@3. Hybrid retrieval and the lightweight reranker do not improve accuracy or recall over vector retrieval here.
- Low citation coverage and irrelevant-context retrieval on no-answer questions are the next research/engineering priorities.
- Full details: `docs/STAGE2_FORMAL_EXPERIMENT_REVIEW.md`.

## 2026-07-13 - Upgrade Stage 1 Safe And Reproducible Baseline

### Context

- The deep project review identified security defaults, ownership boundaries, and persistent test pollution as higher priority than new model or UX features.
- This work is a cross-cutting Phase 8 stabilization gate and does not replace or renumber the existing Phase 8.3-8.7 plan.

### Changes

- Prevented Stub fallback from echoing assembled prompts.
- Set the Java service and supported startup path to loopback-only by default through `SERVER_ADDRESS=127.0.0.1`.
- Changed filesystem MCP to explicit opt-in:
  - `MYAI_MCP_FILESYSTEM_ENABLED=false`
  - explicit roots are required when enabled; empty roots fail fast
  - hidden, environment, credential, private-key, certificate-store, secret, password, and token paths are hidden/rejected
- Added owner-scoped task-run list, detail, and cancellation behavior across Java and Python.
- Fixed the missing `MemoryStatus` import in memory restore and added regression coverage.
- Added configurable runtime storage paths and ephemeral Chroma mode.
- Isolated Python tests into a per-run temporary root with deterministic Stub providers.
- Pinned the remaining unversioned Python dependency and added a release-smoke dependency pin gate.
- Updated release smoke to run the complete package-aware Python test discovery.
- Added the Stage 1 plan and acceptance record:
  - `docs/SAFE_REPRODUCIBLE_BASELINE_PLAN.md`

### Verification

- Passed two consecutive isolated Python suite runs during implementation.
- Passed the final Python suite:
  - `.\.venv\Scripts\python.exe -m unittest`
  - result: 154 tests passed
- Passed Java tests:
  - `.\mvnw.cmd -q test`
  - result: 19 tests, 0 failures, 0 errors, 1 skipped
- Verified development Chroma, knowledge, and memory-settings directories were not mutated by the isolated test runs.
- Passed root `release-smoke.cmd`, including startup diagnostics, documentation links, sensitive-default scan, frontend syntax, the full Python suite, and Java tests.
- Root `release-smoke.cmd` remains the repeatable closeout check for future checkpoints.

### Deferred

- Direct Python service authentication and production multi-user authorization.
- Public/LAN deployment hardening, HTTPS, rate limits, and centralized secrets.
- OS-level filesystem sandboxing.
- Container/CI reproducibility and long-duration persistent-store tests.
- Real local open-source model integration and provider quality calibration.

## 2026-07-06 - Phase 8.2 End-To-End Local Smoke Expansion

### Context

- Phase 8.2 aims to make local product-path verification repeatable before continuing broader stabilization work.
- Existing `release-smoke.cmd` covers static release checks and unit tests, but not a full LocalMode start/API/stop cycle.

### Changes

- Added root smoke command:
  - `local-smoke.cmd`
- Added LocalMode product-path smoke implementation:
  - `scripts/local-smoke.ps1`
- Default smoke covers:
  - startup doctor
  - clean stop before start
  - LocalMode start
  - Python readiness
  - Java readiness
  - `/home` frontend markers and CSRF discovery
  - observability summary
  - memory settings/list/query
  - knowledge files
  - task tools/runs
  - chat submit
  - task execution
  - service stop and port release verification
- Added optional flags:
  - `-KeepRunning`
  - `-SkipStartStop`
  - `-IncludeLiveModelProbe`
  - `-SkipChatSmoke`
  - `-SkipTaskSmoke`
- Updated Phase 8 plan and pain-point tracker with the 8.2 baseline.

### Verification

- First run exposed a smoke-script bug:
  - PowerShell variable `$home` conflicted with read-only `$HOME`, preventing CSRF discovery.
  - Fixed by renaming the local response variable.
- Passed full local smoke:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\local-smoke.ps1`
- Passed root wrapper smoke:
  - `.\local-smoke.cmd`
- Result:
  - `PASS=13 WARN=0 FAIL=0`
- Verified:
  - LocalMode doctor
  - Python and Java startup readiness
  - frontend session and CSRF
  - observability, memory, knowledge, task APIs
  - chat submit
  - task execution
  - clean stop and port release

## 2026-07-03 - Phase 9.1 Real Model Health Probe MVP

### Context

- Stub fallback keeps MyAI usable, but it does not prove external real-model calls are working.
- User asked to upgrade the health module before continuing Phase 8.2.

### Changes

- Added Phase 9 plan:
  - `docs/PHASE9_HEALTH_MODULE_PLAN.md`
- Added Python real-model probe:
  - `POST /observability/model/probe`
- Probe covers:
  - chat
  - task
  - memory
  - embedding
- Probe reports:
  - provider
  - model id
  - real/stub kind
  - ok/status
  - latency
  - missing config
  - classified error type
  - safe error message
- `GET /observability/summary` now includes latest probe under `model.last_probe`.
- Added Java proxy:
  - `POST /observability/model/probe`
- Added Settings > System Health action:
  - `瀹炴椂鎺㈡祴鐪熷疄妯″瀷`
- Updated roadmap with Phase 9.

### Verification

- Passed Python targeted tests:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_model_health tests.test_model_status tests.test_observability_summary`
- Passed frontend inline script syntax check for `home.html`.
- Passed Java tests:
  - `.\\mvnw.cmd -q test`
- Rebuilt Java jar:
  - `.\\mvnw.cmd -q package -DskipTests`
- Restarted LocalMode services.
- Verified Python probe endpoint:
  - `POST http://127.0.0.1:8000/observability/model/probe`
- Verified Java proxy endpoint:
  - `POST http://127.0.0.1:8080/observability/model/probe`
- Current real-provider result:
  - status: `degraded`
  - real roles: `0/4` successful
  - error type: `network`
  - Stub fallback remains enabled for product usability.
- Verified `GET /observability/summary` includes `model.last_probe`.
- Verified `/home` contains:
  - `瀹炴椂鎺㈡祴鐪熷疄妯″瀷`
  - `runModelProbe`
  - `鏈€杩戠湡瀹炴帰娴媊

### 2026-07-03 - Real Model Connectivity Fix

- Investigated why real-provider calls returned `network` errors while Stub fallback worked.
- Found process-level proxy variables:
  - `HTTP_PROXY`
  - `HTTPS_PROXY`
  - `ALL_PROXY`
  - lowercase variants
- These variables pointed to `http://127.0.0.1:9`, which refused SDK connections.
- Verified direct TCP connectivity to:
  - `ark.cn-beijing.volces.com:443`
- Verified direct HTTP client mode with `trust_env=False` can reach the provider endpoint.
- Updated model clients:
  - OpenAI/Volcengine LLM client now uses `httpx.Client(trust_env=False)` by default.
  - Volcengine embedding client now uses `httpx.Client(trust_env=False)` by default.
  - Added `MYAI_MODEL_TRUST_ENV_PROXY=false` default in `.env.example`.
  - If a real local proxy is intentionally used, it can be enabled with `MYAI_MODEL_TRUST_ENV_PROXY=true`.
- Updated health probe output and UI:
  - reports whether proxy environment variables were detected
  - reports whether model clients inherit proxy variables
- Updated configuration docs and Phase 9 plan.

### Verification

- Passed targeted Python tests:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_model_health tests.test_model_fallback`
- Passed frontend inline script syntax check.
- Rebuilt Java jar after stopping services.
- Restarted LocalMode services.
- Verified Java frontend-equivalent probe with CSRF:
  - status: `healthy`
  - real roles: `4/4`
  - chat/task/memory/embedding: `healthy`
  - proxy env detected: `true`
  - model client trust env proxy: `false`

## 2026-07-02 - Frontend Main Path Validation Before Phase 8.2

### Context

- User asked whether the frontend could be guaranteed correct before turning Phase 8.2 into repeatable smoke commands.
- Answer: no full guarantee existed yet; prior validation covered APIs and selected UI paths, not every visible main path.

### Findings And Fixes

- Browser chat submit initially returned:
  - `System error, please check the backend service.`
- Root cause:
  - Python `/chat` returned 500 when the real provider was unreachable.
  - LLM fallback was only applied during initialization, not generation.
- Fixed:
  - added runtime `FallbackLLM`
  - shortened default LLM request timeout
  - disabled SDK retries by default for local dogfooding
  - added short provider-failure circuit breaker for LLM and embedding fallback
- Memory query finding:
  - manual write appeared in memory profile, but query did not return the new exact memory.
- Fixed:
  - added lexical exact/keyword boost in memory retrieval
  - boosts existing vector candidates as well as missing lexical candidates
- Settings health finding:
  - System Health memory card read `/memory/settings` as top-level fields, but API returns nested `settings`.
- Fixed:
  - normalized memory settings payload in health center builder.
- Startup finding:
  - startup script sometimes warns Python did not become ready within 60s, while the API becomes reachable shortly after.
  - recorded as Phase 8.2 follow-up.

### Verification

- Browser-level validation completed for:
  - `/home` LocalMode entry
  - chat submit after fallback fix
  - memory profile/write/query before browser automation disconnected
- Browser automation later could not attach a new tab, so remaining checks used Java frontend-equivalent HTTP session calls with CSRF.
- Passed Python targeted tests:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_model_fallback tests.test_memory_retrieval_lexical`
- Passed frontend inline script syntax check for `home.html`.
- Rebuilt Java jar with:
  - `.\\mvnw.cmd -q package -DskipTests`
- Restarted LocalMode services.
- Final Java frontend-equivalent smoke passed for:
  - home markers
  - observability summary
  - chat
  - memory query
  - knowledge files
  - task execution
  - memory settings
  - task tools/connectors

## 2026-07-02 - Phase 8.1 Dogfooding Log And Pain Point Tracker

### Context

- Phase 8 shifted from feature expansion to stabilization, real-use testing, and dogfooding.
- Recent debugging produced several useful real-world findings across startup, settings, memory, task, and model runtime visibility.

### Changes

- Upgraded `docs/DOGFOODING_LOG.md` into a working dogfooding session log:
  - workflow labels
  - severity and frequency definitions
  - compact entry template
  - initial real-use sessions from recent stabilization work
- Upgraded `docs/PAIN_POINT_TRACKER.md` into a triage tracker:
  - decision rules
  - rough priority formula
  - status and workflow vocabulary
  - tracker entries P8-001 through P8-006
  - priority queue for 8.2 smoke expansion
- Updated `docs/PHASE8_STABILIZATION_DOGFOODING_PLAN.md`:
  - marked 8.1 acceptance criteria as completed
  - documented the implemented baseline
- Updated `docs/ROADMAP.md`:
  - Phase 8 status is now in progress
  - 8.1 dogfooding loop is marked completed

### Verification

- Checked that dogfooding entries P8-001 through P8-006 exist.
- Checked that tracker rows P8-001 through P8-006 exist.
- Checked that the Phase 8 plan marks 8.1 acceptance criteria complete.
- Checked that the roadmap reflects Phase 8 in-progress status.

## 2026-07-02 - Model Runtime Status In System Health

### Context

- User asked how to tell whether the current model runtime is using a real model or Stub.
- The settings health center previously only said model keys are managed by Python Agent environment variables, but did not expose effective runtime mode.

### Changes

- Added Python model status summary at `GET /observability/summary`:
  - `provider_auth_configured`
  - `fallback_to_stub`
  - `memory_llm_extractor_enabled`
  - per-role status for `chat`, `task`, `memory`, and `embedding`
  - effective modes: `stub`, `real`, `real_with_fallback`, `stub_fallback`, `misconfigured`
- Added a new Settings > System Health card: `妯″瀷杩愯妯″紡`.
- The UI shows provider, model id, effective mode, missing config fields, API key presence, and fallback state without exposing secret values.
- Added focused Python tests for model status and observability summary visibility.

### Verification

- Passed Python tests:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_model_status tests.test_observability_summary`
- Passed frontend inline script syntax check:
  - `node --check` on extracted `home.html` scripts
- Rebuilt and restarted LocalMode services.
- Verified running APIs expose model status:
  - `GET http://127.0.0.1:8000/observability/summary`
  - `GET http://127.0.0.1:8080/observability/summary`
- Verified `/home` contains the `妯″瀷杩愯妯″紡` health card.

## 2026-06-30

### LocalMode System Health API Fix

- Investigated Settings -> System Health warning:
  - `鏃犳硶璇诲彇 Python observability API`
- Clarified expected behavior:
  - LocalMode should not disable Python observability
  - model key text is informational because the Java frontend intentionally does not read secrets
  - missing eval history is normal only before any eval has run
- Found actual issue:
  - Java `/observability/summary` returned login/home HTML instead of JSON
  - frontend health fetch treated that as a failed Python observability read
- Updated Java local auth behavior:
  - `/login` redirects to `/home` in LocalMode
  - `LocalAuthFilter` now explicitly replaces anonymous/empty auth with the local user
  - disabled duplicate Servlet filter registration so the filter only runs inside the Spring Security chain
- Updated security access:
  - allowed read-only health/catalog endpoints:
    - `/observability/**`
    - `/eval/**`
    - `/task/tools`
  - user/action endpoints remain authenticated

### Verification

- Passed Java service tests:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`
- Restarted through no-argument `start-myai.cmd` path.
- Verified Java proxy APIs return JSON:
  - `GET http://127.0.0.1:8080/observability/summary`
    - status `200`
    - content type `application/json`
    - eval runs: `27`
    - connectors: `2`
  - `GET http://127.0.0.1:8080/task/tools`
    - tools: `15`
    - connectors: `2`

### Startup Script Double-Click LocalMode Fix

- Investigated Java startup hang from `scripts/logs/java-service.log`.
- Root cause:
  - double-clicking `start-myai.cmd` used the no-argument default path
  - no-argument startup previously used MySQL mode
  - Java failed with `Access denied for user 'root'@'localhost'`
  - Hibernate then reported `Unable to determine Dialect without JDBC metadata`
  - startup script still entered the waiting loop, making the failure look like a hang
- Updated `start-myai.cmd`:
  - no-argument / double-click path now starts `scripts/start-myai.ps1 -LocalMode`
  - explicit arguments still pass through unchanged
- Updated `scripts/start-myai.ps1`:
  - if Java does not listen after startup, the script now reports the failure, stops launched services, and exits non-zero instead of entering the long-running wait loop
- Updated startup documentation:
  - `scripts/README.md`
  - `docs/QUICK_START.md`

### Verification

- Passed PowerShell syntax parse for:
  - `scripts/start-myai.ps1`
- Passed startup diagnostics:
  - `cmd /c start-myai.cmd doctor -LocalMode`
- Passed LocalMode start/stop:
  - `cmd /c start-myai.cmd -LocalMode -NoPause`
  - `cmd /c start-myai.cmd stop`
- Passed no-argument double-click-equivalent start/stop:
  - `cmd.exe /c start-myai.cmd`
  - Java port `8080` opened successfully
  - `cmd /c start-myai.cmd stop`

### Phase 8 Stabilization, Testing And Dogfooding Plan

- Added Phase 8 execution plan:
  - `docs/PHASE8_STABILIZATION_DOGFOODING_PLAN.md`
- Defined Phase 8 focus:
  - dogfooding before deployment
  - stabilization before new major features
  - smoke/e2e expansion
  - real-use regression tests
  - performance and startup review
  - local data management MVP
  - deployment readiness assessment
- Added dogfooding tracking artifacts:
  - `docs/DOGFOODING_LOG.md`
  - `docs/PAIN_POINT_TRACKER.md`
- Updated docs index and roadmap with Phase 8 references.

### Verification

- Passed documentation link/path sanity check for Phase 8 planning docs.

### Phase 7.8 Packaging And Release Baseline

- Added release version marker:
  - `VERSION`
- Added release smoke command:
  - `release-smoke.cmd`
  - `scripts/release-smoke.ps1`
- Release smoke checks:
  - version marker
  - local startup diagnostics
  - documentation link sanity
  - sensitive default scan
  - frontend inline script syntax
  - Python observability/eval smoke tests
  - Java tests
- Added release checklist:
  - `docs/RELEASE_CHECKLIST.md`
- Added artifact cleanup policy:
  - `docs/ARTIFACT_CLEANUP.md`
- Updated docs index, README, release notes, and Phase 7 plan.

### Verification

- Passed release smoke command with:
  - `.\\release-smoke.cmd -JavaHome "<JAVA_HOME>"`
- Smoke covered:
  - version marker
  - local startup diagnostics
  - documentation link sanity
  - sensitive default scan
  - frontend inline script syntax
  - Python observability/eval smoke tests
  - Java tests

### Phase 7.7 Release-Quality Documentation

- Replaced the root README with a product-oriented entrypoint.
- Added `docs/README.md` as the documentation index.
- Added release-quality docs:
  - `docs/QUICK_START.md`
  - `docs/CONFIGURATION_REFERENCE.md`
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/FEATURE_GUIDE.md`
  - `docs/TROUBLESHOOTING.md`
  - `docs/DEVELOPMENT_WORKFLOW.md`
  - `docs/RELEASE_NOTES.md`
  - `docs/KNOWN_LIMITATIONS.md`
- Documented:
  - local mode startup
  - startup diagnostics
  - configuration reference
  - architecture and storage boundaries
  - product features
  - troubleshooting and recovery paths
  - development verification workflow
  - current release baseline and limitations
- Removed the hardcoded database password default from Java application config.
- Updated Phase 7 plan to mark 7.7 baseline implemented.

### Verification

- Passed documentation link/path sanity check.
- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 7.6 Privacy And Safety Review

- Added `docs/PHASE7_PRIVACY_SAFETY_REVIEW.md`.
- Documented local data boundaries for:
  - conversations
  - memory
  - knowledge files and chunks
  - task runtime and trace
  - MCP connector settings
  - observability/eval history
  - logs and runtime artifacts
- Added Python Agent privacy redaction utility.
- Default API responses now redact:
  - local absolute paths
  - path-like fields such as connector roots and eval storage paths
  - secret-like values such as tokens/passwords/api keys
- Added `include_sensitive=true` for explicit local troubleshooting.
- Added privacy metadata to task tool and observability responses.
- Added frontend privacy boundary visibility in:
  - task tool directory
  - observability workbench
  - system health center
- Updated Phase 7 plan to mark 7.6 baseline implemented.

### Verification

- Passed Python observability/privacy tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_summary`
- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 7.5 Screen-Level Product Polish

- Added screen-level hero and workflow guidance to the main workbench areas:
  - memory
  - knowledge
  - task
  - observability
- Refined primary panel headers and subtitles so everyday actions are easier to distinguish from advanced governance and audit surfaces.
- Added a clearer task detail empty state.
- Unified task result rendering across:
  - guided demo task scenarios
  - direct task execution
  - background task creation
  - background task polling
  - background task cancellation
- Improved the empty task run list message with a recovery path.
- Updated Phase 7 plan to mark 7.5 baseline implemented.

### Verification

- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

## 2026-06-29

### Phase 7.4 Demo Scenarios And Guided Workflows

- Added a dedicated Demo workspace in the frontend.
- Added sidebar navigation entry:
  - `婕旂ず`
- Added guided demo cards for:
  - memory correction and governance
  - knowledge-base citation QA
  - task execution and runtime timeline
  - MCP read-only filesystem/git workflows
  - observability and quality gate inspection
- Demo actions now:
  - jump to the relevant workspace
  - fill safe sample prompts or task descriptions
  - show next-step guidance in the target workspace
- Demo flows avoid automatic sensitive writes, file uploads, or destructive actions.
- Updated Phase 7 plan to mark 7.4 baseline implemented.

### Verification

- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 7.3 First-Run Setup And Startup Diagnostics

- Added startup diagnostic action to `scripts/start-myai.ps1`:
  - `.\\start-myai.cmd doctor`
  - `.\\start-myai.cmd doctor -LocalMode`
- Diagnostics now check:
  - Python and Java project directories
  - log directory writability
  - `scripts/start-myai.env`
  - `myai-python-agent/.env`
  - Python executable and key imports
  - Java/JDK command
  - Maven wrapper or built jar availability
  - configured service ports
  - MySQL readiness or SQLite/local mode
  - Chroma, knowledge, and runtime directory writability
  - model/provider readiness for non-stub providers
- Diagnostic output uses explicit `OK`, `WARN`, and `FAIL`.
- `FAIL` exits non-zero to make startup blockers obvious before starting services.
- Updated `scripts/README.md` with the doctor workflow.
- Updated Phase 7 plan to mark 7.3 baseline implemented.

### Verification

- Passed PowerShell syntax parse for:
  - `scripts/start-myai.ps1`
- Passed LocalMode diagnostics on alternate ports:
  - `.\\start-myai.cmd doctor -LocalMode -PythonPort 8011 -JavaPort 8091`
  - Result: 0 failure(s), 0 warning(s).

### Phase 7.2 Unified Settings And Health Center

- Upgraded the settings page into a unified System Health Center.
- Added health summary cards for:
  - Java/Python observability reachability
  - model and eval configuration visibility
  - memory policy settings
  - knowledge-base file health
  - connector health
  - latest eval/eval gate status
- Added health center actions:
  - refresh health status
  - run quality gate
  - jump to observability
- Kept existing account information and memory settings controls on the same page.
- Added Java eval proxy endpoints:
  - `GET /eval/gates/config`
  - `POST /eval/gates/run`
  - `POST /eval/maintenance-report`
- Updated Phase 7 plan with 7.2 baseline implementation and deferred follow-ups.

### Verification

- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Startup Script Reliability Fix

- Reviewed startup entrypoints:
  - `start-myai.cmd`
  - `scripts/start-myai.ps1`
  - `scripts/README.md`
- Verified `start-myai.cmd` delegates to the PowerShell startup script.
- Found a stop reliability issue:
  - tracked launcher pids could be stopped while child Python/Java service processes continued listening on custom ports.
  - port process lookup was not reliable enough in this environment through `Get-NetTCPConnection` alone.
- Fixed `scripts/start-myai.ps1`:
  - added `netstat -ano` fallback for port owner detection.
  - made port cleanup retry for several rounds.
  - added a delay after stopping launcher pids before port cleanup.
- Updated startup README with custom-port stop guidance.

### Verification

- Checked default status:
  - Python on `8000` was already running.
  - Java on `8080` was stopped.
- Verified low-risk local-mode startup on alternate ports:
  - `.\\start-myai.cmd -LocalMode -NoPause -PythonPort 8011 -JavaPort 8091`
  - Python became ready on `127.0.0.1:8011`.
  - Java became ready on `127.0.0.1:8091`.
- Verified stop on alternate ports:
  - `.\\start-myai.cmd stop -PythonPort 8011 -JavaPort 8091`
  - Python and Java listening processes were released.
  - follow-up status reported both ports stopped.
  - `netstat` showed only `TIME_WAIT` entries and no listeners.

### Phase 7.1 Chat Page 2.0

- Upgraded the chat section into an Agent Cockpit layout:
  - conversation history
  - active chat
  - agent context panel
- Added agent context panel showing:
  - current agent status
  - latest trace step count
  - latest trace latency
  - memory influence count
  - knowledge citation count
  - trace step chips
  - contextual influence summary
  - quick links to memory, knowledge, task, and observability
- Added empty-state prompt suggestions for common workflows:
  - project status summary
  - daily work planning
  - citation-first knowledge QA
  - task execution with trace
- Upgraded chat message rendering:
  - user bubble
  - assistant label and bubble
  - trace/status chips
  - existing expandable trace panel retained
- Updated chat lifecycle behavior:
  - new conversation resets context panel
  - pending request shows busy agent status
  - completed response updates the panel from trace metadata
  - failed request shows error status and recovery hint
- Fixed conversation delete button/copy.
- Kept existing chat APIs unchanged.

### Verification

- Passed frontend inline script syntax check for:
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 7 Productization Planning

- Added Phase 7 productization and release hardening plan:
  - `docs/PHASE7_PRODUCTIZATION_PLAN.md`
- Planned Phase 7 around:
  - Chat Page 2.0
  - unified settings and health center
  - first-run setup and startup diagnostics
  - demo scenarios and guided workflows
  - screen-level product polish
  - privacy and safety review
  - release-quality documentation
  - packaging and release baseline
- Defined Phase 7 MVP closeout criteria.
- Recommended first implementation increment:
  - 7.1 Chat Page 2.0
- Updated `docs/ROADMAP.md` with the Phase 7 execution plan link and status.

### Verification

- Documentation-only planning update.
- No runtime tests were required.

### Phase 7 Step 0 Frontend Refresh Baseline

- Completed Phase 6 closeout confirmation before starting Phase 7-adjacent work.
- Added Phase 7 Step 0 frontend refresh document:
  - `docs/PHASE7_STEP0_FRONTEND_REFRESH.md`
- Rebuilt the login page:
  - two-column agent entry layout
  - CSS-only mascot illustration
  - mascot looks toward username input
  - mascot hides its eyes on password input
  - fixed Chinese copy
- Rebuilt the register page with the same visual language and mascot behavior.
- Rewrote shared auth CSS:
  - responsive layout
  - polished form controls
  - local-first CSS illustration without external images
- Refreshed the main workbench visual skin in `home.html` without changing business behavior:
  - modern sidebar
  - softer workspace surface
  - upgraded panels/cards
  - improved chat/message styling
  - upgraded inputs and action buttons
- Updated `docs/ROADMAP.md` to record Phase 7 Step 0.

### Verification

- Passed frontend inline script syntax check for:
  - `login.html`
  - `register.html`
  - `home.html`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 6.8 Production-Oriented Follow-Up And Phase 6 Closeout

- Completed the production-oriented follow-up for Phase 6.
- Updated the Phase 6 plan to mark 6.8 as baseline planned and closed.
- Added Phase 6 closeout document:
  - `docs/PHASE6_OBSERVABILITY_EVALUATION_CLOSEOUT.md`
- Closeout decision:
  - Phase 6 can be closed as baseline completed.
- Production-oriented follow-up is deferred to later hardening work:
  - cross-service trace identity
  - persisted normalized event store
  - observability privacy/redaction controls
  - OpenTelemetry or Prometheus-compatible metric exports
  - alerting and CI quality gates after thresholds stabilize
- Updated `docs/ROADMAP.md`:
  - Phase 6 marked baseline completed and closed
  - Phase 7 recommended as Productization And Release Hardening
- Recommended next priorities:
  - productized local onboarding
  - unified settings and health page
  - end-to-end demo scenarios
  - privacy and safety review
  - release-quality documentation

### Verification

- Documentation and roadmap closeout update.
- No runtime tests were required.

### Phase 6.7 Quality Gates And Maintenance Reports

- Added reusable quality gate module:
  - `app.evaluation.quality`
- Added default local gate checks for:
  - suite status
  - suite pass rate
  - failed reports
  - failed cases
  - failed case delta
  - pass-rate delta
- Gate config supports:
  - global pass-rate threshold
  - failed report/case thresholds
  - historical delta thresholds
  - per-report or per-domain pass-rate thresholds
- Added CLI gate mode:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --quality-gate --strict`
- Added Python API endpoints:
  - `GET /eval/gates/config`
  - `POST /eval/gates/run`
  - `POST /eval/maintenance-report`
- Maintenance reports now include:
  - eval summary
  - quality gate result
  - persisted eval history summary
  - actionable recommendations
- Added regression coverage for gate pass behavior, threshold failure details, and maintenance report API output.

### Verification

- Passed targeted quality gate and observability tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_unified_eval_runner tests.test_observability_summary`
- Passed local strict quality gate command with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --quality-gate --strict`
  - Result: 4 reports, 30/30 cases passed, 6/6 gate checks passed.

### Phase 6.6 Evaluation History Persistence

- Extended the observability eval run store from in-memory-only history to JSONL-backed local persistence:
  - `app.observability.store`
- Eval run history now persists to:
  - `myai-python-agent/.runtime/observability/eval_runs.jsonl`
- The store reloads recent eval runs on startup, so recent reports remain visible after service restart.
- `GET /observability/summary` now exposes:
  - latest eval run
  - previous eval run
  - storage metadata
  - latest-vs-previous delta for pass rate, failed reports, failed cases, total cases, duration, and status changes
- Added a store clear helper for tests and maintenance use.
- Added `.runtime/` to git ignore rules.
- Added regression coverage for persistence reload and delta calculation.

### Verification

- Passed Phase 6 observability and unified eval runner tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_summary tests.test_observability_events tests.test_unified_eval_runner`

### Phase 6.5 Observability Workbench UI

- Added Java proxy service for observability and eval APIs:
  - `PythonObservabilityService`
- Added Java proxy controllers:
  - `GET /observability/summary`
  - `GET /observability/events`
  - `GET /eval/reports`
  - `GET /eval/runs`
  - `POST /eval/runs`
- Added frontend sidebar tab:
  - `瑙傛祴`
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

### Verification

- Passed frontend inline script syntax check with bundled Node.js.
- Passed Python observability API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_summary tests.test_observability_events`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 6.4 Trace And Event Normalization

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

### Verification

- Passed observability events tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_events`
- Passed observability summary tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_summary`
- Passed Phase 6 regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_evaluation_registry tests.test_unified_eval_runner tests.test_observability_summary tests.test_observability_events`
- Passed MCP suite strict command with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite mcp --format markdown --strict`
- Passed all deterministic suites with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --strict`
  - Result: 4 reports, 30/30 cases passed.

### Phase 6.3 Metrics Snapshot And Runtime Counters

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

### Verification

- Passed observability summary tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_observability_summary`
- Passed evaluation registry, unified runner, and observability regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_evaluation_registry tests.test_unified_eval_runner tests.test_observability_summary`
- Passed MCP suite strict command with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite mcp --format markdown --strict`
- Passed all deterministic suites with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --strict`
  - Result: 4 reports, 30/30 cases passed.

### Phase 6.2 Unified Local Eval Runner

- Added unified local eval runner:
  - `app.evaluation.run`
- Supported suite selection:
  - `all`
  - `memory`
  - `task`
  - `knowledge`
  - `mcp`
  - individual report id
- Default `all` skips live-LLM reports for deterministic local runs.
- Added `--include-live` for reports such as memory LLM calibration.
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

### Verification

- Passed unified eval runner tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_unified_eval_runner`
- Passed MCP suite strict command with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite mcp --format markdown --strict`
- Passed all deterministic suites with:
  - `.\\.venv\\Scripts\\python.exe -m app.evaluation.run --suite all --format markdown --strict`
  - Result: 4 reports, 30/30 cases passed.
- Passed registry and report regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_evaluation_registry tests.test_unified_eval_runner`
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_report tests.test_task_runtime_report tests.test_knowledge_eval_report tests.test_mcp_eval_report`

### Phase 6.1 Unified Evaluation Registry

- Added Python evaluation registry:
  - `app.evaluation.registry`
- Registered existing reports:
  - `memory_governance`
  - `memory_llm_calibration`
  - `task_runtime`
  - `knowledge_retrieval`
  - `mcp_tool_ecosystem`
- Added common report metadata:
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
- Added regression coverage for registry discovery, report lookup, API list, API detail, and 404 behavior.

### Verification

- Passed evaluation registry tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_evaluation_registry`
- Passed existing report regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_report tests.test_task_runtime_report tests.test_knowledge_eval_report tests.test_mcp_eval_report`

### Phase 6 Observability And Evaluation Planning

- Added Phase 6 planning document:
  - `docs/PHASE6_OBSERVABILITY_EVALUATION_PLAN.md`
- Planned Phase 6 around:
  - unified evaluation registry
  - unified local eval runner
  - metrics snapshot and runtime counters
  - trace and event normalization
  - observability workbench UI
  - evaluation history persistence
  - quality gates and maintenance reports
  - production-oriented follow-up
- Recommended first implementation increment:
  - 6.1 Unified Evaluation Registry
- Updated `docs/ROADMAP.md` with Phase 6 status and execution plan link.

### Verification

- Documentation-only planning update.
- No runtime tests were required.

### Phase 5.9 Git Read-Only Connector And Phase 5 Closeout

- Added second real MCP-style connector:
  - `GitReadOnlyMCPClient`
- Registered read-only Git tools by default:
  - `mcp__git_readonly__status`
  - `mcp__git_readonly__log`
  - `mcp__git_readonly__show`
- Git connector settings:
  - default repo root: project workspace
  - override: `MYAI_MCP_GIT_ROOT`
  - disable: `MYAI_MCP_GIT_ENABLED=false`
  - git binary override: `MYAI_MCP_GIT_BIN`
- Added connector health checks for git executable availability and repository metadata.
- Added stable Git workflow registry entries:
  - `mcp_git_status_review`
  - `mcp_git_recent_history`
- Extended MCP eval fixture with:
  - Git connector health
  - Git status execution trace
- Closed Phase 5 as baseline completed.
- Added closeout document:
  - `docs/PHASE5_MCP_TOOL_ECOSYSTEM_CLOSEOUT.md`
- Updated `docs/ROADMAP.md` to mark Phase 5 as baseline completed and closed.

### Verification

- Passed Git connector test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge.MCPBridgeTest.test_git_readonly_connector_reports_status_and_log`
- Passed Git workflow execution test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_mcp_git_workflows_are_registered_and_executable`
- Passed task tools API connector summary smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed MCP eval report tests and strict report with 9/9 cases:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_eval_report`
  - `.\\.venv\\Scripts\\python.exe -m app.task.evaluation.mcp_report --format markdown --strict`
- Passed MCP bridge and workflow regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge tests.test_mcp_eval_report`
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_mcp_git_workflows_are_registered_and_executable tests.test_api.MyAITestCase.test_mcp_filesystem_workflows_are_registered_and_executable tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed frontend inline script syntax check with bundled Node.js.

### Phase 5.8 Workflow Integration

- Added MCP-aware argument extraction for filesystem MCP tools:
  - `read_text`
  - `list_files`
  - `search_names`
- Added stable MCP workflow registry entries:
  - `mcp_filesystem_read_summary`
  - `mcp_filesystem_search_plan`
- Workflows require MCP tools by stable registry names:
  - `mcp__filesystem_readonly__read_text`
  - `mcp__filesystem_readonly__search_names`
- Read workflow supports project/local file read and summary-style output.
- Search workflow supports project/local filename search and planning-oriented match output.
- Task execution keeps existing MCP policy metadata and `task.mcp_call.completed` timeline events.
- Added regression coverage for workflow listing, workflow matching, MCP tool args extraction, execution result, and timeline event presence.

### Verification

- Passed MCP filesystem workflow execution test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_mcp_filesystem_workflows_are_registered_and_executable`
- Passed MCP bridge and MCP eval report regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge tests.test_mcp_eval_report`
- Passed workflow endpoint and task tools API smoke tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_workflows_endpoint_lists_registry tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed strict MCP report with:
  - `.\\.venv\\Scripts\\python.exe -m app.task.evaluation.mcp_report --format markdown --strict`

### Phase 5.7 MCP Eval Fixture And Report

- Added MCP eval fixture:
  - `tests/fixtures/mcp_eval.json`
- Added local MCP report runner:
  - `app.task.evaluation.mcp_report`
- Fixture coverage includes:
  - descriptor registration and schema conversion
  - read-only policy mapping
  - destructive policy hosted-mode blocking
  - connector health/settings inspection
  - successful MCP execution trace
  - filesystem path escape fail-closed behavior
  - disabled connector exclusion
- Report output includes total/pass/fail/pass rate, coverage by case type, per-case key result, and expectation errors.
- Added regression coverage for fixture pass/fail and Markdown rendering.

### Verification

- Passed MCP eval report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_eval_report`
- Passed strict MCP report with:
  - `.\\.venv\\Scripts\\python.exe -m app.task.evaluation.mcp_report --format markdown --strict`
- Passed MCP bridge regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`
- Passed task tools API connector summary smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`

### Phase 5.6 Connector Settings And Health UI

- Added connector inspection metadata for `ReadOnlyFilesystemMCPClient`:
  - enabled state
  - health status and message
  - configured root names and resolved paths
  - root availability/readability
  - settings environment variable names
  - risk summary
- Added `TaskService.list_connectors()` to aggregate MCP tools by connector/server id.
- Extended `GET /task/tools` with:
  - `summary.connectors`
  - `summary.healthy_connectors`
  - `connectors`
- Frontend task tool directory now renders connector settings and health cards.
- Connector cards show enabled/healthy state, root paths, tool count, risk level, hosted-mode status, and raw connector tools.
- Added regression coverage for connector health/settings payload and task tools API connector summary.

### Verification

- Passed MCP bridge and connector health tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`
- Passed task tools API connector summary smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed frontend inline script syntax check with:
  - bundled Node.js `vm.Script` check for `home.html`

### Phase 5.5 First Real Connector: Filesystem Read-Only

- Added the first real MCP-style connector:
  - `ReadOnlyFilesystemMCPClient`
- Registered read-only filesystem tools by default:
  - `mcp__filesystem_readonly__list_files`
  - `mcp__filesystem_readonly__read_text`
  - `mcp__filesystem_readonly__search_names`
- Connector root behavior:
  - defaults to the repository workspace
  - can be overridden with `MYAI_MCP_FILESYSTEM_ROOTS`
  - can be disabled with `MYAI_MCP_FILESYSTEM_ENABLED=false`
- Added path containment checks using resolved paths before any read/list/search access.
- Path escape attempts fail closed with `path_outside_allowed_roots`.
- Connector tools are mapped as `filesystem/read`, read-only, and disabled in hosted mode.
- Added regression coverage for list/read/search and path escape rejection.

### Verification

- Passed MCP bridge, trace, and filesystem connector tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`
- Passed task tools API smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`

### Phase 5.4 MCP Execution Events And Trace

- Added MCP call metadata at the adapter boundary:
  - call status
  - call started/finished timestamps
  - call latency
  - server id
  - external tool name
  - registry tool name
  - adapter exception category
- Added task runtime MCP call events:
  - `task.mcp_call.completed`
  - `task.mcp_call.failed`
- MCP call events are written to:
  - the full task run timeline
  - the owning step event list
- Frontend task timeline now shows a compact MCP summary for MCP call events.
- Added regression coverage for TaskService MCP execution trace.

### Verification

- Passed MCP bridge and execution trace tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`
- Passed task tools API smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed frontend inline script syntax check with:
  - bundled Node.js `vm.Script` check for `home.html`

## 2026-06-24

### Phase 5.3 MCP Tool Policy And Permission Mapping

- Added MCP policy mapper:
  - `map_mcp_tool_policy`
- External MCP metadata now maps into MyAI `ToolPolicy` using:
  - descriptor risk fields
  - server defaults
  - `riskLevel` / `risk_level`
  - `readOnlyHint`
  - `destructiveHint`
  - `openWorldHint`
  - capabilities/categories
  - timeout/retry annotations
- Added mapped risk categories:
  - `safe`
  - `network`
  - `filesystem/read`
  - `filesystem/write`
  - `browser/session`
  - `account/action`
  - `sensitive`
  - `destructive`
  - `unknown`
- Conservative defaults:
  - unknown risk requires confirmation
  - destructive/write/browser risks are blocked in hosted mode
  - destructive/write/account/sensitive risks disable retry
- Tool inspection now exposes `policy_metadata`.
- Frontend tool directory now renders policy mapping reasons.
- Added regression coverage for read-only, network, destructive, unknown, and server-default policy mapping.

### Verification

- Passed MCP bridge and policy mapping tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`
- Passed task tools API smoke test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed frontend inline script syntax check with:
  - bundled Node.js `vm.Script` check for `home.html`

### Phase 5.2 Unified Tool Registry And Inspection

- Added unified tool inspection payload from `TaskService.list_tools()`.
- Added Python task tools endpoint:
  - `GET /task/tools`
- Added Java proxy endpoint:
  - `GET /task/tools`
- Tool inspection includes:
  - source (`local` or `mcp`)
  - MCP server id and external tool name
  - description
  - status and health
  - policy metadata
  - input schema
  - required args
  - trigger metadata
- Frontend task workbench now includes a tool directory panel.
- Tool cards show local vs MCP source, risk level, confirmation requirement, required args, and raw schema.
- Added regression coverage for local tool API listing and MCP inspection metadata.

### Verification

- Passed target Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge tests.test_api.MyAITestCase.test_task_tools_endpoint_lists_local_tools`
- Passed frontend inline script syntax check with bundled Node.js.
- Passed Python MCP/task/API regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge tests.test_task_runtime_report tests.test_api`
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 5.1 MCP Bridge MVP

- Added MCP bridge primitives:
  - `MCPServerConfig`
  - `MCPToolDescriptor`
  - `MCPToolAdapter`
  - `MCPToolRegistryLoader`
  - `MockMCPClient`
- MCP descriptors can now be converted into existing MyAI `Tool` instances.
- MCP tool registry names are namespaced as `mcp__server__tool`.
- Adapter preserves tool description, JSON input schema, timeout/retry policy, risk level, and confirmation requirement.
- Mock MCP tools execute through the existing `ToolExecutor`.
- Existing argument validation and permission-required behavior are reused by MCP tools.
- Added regression coverage for schema conversion, mock execution, validation failure, permission blocking, and disabled server exclusion.

### Verification

- Passed MCP bridge tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_mcp_bridge`

### Phase 4 Closeout And Phase 5 Planning

- Closed Phase 4 as baseline complete.
- Added Phase 4 closeout document:
  - `docs/PHASE4_KNOWLEDGE_CLOSEOUT.md`
- Confirmed all Phase 4 increments are baseline implemented:
  - 4.1 Knowledge Metadata And Ingestion Report
  - 4.2 Citation-First Query Results
  - 4.3 Hybrid Retrieval MVP
  - 4.4 Reranking And Retrieval Policy
  - 4.5 Structured Document Summary
  - 4.6 Document QA Mode
  - 4.7 Knowledge In Chat: Answer Citations
  - 4.8 Knowledge Maintenance
  - 4.9 Knowledge Eval And Report
  - 4.10 Knowledge-Aware Task Workflows
- Planned Phase 5 as MCP Tool Ecosystem And External Integrations.
- Added Phase 5 plan document:
  - `docs/PHASE5_MCP_TOOL_ECOSYSTEM_PLAN.md`
- Updated `docs/ROADMAP.md` to mark Phase 2, Phase 3, and Phase 4 as baseline completed, and Phase 5 as next.
- Recommended first Phase 5 increment:
  - 5.1 MCP Bridge MVP

### Verification

- Documentation-only planning and closeout update.
- No runtime tests were required.

### Phase 4.10 Knowledge-Aware Task Workflows

- Added `knowledge_admin` task tool for knowledge-aware workflows:
  - document-scoped QA
  - structured study notes
  - Q&A card generation
  - two-document comparison
  - dry-run knowledge maintenance
  - knowledge eval report
- Registered knowledge workflows in the Phase 3 workflow registry:
  - `knowledge_document_qa`
  - `knowledge_study_notes`
  - `knowledge_qa_cards`
  - `knowledge_document_compare`
  - `knowledge_maintenance`
  - `knowledge_eval_report`
- Kept existing `knowledge_file_summary` workflow available through `file_summary`.
- Knowledge workflow outputs preserve citations, selected hits, answer status, and maintenance/eval summaries where applicable.
- Knowledge maintenance workflow defaults to dry-run to avoid mutating the index through automatic task routing.
- Added regression coverage for direct tool operations, workflow matching, executable task workflow, task timeline completion, and citation-bearing task output.

### Verification

- Passed targeted knowledge workflow tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_knowledge_admin_tool_workflows tests.test_api.MyAITestCase.test_knowledge_workflows_are_registered_and_executable`
- Passed Python API, task runtime report, and knowledge eval report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report tests.test_knowledge_eval_report`

### Phase 4.9 Knowledge Eval And Report

- Added knowledge evaluation fixture:
  - upload parse success
  - duplicate detection
  - exact keyword retrieval
  - deterministic semantic retrieval
  - file-filtered retrieval
  - citation completeness
  - insufficient-evidence document QA
  - Chinese and English mixed query
- Added local knowledge report runner:
  - `.\\.venv\\Scripts\\python.exe -m app.knowledge.evaluation.report --format markdown --strict`
- Report output includes:
  - total/pass/fail/pass rate
  - hit@k
  - expected file found
  - citation completeness
  - average latency
  - coverage by case type
  - per-case retrieval mode, citation id, latency, and errors
- Added deterministic eval embedding to make semantic retrieval regressions measurable without external model calls.
- Added regression coverage for fixture pass/fail and Markdown rendering.

### Verification

- Passed strict knowledge eval report with:
  - `.\\.venv\\Scripts\\python.exe -m app.knowledge.evaluation.report --format markdown --strict`
- Passed Python API, task runtime report, and knowledge eval report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report tests.test_knowledge_eval_report`

### Phase 4.8 Knowledge Maintenance

- Added knowledge maintenance API:
  - Python `POST /knowledge/maintenance`
  - Java proxy `POST /knowledge/maintenance`
- Maintenance supports:
  - dry-run health check
  - apply-mode repair
  - optional single-file scope
  - optional rebuild mode
- Maintenance report includes:
  - per-file stored-file status
  - expected vs actual vector chunk counts
  - missing chunk ids
  - orphan chunk ids
  - duplicate content-hash groups
  - planned/completed actions
- Apply mode can reindex missing chunks from stored files, rebuild selected file chunks, delete orphan vector chunks, and refresh file metadata/profile.
- Frontend knowledge page now has health check, repair, and selected-file rebuild controls with an inline maintenance report.
- Added regression coverage for missing chunk repair, orphan cleanup, and retrieval after repair.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend inline script syntax check with bundled Node.js.
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

### Phase 4.7 Knowledge In Chat: Answer Citations

- Added chat-oriented knowledge retrieval payloads with:
  - prompt snippets carrying citation ids
  - structured citations
  - selected hits
  - retrieval explanations
- Chat `knowledge.retrieve` trace step now includes:
  - `snippets`
  - `citations`
  - `retrieval_explanations`
  - `hits`
- Prompt knowledge snippets now include citation ids such as `[file#chunk]`.
- Frontend chat trace now renders knowledge citations separately from memory citations.
- Frontend chat trace now renders knowledge retrieval explanation cards for selected document chunks.
- Added regression coverage for knowledge citations in chat trace.

### Verification

- Passed Python chat/API regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend inline script syntax check with bundled Node.js.
- Passed Java service tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd -q test`

## 2026-06-23

### Phase 4.6 Document QA Mode

- Added document-scoped QA support:
  - Python `POST /knowledge/qa`
  - Java proxy `POST /knowledge/qa`
- QA requests require a selected `file_id`.
- QA reuses hybrid retrieval, citations, and rerank/final-selection policy with a mandatory file filter.
- Added extractive answer composition from selected evidence chunks.
- Added first-class answer states:
  - `answered`
  - `not_enough_evidence`
  - `empty_question`
- Evidence hits and citations are returned only when enough selected-document evidence is found.
- Frontend knowledge panel now includes a "鏂囨。闂瓟" button that asks against the selected file.
- Added regression coverage for:
  - file-scoped QA without unrelated document leakage
  - not-enough-evidence responses

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 4.5 Structured Document Summary

- Added deterministic `document_profile` generation during knowledge upload.
- Profile fields include:
  - title
  - short summary
  - outline
  - keywords
  - detected topics
  - important passages
  - possible questions
  - document language
  - profile stats
  - summary method
- Kept the existing `summary` field backward compatible by deriving it from `document_profile.short_summary`.
- File listing and duplicate upload responses now expose `document_profile`.
- File summary tool now returns:
  - `document_profile`
  - `outline`
  - `possible_questions`
  - `document_language`
- File summary tool can build a profile on read for legacy index entries that do not yet store profile metadata.
- Java file DTOs accept profile payloads.
- Frontend upload results and file cards now show a collapsible document profile panel.
- Added regression coverage for upload/list/duplicate profile fields and structured file summary tool output.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 4.4 Reranking And Retrieval Policy

- Split knowledge query processing into:
  - candidate retrieval
  - candidate hit construction
  - final selection
- Candidate retrieval now over-fetches vector candidates and merges keyword candidates before final selection.
- Added deterministic rerank scoring with:
  - hybrid retrieval score
  - query term coverage
  - chunk length quality
  - duplicate penalty
  - same-file diversity penalty
- Added final selection policy with:
  - max context token budget
  - max chunks per file
  - relaxed fallback when diversity constraints would under-fill results
- Query hits now expose:
  - `candidate_rank`
  - `final_rank`
  - `rerank_score`
  - `query_coverage`
  - `length_quality`
  - duplicate/diversity penalties
  - `selection_status`
  - `selection_reason`
  - `selection_explanation`
- Java query DTOs accept final selection metadata.
- Knowledge query result cards show final rank, rerank score, selection reason, and rerank factors.
- Added regression coverage for selection metadata and same-file diversity.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 4.3 Hybrid Retrieval MVP

- Added hybrid candidate retrieval for knowledge queries:
  - vector candidates from Chroma similarity search
  - keyword candidates from stored chunk documents
- Keyword retrieval is scoped by `user_id` and optional `file_id`.
- Added explainable fusion scoring with:
  - vector score
  - keyword score
  - filename score
  - recency score
  - file filter score
- Query hits now expose:
  - `retrieval_mode`
  - `retrieval_score`
  - `retrieval_explanation`
  - individual retrieval factor scores
- Java query DTOs now accept retrieval explanation payloads.
- Knowledge query result cards show retrieval score, mode, factors, and reason.
- Added regression coverage for exact-keyword fallback with `top_k=1`.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

## 2026-06-22

### Phase 4.2 Citation-First Query Results

- Added citation-first fields to knowledge query hits:
  - `citation_id`
  - `snippet`
  - nested `citation`
- The nested citation object includes:
  - file and chunk identity
  - character span
  - page and section placeholders
  - score
  - token estimate
  - content hash
  - snippet
- Java query DTOs now accept citation payloads.
- Knowledge query result cards now show citation id, source label, score, snippet, and a collapsible raw chunk.
- Added regression coverage for citation payload consistency.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

## 2026-06-18

### Phase 4.1 Knowledge Metadata And Ingestion Report

- Added knowledge file metadata:
  - `size_bytes`
  - `content_hash`
  - `parser`
  - `parser_version`
  - `text_length`
  - `embedding_provider`
  - `embedding_model`
  - `ingestion_status`
  - `ingestion_warnings`
- Added upload `ingestion_report`.
- Added duplicate upload detection by SHA-256 content hash.
- Added span-aware chunking while preserving the old `chunk_text()` API.
- Added chunk metadata:
  - `char_start`
  - `char_end`
  - `page_start`
  - `page_end`
  - `section_title`
  - `token_estimate`
- Query hits now return chunk source span metadata.
- Java knowledge DTOs accept the new metadata.
- Java knowledge upload result and file cards show ingestion status and file size.
- Added regression coverage for ingestion reports, list metadata, duplicate detection, and chunk spans.

### Verification

- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 4 Knowledge Workbench Planning

- Started Phase 4 planning for the knowledge base module.
- Added an overall plan document:
  - `docs/PHASE4_KNOWLEDGE_BASE_PLAN.md`
- Planned the knowledge module upgrade around:
  - ingestion metadata and reports
  - citation-first query results
  - hybrid retrieval
  - reranking and retrieval policy
  - structured document summaries
  - document QA mode
  - chat answer citations
  - knowledge maintenance
  - knowledge eval/report
  - knowledge-aware task workflows
- Recommended the first implementation increment as:
  - 4.1 Knowledge Metadata And Ingestion Report

### Phase 3.10 Runtime Evaluation And Reports

- Added task runtime eval fixture:
  - `tests/fixtures/task_runtime_eval.json`
- Added local task runtime report runner:
  - `python -m app.task.evaluation.runtime_report --format markdown --strict`
- Fixture coverage includes:
  - no-tool task
  - single safe tool task
  - multi-step chained task
  - invalid tool args
  - permission required
  - retryable failure recovered by retry
  - memory-aware planning
- Report output includes:
  - total/pass/fail/pass rate
  - per-case status, plan source, tool list, latency, and expectation errors
  - tool call count, success rate, and average latency
- Added an eval-only flaky retry tool inside the report runner.
- `StatsManager` now tracks `workflow_hits` separately from no-tool hits.
- Added regression coverage for fixture pass/fail and Markdown rendering.

### Verification

- Ran strict runtime report with:
  - `.\\.venv\\Scripts\\python.exe -m app.task.evaluation.runtime_report --format markdown --strict`
- Passed Python API and runtime report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_task_runtime_report`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.9 Workflow Registry

- Added a task workflow registry baseline.
- Added workflow model primitives:
  - `WorkflowDefinition`
  - `WorkflowStepTemplate`
  - `WorkflowRegistry`
- Added default workflow definitions for:
  - memory policy inspection
  - memory eval report
  - memory maintenance
  - knowledge file summary
  - environment diagnostics
- `ToolPlanner` now tries workflow matching before multi-step/rule/LLM planning.
- Workflow plans now include:
  - `source="workflow"`
  - `plan.workflow`
- Added Python workflow inspection endpoint:
  - `GET /task/workflows`
- Added Java proxy endpoint:
  - `GET /task/workflows`
- Added regression coverage for workflow registry inspection and workflow-based planning.

### Verification

- Passed Python API regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.8 Outcome Memory And Task Experience

- Added governed task outcome memory writing.
- Added `MemoryService.process_task_outcome` so task-derived memories reuse existing governance, dedup, conflict, and pending behavior.
- Extended memory source references with:
  - `task_run_id`
  - `step_id`
- Task runtime now emits:
  - `task.outcome_memory.started`
  - `task.outcome_memory.completed`
- Successful tool tasks can create pending `task_workflow` memories.
- Failed tool steps can create pending `tool_failure` memories.
- No-tool and cancelled tasks remain non-writing in the MVP.
- Java task workbench now shows task outcome memory write status.
- Added regression coverage for outcome memory source references and events.

### Verification

- Passed Python API regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.7 Memory-Aware Task Planning

- Added memory retrieval before task planning when a task has `user_id`.
- Reused governed memory retrieval explanations from Phase 2.
- Passed compact memory summaries into the planner as short context.
- Added memory citations to task plan metadata under `memory_context`.
- Added task runtime events:
  - `task.memory_retrieval.started`
  - `task.memory_retrieval.completed`
- Shared one `MemoryService` between task planning and `memory_admin`.
- Added a planning memory citation panel to the Java task workbench.
- Added regression coverage for memory-aware planning context, citations, and events.

### Verification

- Passed Python API regression tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.6 Task UI 2.0

- Added task run listing support:
  - Python `GET /task/runs`
  - Java proxy `GET /task/runs`
- Upgraded the Java task page into a compact task workbench.
- The workbench now includes:
  - quick synchronous execution
  - background execution
  - cancellation
  - recent task run list
  - selected task detail panel
  - status pills
  - run summary fields
  - step cards
  - execution timeline
  - result summary and raw details toggle
- Synchronous task execution now refreshes the final run snapshot through the run lookup API.
- Background task polling now keeps both the detail panel and recent run list updated.
- Added API regression coverage for user-scoped task run listing.

### Verification

- Passed targeted Python task run list tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_run_list_endpoint_returns_user_runs tests.test_api.MyAITestCase.test_background_task_endpoint_starts_and_can_be_fetched`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.5 Background Task Mode

- Added local background execution for task runs.
- Added Python task runtime endpoints:
  - `POST /task/runs`
  - `GET /task/runs/{task_run_id}`
  - `POST /task/runs/{task_run_id}/cancel`
- Existing synchronous `POST /task` remains available.
- `TaskRun` now supports:
  - `cancel_requested`
  - `task.queued`
  - `task.cancel_requested`
  - `task.cancelled`
- Cancellation is cooperative and happens between steps.
- Added Java task proxy endpoints for:
  - background start
  - run lookup
  - cancellation
- Updated the Java task panel with:
  - background execution button
  - cancel button
  - polling-based run refresh
  - compact run snapshot and timeline rendering
- Added tests for:
  - background task start and fetch
  - cancellation between steps

### Verification

- Passed targeted Python background task tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_background_task_endpoint_starts_and_can_be_fetched tests.test_api.MyAITestCase.test_background_task_can_be_cancelled_between_steps`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.4 Retry Timeout Recovery

- Connected `ToolPolicy.timeout_seconds` to executor behavior.
- Connected `ToolPolicy.retry_count` to executor behavior.
- Added executor-level timeout fallback using a future timeout.
- Added conservative retry classification:
  - retry transient-looking timeout, connection, network, rate-limit, and 5xx-style failures
  - do not retry sensitive or destructive tools
- Tool result metadata now includes:
  - `attempt`
  - `max_attempts`
  - `retry_count`
  - `timeout_seconds`
  - `retryable`
  - `recovery_attempted`
  - `recovery_status`
  - `recovery_recommendation`
  - `errors`
- Task runtime now emits:
  - `task.step.recovery`
- Added tests for:
  - retryable tool failure that succeeds on retry
  - timeout failure with recovery recommendation

### Verification

- Passed targeted Python retry/timeout tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_executor_retries_retryable_tool_failure tests.test_api.MyAITestCase.test_task_executor_timeout_produces_recovery_recommendation tests.test_api.MyAITestCase.test_task_tool_policy_records_allowed_decision tests.test_api.MyAITestCase.test_task_tool_policy_blocks_confirmation_required_tool`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.3 Tool Policy And Permission Governance

- Added baseline `ToolPolicy` support to task tools.
- Policy fields:
  - `risk_level`
  - `timeout_seconds`
  - `retry_count`
  - `requires_confirmation`
  - `allowed_in_local`
  - `allowed_in_hosted`
- `ToolExecutor` now evaluates tool policy after argument validation and before execution.
- Confirmation-required tools fail closed when no confirmation is present.
- Tool results now include policy metadata:
  - `tool_policy`
  - `policy_decision`
  - `permission_required`
- Task runtime now emits policy events:
  - `task.tool_policy.allowed`
  - `task.tool_policy.permission_required`
  - `task.tool_policy.blocked`
- Added baseline policy classifications:
  - `web_search` and `weather`: network
  - `file_summary`: filesystem/read
  - `system_info`: safe/local
  - `memory_admin`: sensitive
- `memory_admin` now requires confirmation for:
  - `maintenance`
  - `update_settings`
- Added tests for:
  - allowed safe tool policy decisions
  - confirmation-required sensitive tool blocking

### Verification

- Passed targeted Python task policy tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_tool_policy_records_allowed_decision tests.test_api.MyAITestCase.test_task_tool_policy_blocks_confirmation_required_tool tests.test_api.MyAITestCase.test_task_endpoint_runs_memory_admin_policy_inspection`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.2 Runtime Event Timeline And Trace Unification

- Added append-only task runtime events.
- Added `TaskEvent` records with:
  - `event_id`
  - `type`
  - `timestamp`
  - `status`
  - `step_id`
  - `message`
  - `metadata`
- `TaskRun` now exposes an `events` timeline.
- `TaskStepRun` now carries step-local events.
- Baseline emitted event types:
  - `task.created`
  - `task.planning.started`
  - `task.planning.completed`
  - `task.running`
  - `task.step.started`
  - `task.step.completed`
  - `task.step.failed`
  - `task.completed`
  - `task.failed`
- Python `/task` responses now include `events`.
- `GET /task/runs/{task_run_id}` returns the same event timeline for inspection.
- Java `TaskResponse` now accepts `events`.
- Java task UI now renders a compact execution timeline.
- Extended runtime tests to verify successful and failed task event sequences.

### Verification

- Passed targeted Python task runtime tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_runtime_run_can_be_fetched_after_sync_task tests.test_api.MyAITestCase.test_task_runtime_marks_missing_tool_step_failed`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 3.1 Task Runtime State Machine MVP

- Started Phase 3: Agent Runtime And Task System 2.0.
- Added an in-memory task runtime state machine for synchronous task execution.
- Added Python runtime models:
  - `TaskRun`
  - `TaskStepRun`
  - `TaskRunStore`
- Existing `TaskService.handle_task` now creates a task run and updates lifecycle status during execution.
- Supported statuses in the baseline:
  - `queued`
  - `planning`
  - `running`
  - `succeeded`
  - `failed`
- Python `/task` responses now include:
  - `task_run_id`
  - `status`
- Added Python run lookup endpoint:
  - `GET /task/runs/{task_run_id}`
- Added Java DTO/service/controller support for:
  - `task_run_id`
  - `status`
  - `GET /task/runs/{taskRunId}`
- Updated the Java task panel to show run id and final status after execution.
- Added regression coverage for:
  - completed synchronous run lookup
  - missing-tool step failure state

### Verification

- Passed targeted Python task runtime tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_runtime_run_can_be_fetched_after_sync_task tests.test_api.MyAITestCase.test_task_runtime_marks_missing_tool_step_failed`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

## 2026-06-03

### Planning

- Created the post-graduation evolution roadmap.
- Selected Phase 1, Agent Runtime And Execution Trace, as the first implementation direction.

### Phase 1 Initial Scope

- Add lightweight runtime trace models in the Python agent.
- Make `/chat` return trace metadata together with the existing reply.
- Extend Java chat DTOs so the new metadata can cross the Java service boundary.
- Keep current chat behavior unchanged.

### Notes

- Persistence and front-end visualization are intentionally left for the next increment.
- This first increment is designed to be low risk: existing clients can continue reading `reply`.

### Implemented

- Added Python runtime trace classes: `AgentRun` and `AgentStep`.
- Added Python chat response schemas for `run_id` and `trace`.
- Instrumented the Python chat pipeline with steps for:
  - context history loading
  - task handling
  - memory write
  - memory retrieval
  - knowledge retrieval
  - memory maintenance
  - prompt building
  - LLM generation
  - context update
- Extended Java chat DTOs to receive `run_id` and `trace`.
- Updated the Java Python proxy so the full chat response crosses the service boundary.

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Java tests were initially blocked by an invalid `JAVA_HOME`.

### Environment And Git Setup

- Found a valid local JDK at `<JAVA_HOME>`.
- Updated the user-level `JAVA_HOME` to `<JAVA_HOME>`.
- Updated the user-level `Path` so `%JAVA_HOME%\\bin` is available.
- Verified Maven Wrapper with the corrected JDK:
  - `.\\mvnw.cmd -version`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2.15 Confidence-Aware Multi-Candidate Pending Behavior

- Added per-write extraction batch metadata for multi-candidate memory writes:
  - `extraction_batch_id`
  - `candidate_index`
  - `candidate_count`
  - `multi_candidate`
- Multi-candidate writes now use a stricter confidence gate:
  - single-candidate low-confidence threshold remains `0.70`
  - multi-candidate pending threshold is `0.85`
- A multi-candidate memory with confidence below `0.85` is routed to pending with an explicit `review_reason`.
- Python memory API exposes the batch/candidate metadata.
- Java memory DTO accepts the new fields.
- Frontend memory cards show candidate position such as `candidate锛?/3`.
- Added tests covering:
  - API batch metadata visibility for rule-based multi-candidate writes.
  - LLM multi-candidate extraction where a high-confidence candidate is accepted and a medium-confidence candidate becomes pending.

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.16 Memory Observability UI

- Upgraded memory cards with a collapsible "娌荤悊涓庡璁¤鎯? panel.
- The detail panel now shows:
  - governance status, review reason, confidence, sensitivity, source, and source reference
  - lifecycle fields such as observed time, valid range, current/history state, access count, and edit metadata
  - multi-candidate batch id and candidate position
  - dedup merge audit summary and merge event details
- Upgraded chat trace memory retrieval explanations from plain text blocks into selected/filtered cards.
- Retrieval explanation cards now show final score, reason, similarity, confidence, review status, sensitivity, source, and content.
- Kept the default memory card compact; observability details are available on demand.

### Verification

- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed inline script syntax check with bundled Node.js.

### Phase 2.17 Confidence Calibration Baseline

- Added a governance-level confidence calibration step.
- Existing `confidence` remains the raw extractor confidence for backward compatibility.
- New metadata fields:
  - `raw_confidence`
  - `calibrated_confidence`
  - `confidence_calibration_reason`
  - `confidence_calibration_factors`
- Calibration currently considers:
  - memory slot
  - source
  - extraction method
  - multi-candidate extraction
  - weak or inferred language
  - sensitivity
- Review/pending classification now uses `calibrated_confidence`.
- Memory retrieval now uses calibrated confidence for ranking while preserving raw confidence in explanation factors.
- API schema, Java DTO, trace explanation UI, and memory observability panel expose calibrated confidence.
- Added tests for calibration metadata and LLM multi-candidate confidence behavior.

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`
- Passed inline script syntax check with bundled Node.js.

### Phase 2.18 Calibration Policy Configuration And Eval Expansion

- Moved calibration weights out of governance constants and into slot/source policy configuration.
- `SlotDefinition` now carries `confidence_adjustment`.
- Added `ConfidenceCalibrationPolicy` for:
  - source adjustments
  - extraction method adjustments
  - unknown source/method fallback
  - multi-candidate adjustment
  - weak-signal adjustment
  - sensitive-memory adjustment
- `enrich_metadata_with_slot_policy` now attaches `slot_confidence_adjustment` to memory metadata.
- `calibrate_confidence` now reads slot/source/method weights from policy configuration.
- Rebuilt the slot registry with stable Unicode escapes for Chinese aliases, reducing future edit friction around encoding.
- Expanded `memory_governance_eval.json` with calibration expectations:
  - explicit major is up-calibrated
  - LLM implied preference is down-calibrated and pending
  - write cases now assert calibration factors and calibrated confidence ranges
- Added eval tests that check raw confidence, calibrated confidence, review status, and factor provenance.

### Verification

- Validated eval fixture JSON with:
  - `.\\.venv\\Scripts\\python.exe -m json.tool tests\\fixtures\\memory_governance_eval.json`
- Passed targeted memory tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval tests.test_api tests.test_memory_llm_extractor`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.19 Calibration Report

- Added a local calibration report command:
  - `.\\.venv\\Scripts\\python.exe -m app.memory.evaluation.governance_report --format markdown --strict`
- The report reuses `tests/fixtures/memory_governance_eval.json`.
- Reported fields include:
  - case id and fixture section
  - pass/fail
  - raw confidence
  - actual calibrated confidence
  - expected confidence range
  - delta/margin against the expected range
  - review status
  - calibration factors
- Supports JSON and Markdown output:
  - `--format markdown`
  - `--format json`
- Supports `--output` for saving reports and `--strict` for non-zero exit on failures.
- Added unit tests for report summary, expected/actual delta, and Markdown table rendering.

### Verification

- Ran report command with:
  - `.\\.venv\\Scripts\\python.exe -m app.memory.evaluation.governance_report --format markdown --strict`
- Passed targeted report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_report tests.test_memory_governance_eval`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.20 Memory Governance Eval Expansion

- Expanded `memory_governance_eval.json` beyond the original write/dedup/conflict/citation/calibration cases.
- Added coverage for:
  - common phrase and ambiguous question should-not-write boundaries
  - sensitive governance cases for explicit secrets and personal-sensitive identifiers
  - rule-based multi-candidate extraction
  - fixture-backed LLM-style multi-candidate extraction with pending behavior
  - temporal location correction preserving history
  - ambiguous opinion down-calibration
- Added a fixture-backed structured extractor in the eval tests so multi-candidate LLM-like behavior can be tested without a live model.
- Added eval assertions for:
  - candidate count and written count
  - per-candidate slot/value/status
  - calibrated confidence ranges
  - multi-candidate metadata
  - sensitive category and review reason
  - temporal current/history links
- Updated the calibration report summary to include fixture coverage by section.

### Verification

- Validated fixture JSON with:
  - `.\\.venv\\Scripts\\python.exe -m json.tool tests\\fixtures\\memory_governance_eval.json`
- Passed targeted eval/report tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval tests.test_memory_governance_report`
- Ran calibration report with:
  - `.\\.venv\\Scripts\\python.exe -m app.memory.evaluation.governance_report --format markdown --strict`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Automatic Pending Classification

- Added automatic review classification to memory governance metadata.
- Memories are now marked `review_status=pending` when:
  - sensitivity is `sensitive`
  - confidence is below `0.70`
  - the memory is a low-importance `opinion` or `decision`
- Added `review_reason` so users can see why a memory was accepted or sent to the confirmation queue.
- Extended Python response schema, Java DTO, and frontend memory cards to include `review_reason`.
- Kept high-confidence personal facts and preferences accepted by default.

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

## 2026-06-30 Memory Frontend Write/Query Fix

### Context

- Frontend memory smoke test showed two symptoms:
  - manual write displayed success, but the memory profile did not show the new item;
  - memory query displayed a generic retry error.

### Findings

- This was not simply caused by local auth mode.
- Java `/memory/write` discarded the Python memory governance result and always returned a fixed success string.
- The frontend treated any `2xx` write response as success, so `writer rejected input`, pending candidates, and other non-persisted outcomes were invisible to the user.
- Runtime `/memory/query` failed because `.env` enabled the Volcengine embedding provider. When the embedding request failed, Python returned `500`; Java then entered an error dispatch path that surfaced as a `/login` redirect in local mode.
- The first embedding fallback used the default 64-dimensional stub vector, while the existing Volcengine Chroma collection expected 2048 dimensions. This allowed empty-query fallback but failed writes that needed to add vectors.
- After Java was packaged, the startup script switched to jar mode and exposed another local startup issue: PATH resolved `java` to the Oracle `javapath` shim, which exited without starting the service.

### Changes

- Java memory write now returns Python's JSON governance result instead of a fixed success string.
- Frontend memory write now parses JSON and shows:
  - written count;
  - pending count;
  - explicit non-write reason such as `writer rejected input`.
- Frontend memory query now requires JSON responses, making redirects/HTML responses visible as real API contract errors.
- Python embedding factory now wraps real embedding clients with runtime fallback to `StubEmbedding` when `MYAI_LLM_FALLBACK_TO_STUB=true`.
- Volcengine embedding fallback now uses a 2048-dimensional stub vector so fallback writes match the existing collection dimension.
- Startup script jar mode now prefers the known local JDK path before PATH `java`, avoiding the Oracle `javapath` shim.
- Added `MemoryControllerLocalModeTest` to keep local mode memory write/query JSON behavior covered.

### Verification

- Passed targeted Java test:
  - `.\\mvnw.cmd -q -Dtest=MemoryControllerLocalModeTest test`
- Passed Java test suite:
  - `.\\mvnw.cmd -q test`
- Rebuilt Java jar:
  - `.\\mvnw.cmd -q package -DskipTests`
- Verified local startup:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\\start-myai.ps1 -LocalMode -NoPause`
- Verified end-to-end memory APIs through Java with CSRF/session:
  - `POST /memory/write` returns `200 application/json`
  - `POST /memory/query` returns `200 application/json`
  - `GET /memory/list` returns `200 application/json`
  - A recognizable preference write (`I like Obsidian`) can be queried back and appears in the memory list.

## 2026-07-01 Memory Java Proxy And Manual Write Audit

### Context

- Frontend manual memory write could still show:
  - `鏈啓鍏ヨ蹇嗭細writer rejected input`
- The user-facing expectation for the memory page is explicit save, not automatic chat extraction.

### Findings

- Java memory proxy paths matched the Python API paths and could call Python correctly.
- The remaining failure was semantic:
  - `/memory/write` used the same extractor-only policy as automatic chat memory extraction.
  - Inputs that did not match rule/LLM structured extraction were rejected even though the user explicitly clicked "鍐欏叆".
- This made a valid manual save look like a Java/proxy failure.
- Java also lacked a memory-specific JSON error boundary, so future Python failures could again surface as HTML or login-like redirects.

### Changes

- Python `/memory/write` now enables explicit manual fallback:
  - extractor candidates are still preferred;
  - if extraction rejects the input, the API creates a `general` memory with slot `manual_note`;
  - chat auto-extraction remains extractor-only and does not use this fallback.
- Added Python regression coverage:
  - default extraction still rejects unstructured input;
  - explicit manual write stores unstructured input as `general/manual_note`.
- Added Java memory controller error handling:
  - Python memory service failures now return `502 application/json`;
  - response includes `success=false` and `error=python_memory_service_error`.
- Extended Java local-mode memory controller tests for the JSON error boundary.

### Verification

- Passed Python manual write tests:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_manual_write`
- Passed Java memory local-mode tests:
  - `.\\mvnw.cmd -q -Dtest=MemoryControllerLocalModeTest test`
- Rebuilt Java jar:
  - `.\\mvnw.cmd -q package -DskipTests`
- Restarted LocalMode services through startup script.
- Verified end-to-end through Java with CSRF/session:
  - manual memory write returns `200 application/json` and `written=true`;
  - query returns `200 application/json` and includes the written memory;
  - list returns `200 application/json` and contains the written memory.

## 2026-07-01 Task Java Proxy And Async Local Auth Audit

### Context

- Task workbench showed:
  - task list load failure;
  - task execution failure with `浠诲姟鎵ц閿欒锛岃绋嶅悗閲嶈瘯`.

### Findings

- Python task API was healthy:
  - `GET /task/runs`
  - `GET /task/workflows`
  - `POST /task`
- Java `/task/tools` worked because it was explicitly permit-all.
- Java authenticated task endpoints returned `302 /login`.
- Root cause:
  - Java task controller returns `Mono`;
  - Spring MVC performs async dispatch for the response body;
  - `LocalAuthFilter` did not run on async dispatch by default;
  - the async response dispatch lost local auth and was redirected to login.

### Changes

- Moved local auth injection earlier in the security chain:
  - before `AnonymousAuthenticationFilter`.
- Updated `LocalAuthFilter` to also run during async and error dispatch.
- Added task-specific JSON error boundary:
  - Python task service failures now return `502 application/json`;
  - payload includes `success=false` and `error=python_task_service_error`.
- Updated task frontend calls to use the shared JSON response reader:
  - task list;
  - tool list;
  - run polling;
  - background task creation/cancel;
  - direct task execution.
- Frontend task errors now include backend JSON error details when available.
- Added `TaskControllerLocalModeTest` covering:
  - local mode task list JSON response;
  - local mode task execution JSON response;
  - Python task service failure JSON boundary.

### Verification

- Passed Java local-mode controller tests:
  - `.\\mvnw.cmd -q "-Dtest=TaskControllerLocalModeTest,MemoryControllerLocalModeTest" test`
- Rebuilt Java jar:
  - `.\\mvnw.cmd -q package -DskipTests`
- Restarted LocalMode services through startup script.
- Verified task endpoints through Java with CSRF/session:
  - `GET /task/runs?limit=20` returns `200 application/json`;
  - `GET /task/tools` returns `200 application/json`;
  - `GET /task/workflows` returns `200 application/json`;
  - `POST /task` returns `200 application/json`;
  - `GET /task/runs/{task_run_id}` returns `200 application/json`;
  - `POST /task/runs` returns `200 application/json`.

### Phase 2.21 Slot Policy Refinement

- Extended slot definitions with governance and retrieval policy fields:
  - review confidence threshold
  - multi-candidate confidence threshold
  - retrieval weight
  - optional low-importance review threshold
- Governance normalization now writes the slot policy fields into memory metadata.
- Pending classification now consumes slot-specific thresholds instead of relying only on global constants.
- Retrieval scoring now multiplies by slot retrieval weight and exposes slot factors in retrieval explanations.
- Expanded eval coverage for slot retrieval weights and low-importance decision pending behavior.

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval tests.test_memory_slot_registry tests.test_api`

### Phase 2.22 Retrieval Policy Advancement

- Added freshness-aware retrieval ranking in the Python memory policy.
- Retrieval candidates now carry temporal and lifecycle metadata:
  - `created_at`
  - `last_accessed_at`
  - `observed_at`
  - `valid_from`
  - `valid_to`
  - `is_current`
- Retrieval scoring now considers:
  - source weight
  - freshness weight
  - current/history weight
- Decisions and opinions decay faster than stable facts and preferences.
- User-explicit memories receive a small source-quality boost; unknown sources are slightly down-ranked.
- Non-current memories are strongly down-ranked when they remain eligible.
- Retrieval explanations now expose source, temporal fields, freshness age, half-life, and the new weight factors.
- Expanded the governance eval fixture with retrieval policy cases for freshness, source weighting, and current/history ranking.

### Verification

- Validated fixture JSON with:
  - `.\\.venv\\Scripts\\python.exe -m json.tool tests\\fixtures\\memory_governance_eval.json`
- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval tests.test_api`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`

### Phase 2.23 Memory Consolidation Baseline

- Added a deterministic memory consolidation maintenance component.
- Consolidation now creates auditable summary memories for:
  - repeated observations with the same type/slot/value
  - long-term multi-value preferences
  - historical fact chains with previous/current states
- Summary memories include audit metadata:
  - `consolidation_summary`
  - `consolidation_kind`
  - `consolidated_at`
  - `consolidated_count`
  - `consolidated_from`
  - `consolidation_events`
- Repeated observation and preference evidence memories are marked `superseded`, linked through `consolidated_into`, and kept as historical evidence.
- Historical fact chain summaries preserve the current fact while summarizing earlier states.
- Memory decay now preserves non-deleted historical evidence instead of dropping all non-active memories.
- `memory.maintenance` trace metadata now includes a consolidation report.
- Python response schema and Java DTO now expose consolidation audit fields.

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_consolidation tests.test_api tests.test_memory_governance_eval`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`

### Phase 2.24 Consolidation Observability UI

- Added frontend visibility for memory consolidation audit metadata.
- Memory cards now show summary kind/count for consolidation summaries.
- Evidence memories now show `consolidated_into` when they have been absorbed by a summary memory.
- The governance/audit detail panel now includes consolidation fields:
  - `consolidation_summary`
  - `consolidation_kind`
  - `consolidated_at`
  - `consolidated_count`
  - `consolidated_from`
  - `consolidated_into`
- `consolidation_events` are parsed and rendered as evidence cards with memory id, source, state, observed time, valid range, and original content.
- Existing merge audit UI remains available in the same detail panel.

### Verification

- Passed frontend script syntax check with bundled Node:
  - `<NODE_EXE>`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.25 Consolidation Policy Tuning

- Added slot/type-driven consolidation policy.
- Supported policies:
  - `replace_evidence`: summary replaces evidence by marking original memories superseded/history.
  - `coexist_with_evidence`: summary links to evidence while original memories remain active/current.
- Current behavior:
  - repeated fact observations use `replace_evidence`.
  - long-term preference summaries use `coexist_with_evidence`.
  - historical fact chain summaries use `coexist_with_evidence` to preserve the current fact.
- Summary and evidence memories now expose:
  - `consolidation_policy`
  - `consolidation_evidence_action`
- `memory.maintenance` consolidation actions now report slot, policy, evidence action, linked evidence count, and replaced evidence count.
- The frontend memory profile now supports consolidation filtering:
  - all
  - summary
  - evidence
  - raw memory
- Memory cards and governance details now show the consolidation policy/action.

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_consolidation tests.test_memory_slot_registry tests.test_api`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed frontend script syntax check with bundled Node:
  - `<NODE_EXE>`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.26 User Memory Control MVP

- Added user-control metadata to memory edit/list responses:
  - `retrieval_enabled`
  - `pinned`
  - `user_hidden`
  - `user_locked`
  - `is_current`
  - `user_control_reason`
- Retrieval policy now filters user-disabled or user-hidden memories before ranking.
- Control-only PATCH requests no longer trigger edit-before-accept recalibration or pending review.
- Java memory DTOs now carry the user-control fields.
- Memory profile UI now defaults to simplified cards instead of always showing governance/audit detail.
- Added an audit view switch for detailed metadata, merge audit, and consolidation evidence.
- Added visibility filtering for visible, hidden, and all memories.
- Memory cards now provide direct controls to:
  - enable or disable retrieval
  - hide or unhide
  - pin or unpin
  - mark historical or restore current
  - delete
- Marking a memory historical from the UI also disables retrieval; restoring current re-enables retrieval.

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed frontend script syntax check with bundled Node:
  - `<NODE_EXE>`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.27 Python Agent Memory Management

- Added a `memory_admin` task tool for explicit Python Agent memory workflows.
- Supported operations:
  - `maintenance`
  - `eval_report`
  - `policy_inspection`
  - `settings_preview`
- `maintenance` runs user-scoped memory maintenance and returns consolidation/decay metadata plus a concise summary.
- `eval_report` wraps the existing memory governance calibration report and supports summary, JSON, and Markdown output.
- `policy_inspection` exposes slot policy, confidence calibration policy, and supported user memory control fields.
- `settings_preview` exposes the planned user-level memory settings contract without persisting settings yet.
- Registered `memory_admin` in the default task service tool registry.
- Added trigger words and argument extraction so `/task` can route memory maintenance/report/policy/settings requests into the tool.
- Added tests for:
  - direct `memory_admin` workflows
  - `/task` rule-based memory policy inspection

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_task_endpoint_runs_memory_admin_policy_inspection tests.test_api.MyAITestCase.test_memory_admin_tool_workflows`
- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.28 Persistent User Memory Settings

- Added persisted per-user memory settings with `MemorySettingsStore`.
- Settings are stored as JSON under:
  - `memory_settings/<user_id>/settings.json`
- Persisted fields:
  - `memory_enabled`
  - `auto_write_enabled`
  - `sensitive_requires_confirmation`
  - `default_memory_view`
- `MemoryService` now applies settings:
  - memory disabled blocks writes and retrieval
  - automatic writes disabled blocks `process_user_input`
  - sensitive confirmation remains enforced when configured
- `memory_admin` now supports:
  - `get_settings`
  - `update_settings`
  - persisted `settings_preview`
- Updated tests to verify settings persistence and that disabling automatic writes affects memory writes.
- Added runtime settings storage to `.gitignore`.

### Verification

- Passed targeted Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_memory_admin_tool_workflows tests.test_api.MyAITestCase.test_task_endpoint_runs_memory_admin_policy_inspection`
- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2.29 Java Frontend Memory Settings

- Added direct Python settings API endpoints for per-user memory defaults.
- Added Java DTO/service/controller plumbing for:
  - `GET /memory/settings`
  - `PATCH /memory/settings`
- Added a memory settings panel to the Java frontend settings page.
- The settings page now supports:
  - enabling/disabling long-term memory
  - enabling/disabling automatic memory writes
  - requiring confirmation for sensitive memories
  - choosing the default memory card view
- The frontend syncs `default_memory_view` into the existing memory page view selector.
- Added Python API regression coverage for loading/updating settings and verifying automatic-write blocking.

### Verification

- Passed targeted Python API test with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api.MyAITestCase.test_memory_settings_api_controls_default_memory_policy`
- Passed frontend script syntax check with bundled Node.js.
- Passed Java tests with:
  - `$env:JAVA_HOME='<JAVA_HOME>'; .\\mvnw.cmd test`

### Phase 2 Sensitive Memory Policy Refinement

- Prioritized sensitive memory policy before negation-aware multi-value updates because LLM extraction and broader retrieval increase the risk of accidentally persisting secrets.
- Split sensitive handling into categories:
  - `secret`: explicit passwords, tokens, API keys, private keys, and similar credential-shaped content.
  - `personal_sensitive`: ID cards, bank cards, credit cards, passports, social security, and similar high-sensitivity personal data.
  - `none`: ordinary personal facts, including terms such as `password manager` when they are not credential assignments.
- Secret-like memories are now forced to `review_status=rejected`, even if an upstream caller tries to mark them accepted.
- Personal-sensitive memories remain `review_status=pending` for human confirmation.
- Memory governance responses now include `sensitive_category`.
- Added regression coverage for:
  - explicit secret rejection
  - avoiding false positives for `password manager`
  - pending classification for personal-sensitive facts
  - eval fixture assertions for sensitivity and sensitive category

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Multi-Candidate Extraction

- Added multi-candidate memory extraction while keeping the old single-candidate API compatible.
- Structured extractors can now expose:
  - `extract()`
  - `extract_many()`
- `SmartMemoryWriter` now exposes:
  - `should_write()` for backward-compatible first-candidate behavior
  - `extract_candidates()` for multi-candidate extraction
- Rule-based extraction can split simple compound user messages, for example:
  - `my major is CS and I like Python`
- LLM extraction now supports both old single-object JSON and multi-candidate payloads:
  - direct JSON array
  - `{ "should_write": true, "memories": [...] }`
- `MemoryService.process_user_input()` now processes each candidate independently through:
  - embedding
  - governance metadata normalization
  - sensitivity / pending / rejected classification
  - dedup merge audit
  - conflict / temporal / negation handling
- The write response remains compatible with old callers by preserving first-result fields such as `memory_id`, `action`, and `reason`.
- The write response now also includes:
  - `candidate_count`
  - `written_count`
  - `results`
- Added tests for:
  - rule-based multi-candidate extraction
  - LLM multi-candidate parsing
  - `/memory/write` writing multiple candidates in one request

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Memory Retrieval Explanation

- Added a retrieval explanation layer to memory governance.
- Existing `retrieve_for_context()` behavior remains compatible for prompt building.
- Added an explanation-oriented retrieval path for chat trace:
  - `retrieve_for_context_with_explanation()`
- Retrieval policy now records one decision per candidate:
  - selected or filtered
  - final score
  - human-readable reason
  - scoring and governance factors
- Selection explanations include score factors:
  - similarity
  - memory score
  - importance
  - confidence
  - type weight
  - confidence weight
  - final score
- Filtering explanations include governance reasons:
  - similarity threshold
  - inactive or historical status
  - rejected review status
  - pending review status
  - sensitive memory exclusion
  - conversation scope mismatch
  - outside max memory context limit
- The `memory.retrieve` trace step now includes:
  - selected memories with `final_score`
  - citations
  - `retrieval_explanations`
- The frontend trace panel now renders a readable "妫€绱㈣В閲? section before raw metadata.

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Dedup Merge Audit

- Added audit metadata when duplicate memories are merged.
- Exact slot/value merges and semantic duplicate merges now record:
  - `merged_count`
  - `last_merged_at`
  - `last_merge_reason`
  - `last_merge_type`
  - `last_merged_memory_id`
  - `merged_from`
  - `merge_events`
- `merged_from` and `merge_events` are stored as JSON strings to remain compatible with Chroma metadata constraints.
- Merge events keep the latest 10 entries and include:
  - incoming memory id
  - merge type
  - reason
  - previous content
  - incoming content
  - incoming source and source reference fields
  - semantic similarity when available
- The memory list API and Java DTO now expose merge audit fields.
- Frontend memory cards now show a compact merge summary when a memory has been merged.
- Expanded unit and eval coverage for exact merge audit and semantic merge audit.

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Negation-Aware Multi-Value Memory Updates

- Added explicit negation handling for multi-value preference memories.
- Rule-based extraction now marks messages such as:
  - `I no longer like Python`
  - `I don't like Python anymore`
  - `I used to like Python but no longer...`
  - Chinese `涓嶅啀鍠滄...` style expressions
- Negation candidates carry:
  - `update_intent=negation`
  - `negation_signal=explicit`
- Deduplication now bypasses negation candidates so they are not merged into the existing positive preference before conflict handling.
- Conflict handling now checks negation before `coexist`/`append` multi-value policies:
  - if a matching current value exists, the old memory is marked `superseded`, `is_current=false`, with `historical_reason=negated by user...`
  - no new negation memory is added when the old value is successfully negated
  - if no matching value exists, the negation memory is added as `pending` for review
- LLM extractor prompt now supports `update_intent=negation`.
- Expanded eval fixtures and unit tests for writer detection, dedup bypass, resolver behavior, and end-to-end governance.

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Edit-Before-Accept

- Added a Python memory edit API:
  - `PATCH /memory/{user_id}/{memory_id}`
- Pending memories can now be edited before acceptance:
  - content
  - memory type
  - scope
  - sensitivity
  - importance
- Editing memory content recomputes the embedding vector.
- Edited pending memories record governance metadata:
  - `edited_before_accept=true`
  - `original_content`
  - `last_edited_at`
- Secret-like edited content remains protected:
  - edits that look like passwords, tokens, API keys, or secrets move the memory to `review_status=rejected`
  - rejected secret memories cannot be accepted through the accept endpoint
- Added Java service/controller forwarding for memory edits.
- Added frontend controls in the pending memory panel:
  - edit content
  - change memory type
  - change scope
  - change sensitivity
  - save
  - save and accept
  - reject

### Verification

- Passed Python tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest discover -s tests`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2 Memory Slot Registry

- Added a memory slot registry in the Python agent.
- The registry defines per-slot governance for:
  - normalized slot names
  - slot aliases
  - value aliases
  - cardinality: `single` or `multi`
  - conflict policy: `supersede`, `coexist`, `append`, or `pending`
- Memory governance metadata now enriches new memories with:
  - normalized `slot`
  - normalized `value`
  - `slot_cardinality`
  - `conflict_policy`
- Deduplication now compares normalized slot and value pairs before falling back to semantic similarity.
- Conflict handling now reads conflict behavior from the slot registry:
  - single-value facts can supersede previous values
  - multi-value preferences can coexist
  - append-style slots can accumulate without conflict
  - pending-style slots can be routed to review when introduced later
- Added focused tests for slot normalization, metadata enrichment, deduplication, and conflict behavior.

### Verification

- Passed slot registry tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_slot_registry`
- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Memory Governance Eval Fixture

- Added a small fixture-driven memory governance evaluation suite.
- The fixture covers:
  - should-write and should-not-write behavior
  - slot extraction and value normalization
  - automatic pending classification
  - slot/value deduplication
  - single-value conflict superseding
  - multi-value preference coexistence
  - citation payload generation from retrieved memories
- Added a deterministic in-memory embedding stub for eval cases so retrieval behavior is stable.
- The eval exposed a real ordering issue: semantic deduplication could merge same-slot but different-value memories before conflict handling had a chance to run.
- Fixed deduplication so semantic merge is skipped when structured slot matches but normalized values differ.

### Verification

- Passed memory governance eval with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval`
- Passed slot registry tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_slot_registry`
- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Memory Recognition Quality Baseline

- Added negative-memory command handling before memory extraction.
- Inputs such as `don't remember this`, `forget this`, `涓嶈璁颁綇`, `鍒`, `涓嶈淇濆瓨`, and `鍒繚瀛榒 now short-circuit memory writing.
- Extracted a structured memory extractor interface:
  - `MemoryToWrite`
  - `StructuredMemoryExtractor`
- Refactored `SmartMemoryWriter` into a small pipeline:
  - negative command gate
  - pluggable extractor list
  - default `RuleBasedMemoryExtractor`
- Cleaned the current rule extractor into UTF-8 Chinese and English patterns.
- Extended the memory governance eval fixture with English and Chinese negative-memory cases.
- Added focused tests proving custom extractors can plug into `SmartMemoryWriter`, and negative commands short-circuit extractors.

### Verification

- Passed memory governance eval with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_governance_eval`
- Passed extractor interface tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_extractor_interface`
- Passed Python memory/API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_memory_slot_registry tests.test_memory_governance_eval tests.test_memory_extractor_interface`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### LLM Memory Extractor

- Added a feature-flagged LLM memory extractor behind the rule-based extractor.
- Added memory-specific LLM settings:
  - `MYAI_MEMORY_PROVIDER`
  - `MYAI_MEMORY_MODEL_ID`
  - `MYAI_MEMORY_LLM_EXTRACTOR_ENABLED`
- Added `create_llm(role="memory")` support.
- The writer pipeline is now:
  - negative command gate
  - rule-based extractor
  - optional LLM structured extractor
- The LLM extractor:
  - asks for pure JSON only
  - validates `should_write`, `mem_type`, `content`, `slot`, `value`, `confidence`, and `importance`
  - rejects invalid JSON and unsupported memory types
  - rejects very low confidence candidates
  - marks metadata with `extraction_method=llm`
  - relies on existing governance to send low-confidence memories to pending
- Added tests for:
  - valid LLM JSON extraction
  - invalid JSON rejection
  - low-confidence rejection
  - MemoryService LLM fallback after rules miss

To enable locally:

- `MYAI_MEMORY_LLM_EXTRACTOR_ENABLED=true`
- optionally set `MYAI_MEMORY_PROVIDER` and `MYAI_MEMORY_MODEL_ID`

### Verification

- Passed LLM extractor tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_llm_extractor`
- Passed Python memory/API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api tests.test_memory_slot_registry tests.test_memory_governance_eval tests.test_memory_extractor_interface tests.test_memory_llm_extractor`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Live Memory LLM Calibration

- Confirmed the real memory-role LLM configuration is enabled through `.env`.
- Added a live calibration fixture with 12 English and Chinese cases.
- Added a reusable calibration command:
  - `.\\.venv\\Scripts\\python.exe -m app.memory.evaluation.calibrate`
- The calibration report checks:
  - should-write decisions
  - memory type
  - slot when specified
  - confidence ranges
- Added fail-closed behavior so model errors skip memory extraction instead of breaking chat.
- Added validated LLM metadata for:
  - `sensitivity`
  - `scope`
- First real-model run passed 12/12 but exposed confidence saturation at `1.0`.
- Added an explicit confidence rubric and confidence range expectations.
- Second real-model run passed 12/12, including all confidence range checks.
- Added a calibration record:
  - `docs/MEMORY_LLM_CALIBRATION.md`

### Verification

- Passed real-model calibration twice:
  - 12/12 cases passed before confidence range enforcement
  - 12/12 cases passed after confidence range enforcement
- Passed focused calibration and LLM extractor tests.

## 2026-06-09

### Temporal Memory Modeling

- Added temporal metadata to new governed memories:
  - `observed_at`
  - `valid_from`
  - `valid_to`
  - `is_current`
- Updated single-value conflict handling so facts are no longer only overwritten:
  - old current fact becomes historical
  - old fact receives `valid_to`
  - old fact receives `is_current=false`
  - old fact records `superseded_by`, `superseded_at`, and `historical_reason`
  - new fact remains active and records `previous_memory_id`
- Existing retrieval behavior remains conservative:
  - historical facts are not injected into normal chat context because they are marked `superseded`
  - memory list still exposes historical facts for user inspection
- Exposed temporal fields through:
  - Python memory response schema
  - Java memory DTO
  - frontend memory cards
- Extended governance eval cases to assert historical/current state for fact changes.

### Verification

- Passed Python memory tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_slot_registry tests.test_memory_governance_eval tests.test_api`

### Correction-Aware Updates And Current/History Filter

- Added correction-aware preprocessing in the memory writer.
- Explicit correction phrases such as `actually`, `correction`, `update`, `鏇存涓€涓媊, `鍏跺疄`, and move/live-now expressions now mark memory candidates with:
  - `update_intent=correction`
  - `correction_signal=explicit`
- Added rule coverage for location changes:
  - `I moved to ...`
  - `I now live in ...`
  - `I currently live in ...`
  - `鎴戞惉鍒?..`
  - `鎴戠幇鍦ㄤ綇鍦?..`
  - `鎴戠洰鍓嶄綇鍦?..`
- Updated the LLM memory extraction prompt and parser so model-backed extraction can also emit `update_intent`.
- Conflict handling now distinguishes correction from ordinary conflict:
  - historical memory reason becomes `corrected by newer value...`
  - new memory records `correction_applied=true`
  - result reason uses `correction on slot ...`
- Added current/history filtering to the memory profile UI:
  - all memories
  - current memories
  - historical memories
- Extended tests and eval fixtures to cover explicit correction updates.

### Verification

- Passed focused memory tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_memory_extractor_interface tests.test_memory_slot_registry tests.test_memory_governance_eval`
- Initialized the project root as a Git repository.
- Renamed the default branch to `main`.
- Added a root `.gitignore` for IDE files, local environments, build outputs, caches, vector stores, uploaded knowledge data, and logs.

### Trace Panel Frontend

- Added a collapsible execution trace panel under each new assistant reply on the chat page.
- The panel displays run id, status, start time, finish time, total step latency, and per-step details.
- Each trace step shows name, status, latency, input summary, output summary, and metadata when available.
- Updated the pending chat bubble behavior so the loading message is replaced by the final reply instead of remaining in the chat history.
- Verified Java side with:
  - `.\\mvnw.cmd test`

### SQLite And Local Auth Mode

- Added a local Spring profile for SQLite persistence:
  - `src/main/resources/application-local.properties`
  - default database: `myai-local.db`
  - Hibernate dialect: `org.hibernate.community.dialect.SQLiteDialect`
- Added SQLite JDBC and Hibernate community dialect dependencies.
- Added local authentication mode:
  - `myai.auth.mode=local`
  - creates or reuses one local user automatically
  - redirects `/` directly to `/home` in local mode
  - preserves the existing login flow when local mode is not enabled
- Moved the `PasswordEncoder` bean into a dedicated password config to avoid a security filter dependency cycle.
- Updated the root startup script:
  - `.\start-myai.cmd -LocalMode`
  - skips MySQL startup
  - enables the `local` Spring profile
  - uses SQLite by default
- Updated script documentation and `.gitignore` for local SQLite files.

### Verification

- Passed startup script status check:
  - `.\\start-myai.cmd status`
- Passed Java tests with:
  - `.\\mvnw.cmd test`
- Added an integration test that verifies the local user is created once and reused with an in-memory SQLite database.

## 2026-06-04

### Phase 1 Closure

- Closed Phase 1: Agent Runtime And Execution Trace.
- Added a dedicated closeout document:
  - `docs/PHASE1_AGENT_TRACE_CLOSEOUT.md`
- Updated the roadmap to mark Phase 1 as completed and Phase 2 as next.
- Confirmed the final Phase 1 scope:
  - Python runtime trace model
  - Python chat API trace response
  - Java trace DTOs and proxy forwarding
  - chat-page "鏈疆鎵ц杞ㄨ抗" collapsible panel
  - backward-compatible `reply` behavior
- Deferred trace persistence, analytics, token usage, and dashboards to Phase 6 Observability And Evaluation.

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`

### Phase 2.4 Confirmation Queue And 2.5 Memory Citations

- Added Python confirmation queue APIs:
  - list pending memories
  - accept memory
  - reject memory
- Added Python service support for updating memory `review_status` in Chroma metadata.
- Added Java proxy and controller endpoints:
  - `GET /memory/pending`
  - `POST /memory/{memoryId}/accept`
  - `POST /memory/{memoryId}/reject`
- Added a "寰呯‘璁よ蹇? panel on the memory page.
- Pending memory cards now support accept and reject actions.
- Added memory citations to the `memory.retrieve` trace step.
- The chat trace panel now renders citations separately before raw trace metadata.
- Kept default write behavior backward compatible: new memories are still accepted by default unless a later policy marks them pending.

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`
- Verified Python pending API:
  - `GET http://127.0.0.1:8000/memory/pending/1`
- Verified Java local mode responds on:
  - `http://127.0.0.1:8080`
- Verified the "寰呯‘璁よ蹇? frontend panel in the browser.

### Phase 2.1/2.2 Memory Governance Metadata

- Added a normalized memory governance metadata helper in the Python agent.
- New memories now carry governance fields in metadata:
  - `source`
  - `source_conversation_id`
  - `source_message_id`
  - `extraction_reason`
  - `confidence`
  - `scope`
  - `sensitivity`
  - `review_status`
- Chat-driven memory extraction now marks source as `chat_extraction` and records conversation id when available.
- Manual memory writes keep source as `user_explicit`.
- Python memory list API now returns governance fields, including a structured `source_ref`.
- Java memory DTO now accepts the governance fields.
- Frontend memory cards now show:
  - source
  - confidence
  - scope
  - review status
  - sensitivity
  - source reference when available
  - extraction reason when available
- Added Python tests for memory governance metadata defaults and API visibility.

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`
- Verified the local memory profile UI in the browser with local auth mode.

### Phase 2.3 Retrieval Governance

- Upgraded memory retrieval policy to consider governance metadata before memories enter prompt context.
- Retrieval now excludes:
  - inactive memories
  - `review_status=rejected`
  - `review_status=pending` in normal chat context
  - `sensitivity=sensitive` in normal chat context
  - mismatched `scope=conversation` memories
- Low-confidence memories are down-ranked instead of being deleted or fully excluded.
- Candidate retrieval now fetches more memories before filtering, so rejected or pending candidates do not block usable memories behind them.
- Memory access reinforcement now happens only after governance filtering accepts a memory into context.
- Agent trace memory retrieval metadata now includes governance fields:
  - confidence
  - scope
  - sensitivity
  - review status
  - source

### Verification

- Passed Python API tests with:
  - `.\\.venv\\Scripts\\python.exe -m unittest tests.test_api`
- Passed Java tests with:
  - `.\\mvnw.cmd test`
