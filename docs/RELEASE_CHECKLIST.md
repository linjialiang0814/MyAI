# Release Checklist

Use this checklist before sharing a local MyAI release snapshot.

## 1. Version

- Confirm `VERSION` exists and contains the intended release marker.
- Confirm release notes mention the current release state.

Current version marker:

```text
0.11.0-local
```

## 2. Privacy And Secrets

- Confirm `.env` is not committed.
- Confirm `scripts/start-myai.env` is not committed.
- Confirm logs are not included in release artifacts.
- Confirm local databases, Chroma stores, uploaded knowledge files, and runtime artifacts are excluded.
- Confirm default API/UI views redact local paths and secret-like values.
- Do not include screenshots that show `include_sensitive=true` output.

## 3. Local Smoke Test

Run:

```powershell
.\release-smoke.cmd -JavaHome "<path-to-jdk-17-or-newer>"
```

The smoke test checks:

- version marker
- local startup diagnostics
- docs link sanity
- sensitive default scan
- frontend script syntax
- Python observability/eval smoke tests
- Java tests

For a faster documentation-only pass:

```powershell
.\release-smoke.cmd -SkipPythonTests -SkipJavaTests
```

## 4. Manual Product Smoke

Start local mode:

```powershell
.\start-myai.cmd -LocalMode
```

Then verify:

- login/local auth reaches the main workbench
- Chat page opens and suggested prompts render
- Demo workspace opens
- Settings health center loads
- Memory workbench loads
- Knowledge file list loads
- Task tool catalog loads and shows privacy boundary
- Observability workbench loads and shows privacy boundary

Stop:

```powershell
.\start-myai.cmd stop
```

## 5. Artifact Cleanup

Follow:

- [Artifact Cleanup](ARTIFACT_CLEANUP.md)

At minimum, do not include:

- `.env`
- `scripts/start-myai.env`
- `scripts/logs/`
- `myai-python-agent/.runtime/`
- `myai-python-agent/.tmp/`
- `myai-python-agent/chroma_db/`
- `myai-python-agent/knowledge_data/`
- Java `target/`
- local `*.db`, `*.db-shm`, `*.db-wal`

## 6. Final Review

- Root README points to product docs.
- Quick Start works from the project root.
- Known limitations are honest and current.
- Phase 7 plan and execution log are up to date.
- No local secrets appear in committed files.

## 7. Portable Windows Artifact

Build and verify the shareable ZIP:

```powershell
.\scripts\build-portable.ps1 -OutputDirectory .\dist
.\scripts\verify-portable.ps1 -ArtifactPath .\dist\MyAI-<version>-windows-x64.zip
```

- Ship the ZIP together with its adjacent `.zip.sha256` file.
- Confirm verification rejects a missing checksum, tampered manifest, modified payload, or unexpected extra file.
- Extract to a directory outside the source tree and run `status.cmd` and `doctor.cmd`.
- On a prepared Windows test machine, complete `setup.cmd`, `doctor.cmd`, `start.cmd -NoBrowser`, a guided demo, `stop.cmd`, and the confirmed reset flow.
- Confirm the artifact contains no `.env`, generated `config/app.env`, logs, database, vector store, uploaded knowledge, virtual environment, Maven cache, or test code.
- Follow [Portable Windows App](PORTABLE_APP.md) for the supported environment and truthful packaging boundary.

## Release Decision

If all checks pass, this release can be treated as a local product baseline snapshot.

This checkpoint provides a checksummed local Windows App Demo artifact. It is not an MSI, a digitally signed publisher release, or a fully bundled runtime.
