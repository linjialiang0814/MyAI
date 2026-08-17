# MyAI Documentation

This folder is the product-oriented documentation home for MyAI.

MyAI started as an undergraduate design project, but the current direction is a local-first personal agent product with memory governance, knowledge-base retrieval, task workflows, MCP-style connectors, observability, and release hardening. Stage 2 completed the reproducible engineering evidence baseline; it is not a thesis manuscript, although its artifacts can support broader research later.

## Start Here

- [Quick Start](QUICK_START.md): run MyAI locally with the least setup.
- [Configuration Reference](CONFIGURATION_REFERENCE.md): environment variables and local mode settings.
- [Feature Guide](FEATURE_GUIDE.md): what the product can do today.
- [Troubleshooting](TROUBLESHOOTING.md): common startup and runtime problems.

## Engineering Docs

- [Project Final Audit](PROJECT_FINAL_AUDIT.md): completion verdict, title fit,
  evidence, engineering governance, and GitHub publication checkpoint.
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md): Java service, Python Agent, storage, and runtime boundaries.
- [Development Workflow](DEVELOPMENT_WORKFLOW.md): test commands, docs workflow, and safe change habits.
- [Privacy And Safety Review](PHASE7_PRIVACY_SAFETY_REVIEW.md): local data boundary and redaction policy.
- [Safe And Reproducible Baseline](SAFE_REPRODUCIBLE_BASELINE_PLAN.md): Upgrade Stage 1 security defaults, isolated tests, acceptance gates, and deferred production hardening.
- [Reproducible Core Evidence](UPGRADE_STAGE2_THESIS_EVIDENCE_PLAN.md): Upgrade Stage 2 local-model baseline, memory/RAG ablations, metrics, and checkpoint gate for the graduation design.
- [Stage 2 Formal Experiment Review](STAGE2_FORMAL_EXPERIMENT_REVIEW.md): reviewed results, statistical boundaries, raw-output findings, and evidence artifacts.
- [Stage 3 Unified Runtime Plan](UPGRADE_STAGE3_UNIFIED_RUNTIME_PLAN.md): FastAPI lifespan/DI, durable runs, Java/Python authority, maintenance scheduling, resilience, acceptance gates, and explicit MVP limits.
- [Stage 3 Unified Runtime Closeout](UPGRADE_STAGE3_UNIFIED_RUNTIME_CLOSEOUT.md): delivered scope, verification handoff, accepted limits, and next hardening priorities for `0.10.0-local`.
- [Stage 4 Local App Demo Plan](UPGRADE_STAGE4_LOCAL_APP_DEMO_PLAN.md): two-checkpoint productization plan for a portable Windows demo followed by standard MCP interoperability.
- [Stage 4 Portable Baseline Closeout](UPGRADE_STAGE4_PORTABLE_APP_BASELINE_CLOSEOUT.md): packaged scope, security controls, verification, and remaining boundaries for `0.11.0-local`.
- [Portable Windows App](PORTABLE_APP.md): build, verify, install, configure, start, stop, and reset the shareable Windows ZIP.
- [CI And Release Gates](CI_RELEASE_GATES.md): Windows CI and local quality-gate contract.

## Release Docs

- [Release Notes](RELEASE_NOTES.md): current release state and change highlights.
- [Known Limitations](KNOWN_LIMITATIONS.md): product boundaries and experimental areas.
- [Release Checklist](RELEASE_CHECKLIST.md): release readiness checklist.
- [Artifact Cleanup](ARTIFACT_CLEANUP.md): what to keep out of source/release artifacts.
- [Contributing](../CONTRIBUTING.md): development, tests, privacy, and pull-request
  expectations.
- [Security Policy](../SECURITY.md): supported trust boundary and responsible
  disclosure.

## Planning Records

- [Roadmap](ROADMAP.md)
- [Phase 7 Productization Plan](PHASE7_PRODUCTIZATION_PLAN.md)
- [Phase 8 Stabilization And Dogfooding Plan](PHASE8_STABILIZATION_DOGFOODING_PLAN.md)
- [Dogfooding Log](DOGFOODING_LOG.md)
- [Pain Point Tracker](PAIN_POINT_TRACKER.md)
- [Execution Log](EXECUTION_LOG.md)
