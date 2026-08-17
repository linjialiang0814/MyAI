# Phase 5 MCP Tool Ecosystem Closeout

Date: 2026-06-29

## Status

Phase 5 is baseline completed and closed.

## Completed Scope

- MCP bridge MVP:
  - MCP descriptors can be converted into MyAI `Tool` instances.
  - MCP tools execute through the existing `ToolExecutor`.
  - MCP tools reuse validation, timeout, retry, and permission paths.
- Unified tool registry and inspection:
  - local tools and MCP tools are exposed through `GET /task/tools`.
  - frontend task workbench shows tool source, policy, schema, and connector data.
- MCP policy and permission mapping:
  - external metadata maps into MyAI `ToolPolicy`.
  - unknown/high-risk tools fail conservatively or require confirmation.
- MCP execution trace:
  - MCP calls emit `task.mcp_call.completed` and `task.mcp_call.failed`.
  - events are attached to both run timeline and step event list.
- First real connector:
  - read-only filesystem connector.
  - tools: list files, read text, search names.
  - path containment prevents access outside configured roots.
- Connector settings and health UI:
  - connector enabled state, health, roots/settings, risk, and tool list are visible.
- MCP eval fixture and report:
  - repeatable local report covers descriptors, policy, connector health, execution trace, fail-closed path behavior, disabled connectors, and Git connector behavior.
- Workflow integration:
  - filesystem MCP workflows can read/search project files through stable workflow definitions.
- Second real connector:
  - read-only Git connector.
  - tools: status, log, show.
  - workflows: git status review and recent history.

## Verification

- MCP bridge and connector tests pass.
- MCP eval report passes strict mode with 9/9 cases.
- Task API smoke tests pass for tool/connector inspection and MCP workflows.
- Frontend task template script syntax check passes.

## Deferred

- Runtime-configurable connector enable/disable from the frontend.
- Persistent connector settings in SQLite/user settings.
- Real remote MCP server process management.
- Higher-risk connectors such as browser session, calendar, database write, or GitHub actions.
- Per-user connector scopes and credential isolation.
- Connector marketplace or install flow.

## Recommended Next Phase

Start Phase 6: Observability And Evaluation.

Phase 5 added more runtime surface area. The next highest-leverage work is to make quality, latency, connector reliability, task traces, and eval regressions visible across the whole system instead of only through individual test commands.
