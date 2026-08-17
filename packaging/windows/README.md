# MyAI Portable Windows Demo

This package runs MyAI locally and binds both services to `127.0.0.1`.

Prerequisites:

- 64-bit Windows 10 or later
- 64-bit CPython 3.12
- 64-bit Java 17 or later
- network access during the first `setup.cmd`, unless dependencies are supplied from a wheel directory

Quick start:

1. Extract the whole ZIP to a short, user-writable directory such as `C:\MyAI` (the package root must be at most 100 characters).
2. Run `setup.cmd` once. It creates an isolated Python environment and a private local configuration.
3. Run `doctor.cmd`.
4. Run `start.cmd`, then open `http://127.0.0.1:8080`.
5. Run `stop.cmd` when finished.

`reset.cmd` stops MyAI and removes only this package's `data` and `runtime` directories. It preserves `config/app.env`. Use `reset.cmd -Force` for unattended reset.

The default provider is the deterministic Stub provider, so the UI can be demonstrated without downloading a model. To use a real local model, edit `config/app.env` after setup. Never share that generated file because it contains the random local password.

The synthetic RAG file is available at `demo/sample-knowledge.txt`. The default MCP connector is read-only and restricted to this `demo` directory; the Git connector is disabled because the package is not a Git repository.
