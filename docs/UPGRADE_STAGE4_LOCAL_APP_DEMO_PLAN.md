# Upgrade Stage 4: Deliverable Local App Demo

Date: 2026-08-12

Target release: `0.11.0-local`

Status: portable App Demo baseline completed; standard MCP vertical slice pending

## Goal

Turn the existing local-first agent workbench into a versioned Windows App Demo that
can be copied to another supported computer, configured without editing source code,
started and diagnosed through stable commands, reset safely, and demonstrated through
repeatable product workflows.

This is a local product-delivery milestone. It is not a claim of a fully self-contained
installer, a public cloud service, or a production multi-instance deployment.

## Product Decision

Stage 4 follows a layered path:

1. deliver a reliable Windows portable App Demo;
2. add high-value engineering gates and frontend maintainability;
3. add one standards-compliant, read-only MCP interoperability slice;
4. defer native installers and public deployment until the Stage 3 production limits
   are resolved.

The primary deliverable remains loopback-only and supports one Python application
runtime.

## Supported Target

The first portable baseline targets:

- Windows 10 or Windows 11 x64;
- Windows PowerShell 5.1 or newer;
- Python 3.12 x64 available on `PATH` or explicitly configured;
- Java 17 or newer available through `JAVA_HOME` or `PATH`;
- network access during setup for pinned Python packages, unless a future release adds
  an offline wheelhouse;
- Ollama only when the user selects the real local-model profile.

The package includes the Spring Boot executable JAR and Python application source. It
does not bundle Python, a JRE, Ollama, model weights, or an offline dependency mirror.

## Runtime Layout

```text
MyAI-<version>-windows-x64/
├─ app/            # immutable Java/Python application payload
├─ config/         # generated local configuration and safe examples
├─ data/           # Java SQLite, Chroma, knowledge, memory settings
├─ runtime/        # Python run database, pids, state, and logs
├─ demo/           # synthetic sample document and guided demo instructions
├─ scripts/        # portable PowerShell implementation
├─ setup.cmd
├─ doctor.cmd
├─ start.cmd
├─ stop.cmd
├─ status.cmd
├─ reset.cmd
├─ manifest.json
└─ README.md
```

All mutable paths resolve underneath the extracted package root. The portable scripts
must not depend on the original repository location or the developer's home directory.

## Workstreams

### 4.1 Portable delivery baseline

- build a deterministic allowlisted ZIP from reviewed repository inputs;
- provide idempotent setup, doctor, start, stop, status, and reset commands;
- generate secrets locally instead of shipping a shared password;
- verify package contents, file sizes, hashes, and unexpected-file rejection;
- stop only processes that were started and identity-checked by this package;
- keep reset bounded to verified package-owned mutable directories;
- test from an unrelated temporary extraction directory.

### 4.2 Frontend modularization

- extract the large inline stylesheet into a static CSS resource;
- split the workbench JavaScript by responsibility without introducing an npm build;
- preserve Thymeleaf bootstrap values, CSRF behavior, existing global handlers, and API
  compatibility;
- extend syntax and MVC resource-contract tests to cover external assets.

### 4.3 Continuous integration and release gates

- run quality gates, Python tests, Java verify, and portable-package verification on
  Windows CI;
- use minimal workflow permissions and cancel superseded branch runs;
- scan tracked content for forbidden runtime artifacts and unsafe configuration
  defaults;
- make local release smoke reuse the same static quality gates where practical.

### 4.4 Standard MCP vertical slice

- connect to one real read-only MCP server through a supported local transport;
- cover initialization, tool discovery, invocation, schema mapping, timeout, permission
  policy, bounded reconnect, and safe shutdown;
- keep filesystem and Git write operations disabled in the App Demo baseline.

This slice follows the portable delivery checkpoint so packaging and frontend changes
remain independently reviewable.

## Demo Acceptance Paths

The packaged application must support five guided demonstrations:

1. governed memory write, correction, review, and retrieval;
2. upload of the included synthetic document and citation-aware RAG;
3. durable TaskRun inspection and restart recovery semantics;
4. a real read-only MCP tool invocation once the MCP slice is enabled;
5. AgentRun trace, health, and observability inspection.

Stub mode may be used to verify startup and UI wiring. Any demonstration of model
quality must use the explicit Ollama/Qwen/BGE profile and must not be represented as a
stub result.

## Release Acceptance

- a clean checkout passes CI without developer-specific paths or secrets;
- a built ZIP passes independent manifest and checksum verification;
- after extraction to an unrelated path, no source edit is needed for setup;
- setup is safe to rerun and produces actionable failures for missing prerequisites;
- doctor reports readiness in both human-readable and JSON form;
- start binds Java and Python to loopback and records package-owned process identities;
- stop cannot terminate an unrelated process merely because it owns a configured port;
- reset refuses paths outside the extracted package and requires confirmation unless
  explicitly forced;
- no `.env`, database, Chroma store, uploaded document, model, log, cache, or private
  path from the build machine enters the ZIP;
- the five guided demo paths have an operator checklist and synthetic sample data.

## Explicit Non-Goals

- MSI/MSIX, Electron, Tauri, automatic update, and code signing;
- bundling model weights, Python, a JRE, or Ollama in the first ZIP;
- React/Vue rewrite or a Node-based frontend build chain;
- public network binding, Kubernetes, multi-tenancy, or high availability;
- high-risk MCP write tools, OAuth connector marketplace, or every MCP transport;
- claiming offline setup before an offline dependency mirror is actually produced.

## Checkpoint Strategy

Stage 4 uses two checkpoints:

1. `portable-app-baseline`: packaging, modular frontend, CI, docs, synthetic demo data,
   and cross-directory verification;
2. `standard-mcp-demo`: one real read-only MCP transport and end-to-end demonstration.

Each checkpoint requires implementation review, focused tests, full Python/Java
regression, release smoke, staged secret/artifact review, and a clean Git commit.
