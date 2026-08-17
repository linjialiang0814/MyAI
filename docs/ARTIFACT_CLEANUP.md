# Artifact Cleanup

This document defines what belongs in source control and what should stay local.

## Keep In Source

- source code
- tests and eval fixtures
- docs
- `.env.example` files
- startup scripts
- release smoke scripts
- `VERSION`

## Keep Local

Secrets and local settings:

- `.env`
- `.env.*` except `.env.example`
- `scripts/start-myai.env`
- API keys
- database passwords

Runtime output:

- `scripts/logs/`
- `*.log`
- PID files
- temporary test caches
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`

Build output:

- Java `target/`
- Java `build/`
- project-local Maven caches:
  - `.m2repo/`
  - `.maven-home/`
- Python virtual environments:
  - `.venv/`
  - `venv/`

Local data:

- `*.db`
- `*.db-shm`
- `*.db-wal`
- Chroma/vector stores
- uploaded knowledge files
- Python Agent runtime history
- calibration/report JSON generated from local runs

## Current Ignore Baseline

The root `.gitignore` covers:

- environment files
- Python caches and virtual environments
- Java build outputs
- local databases
- Chroma and knowledge storage
- Python Agent runtime directories
- logs
- generated calibration reports

## Before Sharing

Run:

```powershell
git status --short
```

Review untracked files carefully. Do not add runtime data or secrets.

Run the release smoke:

```powershell
.\release-smoke.cmd -JavaHome "<path-to-jdk-17-or-newer>"
```

## If A Sensitive File Was Added

Do not commit it.

Remove it from staging:

```powershell
git restore --staged <path>
```

If it was already committed, rotate the secret and clean history before sharing.

## Sample Data Policy

No sample data bundle is included yet.

Future sample data should be:

- synthetic
- small
- clearly licensed
- free of personal information
- safe to index into the knowledge base
- safe for screenshots and demos
