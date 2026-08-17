# Phase 7 Productization And Release Hardening Plan

## Goal

Make MyAI easier to install, configure, trust, demonstrate, and maintain as a real personal agent product.

Previous phases made MyAI capable. Phase 7 should make it usable and presentable.

The core shift is:

- from feature-complete to user-ready
- from internal workbench to product experience
- from "can run locally" to "can be started, diagnosed, trusted, and demonstrated"

## Current Foundation

MyAI already has strong agent capabilities:

- conversational assistant with execution trace
- governed memory module
- task runtime and workflow registry
- knowledge workbench with citations and QA
- MCP-style tool ecosystem
- observability, eval history, and quality gates
- refreshed auth pages and baseline workbench skin

The remaining friction is mostly product-level:

- first-run setup is still too implicit
- settings are spread across environment variables, backend defaults, and UI panels
- health and readiness are not unified
- chat does not yet fully express the agent runtime around it
- demos and docs are still more engineering-oriented than product-oriented

## Product Principles

- Local-first remains the default.
- Advanced controls should be discoverable, not always visible.
- Every feature should have a visible state: enabled, disabled, degraded, or needs setup.
- Trust comes from inspectability: citations, traces, settings, health, and memory controls.
- Avoid decorative dashboards; prioritize repeatable workflows and clear recovery paths.
- UI polish should reduce cognitive load, not hide system behavior.

## Step 0 Frontend Refresh

Status: baseline implemented.

Reference:

- `docs/PHASE7_STEP0_FRONTEND_REFRESH.md`

Completed:

- login/register redesign
- CSS-only interactive mascot
- Chinese copy cleanup
- baseline workbench visual refresh

This gives Phase 7 a stronger visual baseline, but does not replace deeper screen-by-screen product work.

## 7.1 Chat Page 2.0

Purpose: make chat feel like the main agent cockpit, not only a message box.

Status: baseline implemented.

Add:

- clearer three-zone chat layout:
  - conversation list
  - active chat
  - contextual agent side panel
- agent side panel with:
  - current conversation status
  - latest execution trace summary
  - memory influence
  - knowledge citations
  - task handoff / recent task
  - quality/health hints when relevant
- stronger message model:
  - user bubble
  - assistant bubble
  - pending state
  - trace and citation chips
- empty states:
  - suggested prompts
  - demo flows
  - "what MyAI can do" examples without becoming a landing page
- better mobile layout.

Acceptance criteria:

- Chat remains fully usable with existing APIs.
- A user can understand what influenced the answer.
- Trace is visible but no longer visually noisy.
- Chat can naturally hand off to memory, knowledge, task, and observability surfaces.

Implemented baseline:

- Upgraded chat section into a three-zone Agent Cockpit:
  - conversation history
  - active chat
  - agent context panel
- Added agent context panel with:
  - current status
  - latest trace step count
  - latest trace latency
  - memory influence count
  - knowledge citation count
  - trace step chips
  - contextual influence summary
  - quick links to memory, knowledge, task, and observability
- Added empty-state prompt suggestions for common agent workflows.
- Upgraded message rendering:
  - user message bubble
  - assistant label and bubble
  - trace/status chips
  - existing expandable trace panel retained below each answer
- Updated chat lifecycle behavior:
  - new conversation resets context panel
  - pending request shows busy agent status
  - completed response updates the panel from trace metadata
  - failed request shows error status and recovery hint
- Fixed conversation delete copy in the chat history list.
- Kept existing chat/conversation APIs unchanged.

Deferred:

- Persisted trace summary for historical assistant messages.
- Direct citation chips attached to answer text.
- Rich task handoff card from chat to task workbench.
- Dedicated mobile chat navigation controls beyond responsive stacking.

## 7.2 Unified Settings And Health Center

Purpose: make setup and runtime state understandable in one place.

Status: baseline implemented.

Add:

- local mode status
- Java service status
- Python agent status
- model/provider configuration status
- memory settings
- knowledge storage status
- connector status
- eval gate status
- environment checks

Acceptance criteria:

- A user can tell whether MyAI is ready to use.
- Missing configuration is shown with actionable next steps.
- Existing settings are consolidated without removing advanced controls.

Implemented baseline:

- Upgraded the settings page into a System Health Center plus settings page.
- Added a health summary surface for:
  - Java/Python observability reachability
  - model/eval configuration visibility
  - memory policy settings
  - knowledge-base file health
  - connector health
  - latest eval gate/eval history state
- Added quick actions:
  - refresh health status
  - run quality gate
  - jump to observability
- Reused existing Java proxy APIs where possible.
- Added Java proxy endpoints for:
  - `GET /eval/gates/config`
  - `POST /eval/gates/run`
  - `POST /eval/maintenance-report`
- Kept existing memory settings controls in the same page.

Deferred:

- Dedicated backend `/health` aggregate endpoint.
- Direct model provider status from Python config.
- First-run remediation checklist and environment validation.
- Redaction/privacy review for diagnostic exports.

## 7.3 First-Run Setup And Startup Diagnostics

Purpose: reduce setup friction for a new local user.

Status: baseline implemented.

Add:

- startup checklist
- `.env` detection and validation
- Java/Python dependency checks
- SQLite/local auth readiness
- Chroma/storage directory checks
- quick-start script output cleanup
- clear recovery messages for common failures

Acceptance criteria:

- A fresh local setup can be diagnosed without reading source code.
- Startup failures point to a concrete fix.
- Reconnecting/network instability does not trigger noisy retry loops.

Implemented baseline:

- Added startup diagnostic action:
  - `.\\start-myai.cmd doctor`
  - `.\\start-myai.cmd doctor -LocalMode`
- Diagnostics check:
  - project directories
  - `scripts/start-myai.env`
  - `myai-python-agent/.env`
  - Python executable and key imports
  - Java/JDK command
  - Maven wrapper or built jar availability
  - configured Python/Java ports
  - MySQL readiness or SQLite/local mode
  - writable log/runtime/storage parents
  - model/provider readiness for non-stub providers
- Diagnostic output uses explicit `OK`, `WARN`, and `FAIL` levels.
- `FAIL` exits non-zero so startup blockers are visible before running services.
- `WARN` provides remediation without blocking startup.
- Startup README documents the doctor workflow and custom-port stop behavior.

Deferred:

- GUI health-center integration with doctor output.
- JSON diagnostics output for automated parsing.
- One-click remediation for missing env files or dependencies.
- Full dependency installation automation.

## 7.4 Demo Scenarios And Guided Workflows

Purpose: make MyAI easy to demonstrate and evaluate as a product.

Status: baseline implemented.

Add guided flows for:

- memory correction and review
- document upload, summary, and citation-first QA
- task workflow execution and recovery
- MCP filesystem/git read-only workflows
- observability and quality gate inspection

Acceptance criteria:

- Each demo flow works with local fixtures or safe sample data.
- Users can reset or rerun demos.
- Demo data does not pollute personal memory by default.

Implemented baseline:

- Added a dedicated frontend Demo workspace.
- Added guided demo cards for:
  - memory correction and governance
  - knowledge-base citation QA
  - task execution and runtime timeline
  - MCP read-only filesystem/git workflows
  - observability and quality gate inspection
- Demo cards either:
  - jump to the relevant workspace
  - fill safe sample prompts
  - show next-step guidance
- Demo flows do not auto-submit memory writes, upload files, or perform sensitive actions.
- Added sidebar navigation entry for demo workflows.

Deferred:

- Safe sample data bundle.
- One-click demo reset.
- Scripted end-to-end demo runner.
- Demo isolation mode that prevents accidental personal memory pollution.

## 7.5 Screen-Level Product Polish

Purpose: make every major workbench area easier to use.

Status: baseline implemented.

Areas:

- Memory page:
  - simplified everyday controls
  - advanced governance detail on demand
  - clearer pending/review states
- Knowledge page:
  - document-centered workspace
  - ingestion status
  - structured summaries
  - QA and citations in a calmer layout
- Task page:
  - workflow launcher
  - runtime timeline
  - permission/retry/recovery controls
  - background task visibility
- Observability page:
  - quality gate controls
  - maintenance report view
  - recent regressions
  - connector and runtime health summary

Acceptance criteria:

- Each screen has a primary workflow and a clear empty state.
- Advanced metadata remains accessible but not overwhelming.
- The UI remains responsive and readable.

Implemented baseline:

- Added screen-level hero blocks for:
  - memory workbench
  - knowledge workbench
  - task workbench
  - observability workbench
- Added workflow strips that make the primary path of each screen visible without hiding advanced controls.
- Refined major panel headers with subtitles so users can distinguish everyday actions from governance/audit details.
- Added clearer task detail empty state and unified task result rendering so the empty state disappears once a task, demo scenario, or background run is active.
- Improved empty task run list guidance.
- Preserved existing APIs, advanced metadata, and audit surfaces.

Deferred:

- Full per-screen information architecture redesign.
- Dedicated route/subtab model for large workbenches.
- More compact mobile task/observability controls.
- Deep visual treatment for cards, timelines, and evidence chains.
- Screen-level guided tours beyond the current demo workspace.

## 7.6 Privacy And Safety Review

Purpose: make local trust explicit before broader usage or promotion.

Status: baseline implemented.

Reference:

- `docs/PHASE7_PRIVACY_SAFETY_REVIEW.md`

Review:

- stored memory content
- trace payloads
- knowledge excerpts
- connector paths
- eval history
- logs and runtime artifacts
- sensitive settings and `.env`

Add:

- redaction policy for UI/debug exports
- delete/export controls where appropriate
- clear local data storage documentation
- safer defaults for external connectors

Acceptance criteria:

- Users know what is stored locally.
- Sensitive content is not shown or exported accidentally.
- Connector risks are visible before use.

Implemented baseline:

- Added privacy and safety review documentation covering:
  - conversation data
  - memory data
  - knowledge data
  - task runtime and trace
  - connector settings
  - observability/eval history
  - logs and runtime artifacts
- Added Python API redaction utility for:
  - local absolute paths
  - path-like fields
  - secret-like fields
- Applied default redaction to:
  - task tool catalog
  - task run responses
  - observability summary
  - observability events
- Added explicit `include_sensitive=true` escape hatch for local troubleshooting.
- Exposed privacy metadata in API responses.
- Added frontend privacy boundary visibility in:
  - task tool directory
  - observability workbench
  - system health center

Deferred:

- One-click local data export/delete controls.
- Redacted diagnostic bundle export.
- Conversation export redaction.
- Central log retention/redaction policy.
- Privacy regression suite in unified eval.

## 7.7 Release-Quality Documentation

Purpose: replace thesis-era framing with practical product documentation.

Status: baseline implemented.

Add:

- quick start
- local mode guide
- configuration reference
- architecture overview
- feature guide
- troubleshooting
- development workflow
- release notes
- known limitations

Acceptance criteria:

- A technically capable new user can install and run MyAI from docs.
- The docs explain what works, what is experimental, and how to recover from failures.

Implemented baseline:

- Replaced root README with a product-oriented entrypoint.
- Added documentation index:
  - `docs/README.md`
- Added release-quality user and engineering docs:
  - `docs/QUICK_START.md`
  - `docs/CONFIGURATION_REFERENCE.md`
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/FEATURE_GUIDE.md`
  - `docs/TROUBLESHOOTING.md`
  - `docs/DEVELOPMENT_WORKFLOW.md`
  - `docs/RELEASE_NOTES.md`
  - `docs/KNOWN_LIMITATIONS.md`
- Documented:
  - local mode startup
  - configuration model
  - architecture boundaries
  - current feature surface
  - troubleshooting paths
  - development verification
  - release status
  - known limitations
- Removed hardcoded database password default from Java application config.

Deferred:

- Full cleanup of older module-level README wording.
- Generated docs site or screenshots.
- Public-facing release page.
- Versioned changelog automation.

## 7.8 Packaging And Release Baseline

Purpose: prepare MyAI for repeatable local releases.

Status: baseline implemented.

Add:

- version marker
- release checklist
- script sanity checks
- artifact cleanup rules
- optional sample data bundle
- repeatable local smoke test command

Acceptance criteria:

- A release can be prepared with a checklist rather than memory.
- Generated/runtime artifacts are separated from source.
- The project can be shared without leaking local data.

Implemented baseline:

- Added version marker:
  - `VERSION`
- Added release smoke entrypoints:
  - `release-smoke.cmd`
  - `scripts/release-smoke.ps1`
- Smoke test covers:
  - version marker presence
  - startup diagnostics in local mode
  - documentation link sanity
  - sensitive default scan
  - frontend inline script syntax
  - Python observability/eval smoke tests
  - Java tests
- Added release checklist:
  - `docs/RELEASE_CHECKLIST.md`
- Added artifact cleanup policy:
  - `docs/ARTIFACT_CLEANUP.md`
- Updated README and release notes with version and smoke command.
- Confirmed `.gitignore` already separates common generated/runtime artifacts from source.

Deferred:

- Installer or packaged binary distribution.
- Container image.
- Signed release artifact.
- Synthetic sample data bundle.
- CI-hosted release pipeline.

## Recommended Implementation Order

1. 7.1 Chat Page 2.0
2. 7.2 Unified Settings And Health Center
3. 7.3 First-Run Setup And Startup Diagnostics
4. 7.4 Demo Scenarios And Guided Workflows
5. 7.5 Screen-Level Product Polish
6. 7.6 Privacy And Safety Review
7. 7.7 Release-Quality Documentation
8. 7.8 Packaging And Release Baseline

## Why Start With Chat Page 2.0

Chat is the daily-use surface where all previous phases converge:

- memory writes and retrievals
- knowledge retrieval and citations
- task planning and handoff
- tool/MCP execution
- trace and observability

Improving chat first gives immediate product value and reveals which settings, health signals, and demo flows matter most.

## Phase 7 MVP Definition

Phase 7 MVP can be considered complete when:

- chat feels like a coherent agent cockpit
- setup and health status are visible
- at least three guided demos are available
- privacy/storage behavior is documented
- quick-start documentation works from a fresh local checkout
- local quality gate remains green

## Non-Goals

- Cloud deployment.
- Multi-tenant production hosting.
- Paid product infrastructure.
- Public marketplace packaging.
- Full telemetry export before privacy/redaction is designed.

These can be considered after local productization is credible.
