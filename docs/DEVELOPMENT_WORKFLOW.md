# Development Workflow

This project should stay practical: small changes, visible behavior, repeatable validation.

## Working Principles

- Prefer local mode for development.
- Keep runtime artifacts out of source changes.
- Update docs when a phase or behavior changes.
- Use eval/tests for behavior that should not regress.
- Avoid exposing `.env`, local paths, passwords, API keys, or raw diagnostic bundles.

## Common Loop

1. Read only the files needed for the change.
2. Make a small implementation.
3. Add or update focused tests/eval fixtures.
4. Update relevant docs.
5. Run targeted verification.
6. Record the result in `docs/EXECUTION_LOG.md`.

## Start Dev Services

```powershell
.\start-myai.cmd doctor -LocalMode
.\start-myai.cmd -LocalMode
```

Background mode:

```powershell
.\start-myai.cmd -LocalMode -NoPause
```

Stop:

```powershell
.\start-myai.cmd stop
```

## Java Verification

```powershell
cd myai-java-service
$env:JAVA_HOME='<path-to-jdk-17-or-newer>'
.\mvnw.cmd --batch-mode --no-transfer-progress verify
```

Frontend external and inline script syntax check (requires Node.js on `PATH`):

```powershell
cd ..
.\scripts\ci-quality-gates.ps1
```

## Python Verification

Use the project virtual environment:

```powershell
cd myai-python-agent
.\.venv\Scripts\python.exe -m unittest
```

Targeted examples:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_observability_summary
.\.venv\Scripts\python.exe -m unittest tests.test_unified_eval_runner
```

If `pytest` is not installed in the venv, prefer `unittest` rather than switching to the system Python.

## Eval And Quality Gates

Use the Observability UI for normal checks.

Run the same static gate used by CI before a checkpoint:

```powershell
# From the repository root:
.\scripts\ci-quality-gates.ps1
```

It validates repository artifact hygiene, local documentation links, dependency pins, secret/default configuration safety, and frontend JavaScript syntax. See [CI And Release Gates](CI_RELEASE_GATES.md) for the workflow and portable artifact contract.

Relevant suites:

- memory
- task
- knowledge
- mcp
- all

Quality gates should be green before a release checkpoint.

## Documentation Workflow

Product docs live under:

```text
docs/
```

When changing a feature:

- update the relevant user-facing doc
- update the phase plan if it changes scope/status
- add an execution log entry

For planning docs, keep:

- purpose
- implemented baseline
- deferred work
- verification

## Privacy Workflow

Before adding new diagnostic, export, trace, connector, or report data:

- decide whether it can contain local paths
- decide whether it can contain user content
- decide whether it can contain secrets
- pass default UI/API output through redaction when needed
- expose raw values only through explicit local troubleshooting paths

## Release Hygiene

Before sharing the project:

- remove local runtime artifacts
- do not commit `.env`
- do not commit `scripts/start-myai.env`
- do not commit logs
- run doctor in local mode
- run Java and Python tests
- check the privacy/safety review
