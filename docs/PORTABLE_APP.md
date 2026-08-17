# Portable Windows App

The Stage 4 portable artifact packages the MyAI Java web application, Python Agent source, pinned Python requirements, evaluation fixtures, launch controls, and a synthetic RAG demo into one Windows ZIP.

It is a local App Demo, not an MSI installer and not a fully bundled runtime. The target machine must provide:

- 64-bit Windows 10 or later
- Windows PowerShell 5.1 or PowerShell 7
- 64-bit CPython 3.12
- 64-bit Java 17 or later
- network access during the first setup, unless all Python wheels are supplied locally

Only Python 3.12 is currently in the supported contract. Python 3.11 has not been validated for this artifact.

## Build And Verify

From the repository root:

```powershell
.\scripts\build-portable.ps1 -OutputDirectory .\dist
.\scripts\verify-portable.ps1 -ArtifactPath .\dist\MyAI-<version>-windows-x64.zip
```

CI also extracts the artifact and runs `scripts/test-portable-controls.ps1` against the package root. This is a control/security smoke, not a substitute for first-install and UI startup acceptance on a prepared Windows machine.

If the Spring Boot executable JAR already exists under `myai-java-service/target`:

```powershell
.\scripts\build-portable.ps1 -OutputDirectory .\dist -SkipJavaBuild
```

The build selects tracked Python application files plus explicit runtime fixtures and package assets. It rejects known runtime data paths. It does not copy `.env`, logs, databases, vector stores, uploaded knowledge, virtual environments, Maven caches, or test code.

Output:

- `MyAI-<version>-windows-x64.zip`
- `MyAI-<version>-windows-x64.zip.sha256`

Inside the ZIP, `manifest.json` records each allowlisted file's relative path, byte length, and SHA-256. `manifest.sha256` protects the manifest. The external checksum is required by `verify-portable.ps1` and protects the ZIP itself. These are integrity checks, not a digital signature or publisher identity guarantee.

The manifest intentionally omits a build timestamp, so equivalent inputs have reproducible manifest content. PowerShell ZIP metadata may still prevent the complete ZIP from being byte-for-byte reproducible.

## Install On Another Computer

1. Transfer both the ZIP and adjacent `.zip.sha256` file.
2. Run `verify-portable.ps1` before sharing when the repository verification script is available.
3. Extract the complete ZIP into a short, user-writable directory such as `C:\MyAI`. The package root must be at most 100 characters because some pinned Python dependencies create long nested paths. Do not run directly from inside the ZIP viewer.
4. Run `setup.cmd`.
5. Run `doctor.cmd`. Use `doctor.cmd -Json` for a single machine-readable JSON result; failed checks still return a non-zero exit code.
6. Run `start.cmd` and open `http://127.0.0.1:8080`.
7. Run `stop.cmd` when finished.

The first setup creates `runtime/python`, installs the pinned dependencies without populating the user pip cache, and creates `config/app.env`. The setup generates a cryptographically random local password, does not print it, and attempts to restrict that configuration file's Windows ACL to the current user. Re-running setup preserves the configuration and virtual environment.

`setup.cmd` rejects an overlong package root before creating the Python environment or downloading dependencies. `doctor.cmd` reports the same path preflight as a human-readable or JSON check.

To install from an existing wheel directory without network access:

```powershell
.\setup.cmd -Offline -WheelDirectory D:\myai-wheels
```

The wheel directory must contain a complete set of compatible wheels for the pinned requirements and CPython 3.12 x64.

## Runtime Layout

All mutable state is kept outside packaged application files:

```text
config/app.env        generated private settings; preserved by reset
data/                 Java SQLite, Chroma, knowledge, memory and run history
runtime/python/       isolated virtual environment
runtime/logs/         Java and Python logs
runtime/temp/         package-local Python/process temporary files
runtime/java-tmp/     package-local Java and SQLite temporary files
runtime/*.pid.json    package-owned process identity records
demo/                 synthetic RAG demonstration material
```

The Python and Java services bind to loopback by default. `start.cmd` refuses to take over an occupied port. `stop.cmd` only stops processes matching this package's recorded PID and process start time; it never kills a process merely because it owns a configured port.

## Configuration

Edit `config/app.env` after setup. The default Stub providers allow an offline functional UI demonstration after dependencies are installed. A real local model server remains a separate prerequisite; configure its OpenAI-compatible endpoint and model IDs in this file.

Do not share or commit `config/app.env` because it contains the local password and may later contain model credentials.

Use `demo/sample-knowledge.txt` for the packaged RAG walkthrough. It contains synthetic facts only.

The portable baseline enables the built-in read-only filesystem connector and dynamically restricts its only root to the package's `demo` directory. It explicitly disables the Git connector because the ZIP is not a Git repository and Git is not a prerequisite. A complete external/standard MCP client remains a later product checkpoint; this baseline demonstrates the existing connector policy, discovery, invocation, trace, and failure behavior.

## Reset

Interactive reset:

```powershell
.\reset.cmd
```

Unattended reset:

```powershell
.\reset.cmd -Force
```

Reset first stops package-owned processes, then deletes only resolved, non-link `data` and `runtime` directories beneath that package root. It preserves `config/app.env`. Reset is destructive for local conversations, users, memory, uploaded knowledge, task/run history, logs, and the Python environment, so `setup.cmd` must be run again afterward.

## Commands

```powershell
.\setup.cmd
.\doctor.cmd
.\start.cmd -NoBrowser
.\status.cmd
.\stop.cmd
.\reset.cmd
```

If startup fails, inspect `runtime/logs/python.err.log` and `runtime/logs/java.err.log`.
