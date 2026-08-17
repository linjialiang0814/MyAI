# CI And Release Gates

Stage 4 uses a Windows-first GitHub Actions workflow to prove that a clean checkout can be tested, packaged, and inspected without relying on a developer's machine.

## Workflow

The workflow lives at `.github/workflows/ci.yml` and runs on pushes, pull requests, and manual dispatches. It grants read-only repository permission and cancels superseded runs for the same branch.

The jobs form this gate:

```text
static quality gates
        |
        +--> Python 3.12 full unittest suite --+
        |                                      |
        +--> Java 17 Maven verify + JAR -------+--> portable ZIP build and verification
```

The portable job consumes the JAR produced by the Java verification job. It does not rebuild a different JAR, so the packaged binary is the binary that passed the Java tests.

## Static Quality Gate

Run the same cross-machine gate locally:

```powershell
.\scripts\ci-quality-gates.ps1
```

It checks:

- a SemVer-compatible `VERSION` marker;
- Git tracked, staged, and non-ignored files for forbidden runtime/release artifacts;
- local Markdown links across the repository;
- exact Python dependency pins;
- common committed-secret signatures and sensitive default configuration values;
- external JavaScript, executable inline template scripts, local script references, and classic-script global declaration conflicts using Node.js.

The scanner intentionally reads repository-visible files instead of local ignored directories. Runtime databases, caches, logs, model stores, and developer `.env` files therefore do not create false failures, while an accidentally staged copy still fails the gate.

## Test And Build Gate

Python runs the complete `unittest` discovery suite with Python 3.12 and bytecode output disabled. Java runs Maven `verify` on Java 17, which executes tests and creates the Spring Boot JAR.

The portable artifact job then invokes:

```powershell
.\scripts\build-portable.ps1 -OutputDirectory <directory> -SkipJavaBuild
.\scripts\verify-portable.ps1 -ArtifactPath <zip>
.\scripts\test-portable-controls.ps1 -PackageRoot <extracted-package-root>
```

Verification covers the external ZIP checksum, the manifest checksum, and every packaged file's declared size and SHA-256 hash. The extracted control test checks environment isolation, the package-root length preflight, the demo-only filesystem MCP boundary, Git disablement, bytecode write protection, cross-package PID rejection, and fail-closed reset behavior for nested filesystem links. The workflow uploads only the verified ZIP and its checksum, with short retention because this is a demo artifact rather than a signed public release.

## Scope Boundary

Passing CI means the source, tests, JAR, and portable file structure are reproducible on the supported Windows runner. It does not mean that external model downloads are available, that an Ollama model is installed, or that the artifact is code-signed. Live-model and interactive end-to-end checks remain explicit local acceptance steps.
