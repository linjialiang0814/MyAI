# Feature Guide

This guide describes the current user-visible MyAI product surface.

## Chat Cockpit

Chat is the main daily-use surface.

Capabilities:

- multi-turn conversation
- conversation history
- trace summary and expandable execution trace
- memory and knowledge influence visibility
- task handoff hints
- quick links to memory, knowledge, task, and observability workbenches

Use it for:

- general assistant conversation
- asking questions over remembered preferences
- asking questions over uploaded knowledge
- starting task-oriented workflows

## Memory Workbench

The memory module manages what MyAI remembers about the user.

Capabilities:

- governed memory extraction
- multiple memory candidates from one input
- confidence-aware pending behavior
- edit-before-accept
- correction-aware updates
- current/history filtering
- temporal metadata and history retention
- dedup merge audit
- retrieval explanations
- consolidation summary and evidence chains
- user memory settings

Use it for:

- reviewing remembered facts and preferences
- accepting or rejecting pending memory candidates
- inspecting why a memory was retrieved
- tuning default memory behavior from the settings page

## Knowledge Workbench

The knowledge module turns local documents into searchable, citable context.

Capabilities:

- upload `.txt`, `.pdf`, `.docx`
- ingestion metadata and maintenance report
- hybrid retrieval baseline
- reranking/final selection separation
- structured document profile
- single-document QA
- citation-first query results
- answer citations in chat

Use it for:

- asking questions about local documents
- validating which chunks supported an answer
- rebuilding or checking knowledge indexes

## Task Workbench

The task module converts requests into observable execution.

Capabilities:

- task state machine
- runtime event timeline
- trace unification
- tool policy and permission governance
- retry, timeout, and recovery metadata
- background task mode
- memory-aware planning
- outcome memory
- workflow registry
- runtime eval and reports

Use it for:

- repeatable operational workflows
- inspecting tool calls and task plans
- testing MCP connector workflows

## MCP-Style Tool Ecosystem

MCP-style tools are exposed through the unified task tool registry.

Current connectors:

- read-only filesystem connector
- read-only git connector

Capabilities:

- descriptor inspection
- policy and permission mapping
- connector health
- execution events and trace
- workflow integration
- eval fixture and report

Safety baseline:

- current connectors are read-only
- local absolute paths are redacted by default in API/UI views
- hosted mode remains blocked for local filesystem risks

## Observability Workbench

The observability module helps determine whether MyAI is reliable.

Capabilities:

- unified eval registry
- local eval runner
- metrics snapshot
- runtime counters
- normalized events
- eval history persistence
- quality gates
- maintenance reports
- connector health visibility

Use it for:

- running eval suites before changes
- checking quality gate status
- reviewing recent runtime events
- inspecting connector health

## Settings And Health Center

The settings page is the user-facing control center.

Capabilities:

- system health summary
- Java/Python readiness indicators
- model/eval configuration visibility
- memory settings
- knowledge health summary
- connector health summary
- eval gate status
- privacy boundary state

Use it for:

- first-run validation
- checking if MyAI is ready
- managing default memory policy
- seeing whether sensitive values are redacted

## Demo Workspace

The demo workspace provides guided scenarios.

Scenarios:

- memory correction and governance
- knowledge citation QA
- task runtime timeline
- read-only MCP filesystem/git workflows
- observability and quality gates

Demo flows are intentionally safe:

- no automatic memory writes
- no automatic file uploads
- no destructive connector actions
