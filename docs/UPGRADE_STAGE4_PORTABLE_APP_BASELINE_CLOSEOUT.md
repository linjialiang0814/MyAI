# Stage 4 Portable App Demo Baseline Closeout

Date: 2026-08-12

Release target: `0.11.0-local`

Status: implementation complete; standard MCP interoperability remains the second
Stage 4 checkpoint.

## Outcome

MyAI can now be built as a checksummed Windows ZIP and extracted on another supported
computer without editing source code. The target machine supplies Python 3.12 x64 and
Java 17+; setup creates a package-local virtual environment and normally downloads the
pinned Python dependencies.

This is a portable local App Demo, not an MSI, digitally signed release, fully offline
bundle, or public deployment.

## Delivered Scope

- allowlisted build of the Spring Boot executable JAR, Python runtime source, five
  deterministic eval fixtures, configuration template, and synthetic demo data;
- external ZIP SHA-256 plus a manifest containing every packaged file's byte size and
  SHA-256, with rejection of missing, modified, duplicate, or unexpected content;
- `setup`, `doctor`, `start`, `stop`, `status`, and `reset` entrypoints;
- random non-echoed local password generation and a best-effort current-user ACL;
- loopback-only ports and package-local Java SQLite, Chroma, knowledge, memory,
  AgentRun/TaskRun, observability, eval-work, logs, and Python environment;
- PID ownership checks using schema, role, canonical package root, start time,
  executable, and command marker; stop never kills an arbitrary port owner;
- reset restricted to exact package-local `data` and `runtime` directories, rejecting
  top-level or descendant filesystem links;
- inherited model, Spring, Python-path, and JVM option isolation before startup;
- demo-only read access for the built-in MCP-style filesystem connector, with Git
  disabled in the portable package;
- externalized CSS and seven ordered JavaScript files while retaining the existing
  Thymeleaf, CSRF, and global-handler contracts;
- Windows CI for repository gates, Python 3.12 tests, Java 17 `verify`, portable build,
  artifact verification, and extracted-package safety controls.

## Verification

The implementation was reviewed against cross-machine paths, runtime-data isolation,
environment inheritance, process ownership, link-safe reset, bytecode/eval workspace
pollution, demo routing, and CI artifact handoff.

Final authoritative counts and generated artifact identity are recorded in the Stage 4
entry in `docs/EXECUTION_LOG.md`. The local validation completed build, external
checksum verification, extracted-path controls, fresh setup in a path containing
spaces, human/JSON doctor, start/status/stop, API/UI smoke, reset, full Python and Java
regression, and the shared release gate. Independent final review found no remaining
P0 or P1 issue in the portable baseline.

## Product Boundary

- Stub mode proves packaging, UI, storage, task, and API wiring; it does not demonstrate
  open-model answer quality.
- Real local intelligence still requires a separately installed compatible runtime and
  configured models.
- The built-in filesystem/Git classes are MCP-style adapters, not a complete standard
  MCP client.
- The second Stage 4 checkpoint will add one real read-only MCP Server transport with
  initialize, discovery, invocation, timeout, bounded reconnect, policy, and shutdown.
- Existing Stage 3 limits remain: one Python runtime, cooperative cancellation,
  process-local queues, unencrypted runtime SQLite, and no cross-service purge.

## Next Checkpoint

Implement a standards-compliant local stdio MCP vertical slice against one real
read-only server. Keep it optional, permission-governed, loopback/local-process only,
and covered by the portable demo and CI without expanding into write-capable tools or
a connector marketplace.
