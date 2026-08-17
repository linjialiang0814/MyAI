# Phase 7.6 Privacy And Safety Review

## Goal

Make MyAI's local data boundary explicit before broader productization.

The product should be inspectable without accidentally exposing local filesystem paths, secret-like values, or personal data in routine UI/API views.

## Default Policy

- MyAI is local-first.
- Default UI/API views should be safe for routine inspection.
- Sensitive local details require explicit troubleshooting intent.
- Trace, eval, connector, and maintenance data should favor summaries over raw payloads.
- Deletion/export controls should be added before any broader sharing or cloud sync workflow.

## Data Inventory

### Conversation Data

- Stored by Java service through conversation/message entities.
- May include personal prompts, assistant replies, trace summaries, citations, and task handoff content.
- Current boundary: authenticated/local user scope.
- Product risk: exported conversations may contain personal facts and retrieved context.

### Memory Data

- Stored by Python Agent memory module.
- Includes current memories, history, pending candidates, citations, governance metadata, confidence, and policy metadata.
- Current boundary: user-scoped API plus memory settings.
- Product risk: memory cards can contain sensitive personal facts by design.

### Knowledge Data

- Stored under Python Agent knowledge storage.
- Includes uploaded original files, extracted text, chunks, document profiles, summaries, citations, and maintenance reports.
- Current boundary: local storage and user-scoped API calls.
- Product risk: local stored file paths and document excerpts can reveal private workspace structure or document content.

### Task Runtime And Trace

- Stored in memory by task runtime, with recent runs exposed through API/UI.
- Includes task content, plans, tool calls, tool arguments, tool results, event timeline, retry/recovery metadata, and outcome memory.
- Current boundary: user-scoped Java task run list, Python task APIs.
- Product risk: tool results can contain local path metadata, file snippets, connector metadata, and memory context.

### Connector Settings

- MCP-style connectors expose health and settings.
- Filesystem connector includes allowed root names and root paths.
- Git connector includes repository root and git binary setting.
- Current boundary: local read-only connectors.
- Product risk: absolute local paths reveal usernames, project structure, and filesystem layout.

### Observability And Eval

- Eval run history is persisted as JSONL by Python Agent.
- Observability summary includes task counters, connector health, recent events, eval status, and eval storage metadata.
- Current boundary: local API/UI.
- Product risk: persisted eval path and event metadata may expose local paths or task/tool details.

### Logs And Runtime Artifacts

- Startup scripts and local services write runtime output/logs.
- Python Agent may have `.runtime`, Chroma, knowledge data, and temporary directories.
- Current boundary: local filesystem.
- Product risk: logs can capture prompts, connector failures, paths, stack traces, and environment hints.

## Implemented Baseline

- Added Python API redaction utility:
  - redacts local absolute paths in path-like fields
  - redacts secret-like fields such as token/password/api_key
  - preserves non-sensitive status, counts, health, root labels, and relative connector paths
- Default API responses now redact sensitive local metadata for:
  - `/task/tools`
  - `/task`
  - `/task/runs`
  - `/task/runs/{task_run_id}`
  - `/task/runs/{task_run_id}/cancel`
  - `/observability/summary`
  - `/observability/events`
- Explicit local troubleshooting remains available through:
  - `include_sensitive=true`
- API responses expose privacy metadata:
  - whether redaction is applied
  - whether sensitive values are included
  - which field families are redacted
- Frontend now surfaces privacy boundary state in:
  - task tool directory
  - observability workbench
  - system health center

## Product Rules

- Default user-facing API calls should not include full local absolute paths.
- Default connector health views should show root labels and health, not raw local roots.
- Raw trace/tool results should be treated as potentially sensitive.
- Eval and maintenance reports should prefer aggregate metrics and case IDs over raw user content.
- `.env`, API keys, tokens, and credentials must never be displayed by default.
- Any future export/share/debug bundle must pass through the same redaction policy.

## Known Gaps

- No one-click delete/export control for all local user data yet.
- No dedicated debug bundle export with redaction preview.
- Logs are not centrally reviewed or redacted.
- Conversation export is not yet routed through a redaction policy.
- Knowledge original files and vector/chunk data do not yet have a UI-level deletion audit.
- `include_sensitive=true` is API-level only and should remain local/troubleshooting oriented.

## Next Candidates

- Add a local data management page:
  - export inventory
  - delete conversation/memory/knowledge/eval artifacts
  - show storage locations with redaction preview
- Add a redacted diagnostic bundle generator.
- Add log retention and redaction guidance to startup scripts.
- Add privacy regression cases to unified eval.
- Add per-connector privacy labels and hosted-mode blockers.
