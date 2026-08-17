# Safe And Reproducible Baseline

## Status

Completed on 2026-07-13 as Upgrade Stage 1, a cross-cutting hardening gate within the Phase 8 stabilization work.

This baseline does not add a new user-facing capability. It removes high-consequence defaults and makes the existing local product repeatable enough to support later model, workflow, and UX upgrades.

## Why This Stage Comes First

The review found several issues that could invalidate later work:

- Stub fallback could echo a complete assembled prompt containing conversation history, memory, retrieved knowledge, or tool output.
- The Java service did not explicitly declare a loopback-only bind address.
- The filesystem connector was enabled by default and its default root could include local configuration files.
- Task-run detail and cancellation paths did not consistently enforce the authenticated owner's boundary.
- Python tests could reuse development Chroma, knowledge, and memory-settings storage.
- Memory restore referenced `MemoryStatus` without importing it.
- The repository needed a verified, secret-free checkpoint before larger changes.

These are baseline risks rather than feature gaps. They are therefore addressed before open-source model integration, UI refinement, or deployment experiments.

## Implemented Baseline

### 1. Local Network Boundary

- Java now defaults to `SERVER_ADDRESS=127.0.0.1`.
- The Windows startup path explicitly sets the same loopback address.
- The local example configuration documents the bind address.
- LAN, hosted, and public exposure remain unsupported until a stronger authentication and service boundary exists.

### 2. Safe Stub Fallback

- Stub output is now a fixed generic availability message.
- Stub no longer returns or interpolates the input prompt.
- This prevents fallback behavior from disclosing assembled prompt contents to the UI, logs, or API consumers.

### 3. Filesystem Connector Is Opt-In

- `MYAI_MCP_FILESYSTEM_ENABLED` now defaults to `false`.
- Enabling the connector requires at least one explicit read-only allowed root and fails fast when roots are empty.
- Direct reads reject paths outside configured roots.
- Listing, searching, and reading hide or reject:
  - dot-prefixed files and directories
  - `.env`-style files
  - private-key, certificate-store, and SSH credential names
  - filenames tokenized as credential, password, secret, or token material
- Rejected sensitive access uses the `sensitive_path` error category.

The filename policy is defense in depth, not a substitute for a narrow root. When enabling the connector, configure `MYAI_MCP_FILESYSTEM_ROOTS` to the smallest directory required for the task.

### 4. Task Ownership Boundary

- Task-run list, detail, and cancellation API paths require a user identifier.
- The Java controller derives that identifier from the authenticated principal and forwards it to Python.
- Python verifies the persisted task-run owner before returning detail or accepting cancellation.
- Owner mismatch is returned as not found, which avoids revealing another user's task-run existence.

This is an ownership check for the current local architecture. It is not service-to-service authentication and does not make the Python API safe for direct public exposure.

### 5. Memory Restore Correctness

- The memory service now imports and uses `MemoryStatus` correctly when restoring a superseded memory.
- A focused regression test covers the restore-to-active transition.

### 6. Isolated And Repeatable Tests

- Model providers are forced to Stub during the Python test process.
- Chroma supports explicit `persistent` and `ephemeral` modes.
- Tests use ephemeral Chroma and a per-run temporary data root.
- Knowledge uploads and memory settings are redirected to that test root.
- Owned test roots are cleaned on process exit.
- Memory decay no longer constructs a Chroma client as an import-time default argument.
- Release smoke uses package-aware full discovery:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -p "test_*.py"
```

- Every direct Python requirement is version-pinned; release smoke rejects unpinned entries.

This keeps normal `chroma_db`, `knowledge_data`, and `memory_settings` state outside the test lifecycle.

### 7. Repository Checkpoint Gate

The baseline checkpoint is created only after:

- full Python and Java test suites pass
- release smoke passes
- documentation and configuration defaults match implementation
- ignored runtime data and local `.env` files remain untracked
- staged content passes a secret-pattern and diff sanity check

The checkpoint records the working product baseline; it must not include personal runtime stores, logs, databases, uploaded documents, or credentials.

## Configuration Baseline

| Variable | Safe default | Operational rule |
| --- | --- | --- |
| `SERVER_ADDRESS` | `127.0.0.1` | Do not widen the bind address until deployment security is designed. |
| `MYAI_CHROMA_MODE` | `persistent` | Use `ephemeral` only for isolated tests/evaluation. |
| `MYAI_CHROMA_DIR` | `./chroma_db` | Override for isolated environments; never point tests at personal data. |
| `MYAI_KNOWLEDGE_DATA_DIR` | `./knowledge_data` | Keep uploaded documents out of source control. |
| `MYAI_MEMORY_SETTINGS_DIR` | `./memory_settings` | Keep user-specific settings out of source control. |
| `MYAI_MCP_FILESYSTEM_ENABLED` | `false` | Enable explicitly and pair with narrow roots. |
| `MYAI_MCP_FILESYSTEM_ROOTS` | required when enabled | Set explicit minimal roots before opting in; empty roots fail fast. |

## Acceptance Evidence

The implementation is accepted when all of the following remain true:

- A Stub response contains no portion of its input prompt.
- Java and the supported startup script bind to loopback by default.
- Filesystem MCP is absent unless explicitly enabled.
- Sensitive and hidden filesystem paths are neither listed nor readable.
- Cross-user task list, detail, and cancellation access is rejected.
- Memory restore changes a superseded item back to active without a runtime name error.
- Two consecutive full Python runs pass without changing development persistence directories.
- Java tests pass with the principal-derived task ownership path.
- Root release smoke passes using the isolated full Python test suite.
- The Git checkpoint contains no local secrets or runtime data.

Verification commands:

```powershell
Set-Location myai-python-agent
.\.venv\Scripts\python.exe -m unittest

Set-Location ..\myai-java-service
.\mvnw.cmd -q test

Set-Location ..
.\release-smoke.cmd
```

The 2026-07-13 implementation check passed 154 Python tests and 19 Java tests (1 skipped), and the complete root release smoke passed. The root release smoke remains the single closeout command for future checkpoints.

## Deferred Deliberately

- Authenticated service-to-service calls between Java and Python.
- A production multi-user and multi-tenant authorization model.
- HTTPS, reverse-proxy hardening, rate limits, and public deployment.
- OS-level filesystem sandboxing and content-aware secret detection.
- Central secret management and automatic credential rotation.
- Container images, dependency lock verification, and hosted CI/CD.
- Explicit WebClient timeout/retry policies across every Java-to-Python call.
- Long-duration persistent-store and migration tests.
- Default integration of a real local open-source model; this should build on this baseline rather than bypass it.

## Next Stage Entry Conditions

Later work may proceed once the checkpoint and root smoke are green. The next upgrade should preserve these defaults, add regression coverage for every changed boundary, and treat any network exposure as a separate security design rather than a startup flag change.
