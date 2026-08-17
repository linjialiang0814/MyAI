# Known Limitations

MyAI is usable as a local personal agent workbench, but several areas remain experimental or incomplete.

## Deployment

- No cloud deployment baseline yet.
- No multi-tenant security model.
- The supported Java startup path binds to `127.0.0.1` by default; LAN or public exposure is not a supported configuration.
- The Python service does not yet authenticate Java service-to-service calls, so it must not be exposed directly to untrusted clients.
- No container packaging, native installer, automatic updater, or signed publisher
  release. These are deferred product directions rather than requirements for the
  selected local App Demo checkpoint.
- A checksummed Windows portable App Demo exists, but the target computer must provide Python 3.12 x64 and Java 17+; first setup normally downloads pinned Python dependencies.
- The ZIP does not bundle Ollama, model weights, Python, a JRE, or an offline wheelhouse.

## Authentication And Storage

- Local mode is optimized for single-user development.
- MySQL mode exists, but first-run documentation recommends SQLite/local auth.
- No unified local data delete/export page yet.
- Runtime artifacts are distributed across Java, Python, logs, Chroma, knowledge data, and eval history.

## Privacy

- Default task/observability API views redact local paths and secret-like values.
- Conversation export redaction is not fully implemented yet.
- Logs are not centrally redacted.
- Diagnostic bundle export does not exist yet.
- `include_sensitive=true` should remain local troubleshooting only.

## Memory

- LLM extraction quality depends on provider/model configuration.
- Some sensitive-memory and edge-case conflict policies still need deeper eval coverage.
- Memory consolidation is auditable, but user-facing simplification can continue.
- No full natural-language memory control assistant yet.

## Knowledge

- Retrieval quality depends on document format, chunking, and embedding configuration.
- OCR/image-heavy PDFs are not a primary supported path.
- Large document collections may need performance tuning.
- Knowledge delete/rebuild audit can be improved.

## Task Runtime

- The task runtime is observable, but not a durable distributed job system.
- Background task admission is bounded, but the accepted-work queue is process-local
  and is not restored after a process restart.
- Synchronous `POST /task` returns HTTP 200 for a task business-result envelope even
  when planning or tool execution failed. Clients must inspect `status`, `success`,
  `error_code`, and `retryable` instead of treating transport success as task success.
- Task-run list, detail, and cancellation are owner-scoped, but Python currently receives a user identifier rather than an independently authenticated service identity.
- Workflow registry is useful but still curated manually.
- Tool permission governance is a baseline, not a full enterprise policy engine.

## Stage 3 Unified Runtime

- The supported Python deployment remains one application worker. Per-user locks,
  the knowledge JSON index, in-process context cache, and maintenance scheduler do not
  provide multi-process coordination or distributed leases.
- Java remains authoritative for users, conversation ownership, and chat messages.
  Python stores Java-validated identifiers as logical references; there is no
  cross-service foreign key or independent Python ownership authority.
- `.runtime/runtime.db` is an unencrypted local operational database. It contains
  redacted task content and assistant responses required for run inspection and
  idempotent replay; filesystem permissions and local-machine trust remain part of the
  security boundary.
- Retention, user export, and cross-service purge are not implemented. Deleting a Java
  conversation does not yet remove its Python AgentRun/TaskRun rows or guarantee secure
  deletion from SQLite WAL pages.
- A Python thread that has already entered a provider, tool, or maintenance operation
  cannot be forcibly terminated. Chat/task and maintenance deadlines are cooperative
  caller-side budgets checked around orchestration boundaries. Caller-side tool timeout
  is recorded as `outcome_unknown`, the operation is not automatically retried, and
  every dependency still needs its own transport timeout or cooperative cancellation.
- Memory consolidation can repair an interrupted evidence-link update, and conflicting
  writes attempt compensation, but Chroma does not provide a transaction across several
  memories. A simultaneous store outage can still require manual reconciliation.
- Memory maintenance is removed from the synchronous chat call sequence, but still
  competes for the same per-user lock. Foreground chat/task memory work and maintenance
  use non-blocking admission: the losing side records deferred/skipped work instead of
  waiting. Skipped foreground memory work is not durably queued for later replay.
- Maintenance uses two workers and a 60-second cooperative batch deadline by default.
  A blocking dependency can still hang one worker beyond that deadline; the second
  worker reduces cross-user impact, but enough hung calls can exhaust the pool and
  prevent clean shutdown until they return.
- Pending maintenance requests and scheduler generations are not persisted. A clean or
  abrupt restart can discard work that has not begun, and there is no durable lease,
  dead-letter queue, or automatic restart compensation.
- Java/Python idempotency prevents duplicate run/message creation for a repeated logical
  request. It does not make arbitrary external tool side effects exactly-once.

## MCP-Style Connectors

- Current real connectors are read-only and local.
- Filesystem MCP is disabled by default and rejects hidden/secret-like paths, but filename filtering is not an OS sandbox or complete content-aware secret detector.
- Hosted mode is not supported for filesystem-style risks.
- Connector settings are visible, but advanced per-user connector configuration remains future work.
- Write-capable connectors require a stronger confirmation and audit model before use.
- The portable baseline enables only the built-in MCP-style read-only filesystem
  connector and confines it to the package's synthetic `demo` directory. It is not yet
  a standards-compliant external MCP client; protocol interoperability is an optional
  future extension beyond the completed local App Demo scope.

## Observability And Eval

- Eval history is local and lightweight.
- Deterministic tests use Stub providers and isolated ephemeral stores; they do not prove live-model availability or long-duration persistent-store behavior.
- A Windows GitHub Actions workflow mirrors the local static, Python, Java, package,
  and safety gates. A workflow definition is not proof that a particular unpublished
  commit passed remotely, and live-model acceptance remains a separate local check.
- Regression delta is basic.
- Metrics are product-health oriented, not full APM telemetry.

## Stage 2 Engineering Evidence And Local Models

- Stage 2 is complete as a reproducible graduation-design engineering evidence
  baseline, not as a thesis manuscript or published paper. Its frozen artifacts can be
  extended into later research, but current claims remain limited to the recorded
  model, embedding, hardware, and synthetic datasets.

- The accepted formal evidence uses 18 unique memory cases and 30 unique RAG cases over a hand-authored synthetic corpus. Three technical repeats measure stability but do not enlarge the independent sample size or represent real-user distributions.
- Accuracy is deterministic core-proposition rubric accuracy, followed by mandatory raw-output review; it is not a learned semantic judge or unrestricted whole-answer factuality score.
- The Qwen2.5 1.5B baseline often retrieves the right evidence but fails to use it. All three RAG arms reach 100% Support Hit@3, while answerable accuracy remains 73.08% / 65.38% / 65.38%.
- Generated citation coverage is only 66/234 answerable RAG attempts (28.21%). A valid citation does not imply a complete or correct answer.
- All 36 no-answer RAG attempts correctly abstain, but every arm still selects three irrelevant chunks. A retrieval-level relevance/abstention gate is not implemented.
- Governed memory's measured gain comes primarily from safe abstention and forbidden-evidence filtering. Basic and governed memory both answer only 41.67% of answerable cases correctly.
- The current RAG dataset is saturated at Top-3 support recall and cannot establish that hybrid retrieval or lightweight reranking improves recall. Observed rerank citation gains are descriptive, not paired-significance claims.
- CPU-only model placement is verified through Ollama `size_vram=0`; the launcher requests `cpu_avx2`, but the exact CPU library is not exposed by `/api/ps`. GPU and system-wide resource metrics are observational, not model-process attribution.
- The formal artifact records the runtime byte hash of `requirements.txt`; the committed blob differs only by one Git-normalized line ending. Package verification still passed 95/95, but the file should receive an explicit LF attribute in a future baseline rather than rewriting historical evidence.
- The three retrieval strategies are exposed by the Python experiment/API layer. Existing Java knowledge DTOs keep the backward-compatible default and do not yet expose strategy selection or rerank metadata in the product UI.
- FastAPI lifespan now owns the supported single-process service graph. Multi-worker
  ownership, distributed leases, and hard cancellation remain production hardening.

## Frontend

- The UI remains one server-rendered Thymeleaf workspace, but its stylesheet and seven responsibility-oriented scripts are now external modules without an npm build chain.
- Screen-specific routing or a component framework may improve maintainability later; a SPA rewrite is not part of the portable MVP.
- Mobile responsiveness exists, but advanced mobile interactions are not fully optimized.

## Documentation

- The docs now provide a release-quality baseline.
- Some older module READMEs may still contain historical or thesis-era wording.
- Phase docs are execution records, not polished user manuals.
- The repository does not yet include a LICENSE; public visibility alone does not
  grant permission to copy, modify, or redistribute the code.
