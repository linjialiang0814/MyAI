# Architecture Overview

MyAI is a local-first personal agent composed of two services.

```text
Browser
  |
  v
Java Spring Boot Service
  |
  v
Python FastAPI Agent
  |
  +-- LLM / embedding providers
  +-- memory store
  +-- knowledge store
  +-- task runtime
  +-- MCP-style connectors
```

## Java Service

Path:

```text
myai-java-service/
```

Responsibilities:

- user-facing web UI
- authentication and local auth mode
- conversation persistence and export
- request proxying to Python Agent
- CSRF/session handling
- system health center frontend integration

Key areas:

- `controller/`: page and REST controllers
- `service/`: Java business services and Python proxy clients
- `model/`: user, conversation, message entities
- `repository/`: persistence repositories
- `templates/`: Thymeleaf UI
- `application-local.properties`: SQLite/local auth profile

## Python Agent

Path:

```text
myai-python-agent/
```

Responsibilities:

- chat orchestration
- memory governance
- knowledge ingestion, retrieval, citation, and QA
- task planning and runtime
- MCP-style connector registry and execution
- eval, quality gates, observability, and maintenance reports
- privacy redaction for sensitive API output

Key areas:

- `app/api/`: FastAPI routes
- `app/core/`: chat orchestration
- `app/memory/`: memory extraction, governance, retrieval, consolidation
- `app/knowledge/`: document ingestion, indexing, QA, maintenance
- `app/task/`: planning, tools, workflows, runtime, MCP connectors
- `app/evaluation/`: eval suites, reports, gates
- `app/observability/`: eval history and event normalization
- `app/privacy/`: API redaction helpers

## Storage

Default local mode:

- Java: SQLite database through the `local` Spring profile
- Python: local runtime files, Chroma/vector stores, knowledge data, eval history

MySQL mode:

- Java uses MySQL for user/conversation persistence.
- Python Agent still manages its own memory, knowledge, and runtime artifacts locally.

Important local artifact areas:

- `myai-python-agent/knowledge_data/`
- `myai-python-agent/chroma_db/`
- `myai-python-agent/.runtime/`
- `scripts/logs/`
- Java local SQLite database in the Java working directory when local mode is used

## Runtime Flow

### Chat

1. Browser sends a chat message to Java.
2. Java stores conversation messages and forwards context to Python.
3. Python retrieves memory and knowledge context.
4. Python may classify task intent or invoke task workflows.
5. Python returns the assistant reply with trace metadata.
6. Java stores the assistant reply and renders trace/citation details.

### Memory

1. User input is evaluated for memory candidates.
2. Candidates go through extraction, slot policy, confidence, pending behavior, dedup/conflict handling, temporal metadata, and citation tracking.
3. Current and historical memory views remain auditable.

### Knowledge

1. User uploads a supported document.
2. Python parses and chunks the document.
3. Chunks are indexed for retrieval.
4. Queries return citation-first results and can be used in chat answers.

### Task Runtime

1. User submits a task.
2. Planner selects a workflow, rule, or LLM plan.
3. Runtime executes steps with policy and permission metadata.
4. Events are normalized into timelines and observability views.
5. Outcomes can generate memory candidates.

### MCP-Style Connectors

Connectors are integrated through the task tool registry.

Current low-risk connectors:

- read-only filesystem connector
- read-only git connector

Default UI/API responses redact local absolute paths before showing connector settings.

## Observability

MyAI exposes:

- eval registry and unified eval runner
- eval history persistence
- quality gates
- runtime counters
- recent normalized events
- connector health
- system health center in the frontend

This makes the product inspectable during local development without requiring cloud telemetry.

## Trust Boundary

MyAI is not designed as a hosted multi-tenant system yet.

The current trust model is:

- local-first
- user-controlled services
- read-only external connector baseline
- default redaction for sensitive local metadata
- explicit `include_sensitive=true` only for local troubleshooting
