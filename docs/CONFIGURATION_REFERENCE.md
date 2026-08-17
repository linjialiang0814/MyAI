# Configuration Reference

MyAI is configured through startup script options, Java environment variables, and Python Agent `.env` values.

Prefer local mode for daily development.

## Startup Script

Main entry:

```powershell
.\start-myai.cmd
```

Common options:

| Option | Purpose |
| --- | --- |
| `-LocalMode` | Use SQLite and automatic local auth. Recommended for first-run. |
| `-NoPause` | Start services in the background and return to the shell. |
| `-PythonPort <port>` | Override Python Agent port. |
| `-JavaPort <port>` | Override Java service port. |
| `-SkipMysql` | Skip MySQL service startup. |
| `-MysqlServiceName <name>` | Select a local MySQL Windows service. |
| `-DbUsername <name>` | Override database username. |
| `-DbPassword <value>` | Override database password for the current run. |

Script env file:

```text
scripts/start-myai.env
```

Create it from:

```text
scripts/start-myai.env.example
```

Do not commit real secrets.

## Java Service

Java config lives in:

```text
myai-java-service/src/main/resources/application.properties
myai-java-service/src/main/resources/application-local.properties
```

Important variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SERVER_PORT` | `8080` | Java web app port. |
| `SERVER_ADDRESS` | `127.0.0.1` | Java bind address. Keep the loopback default for the supported local-only baseline. |
| `PYTHON_SERVICE_BASE_URL` | `http://127.0.0.1:8000` | Python Agent base URL. |
| `PYTHON_SERVICE_CONNECT_TIMEOUT_MILLIS` | `5000` | Java-to-Python TCP connect timeout. |
| `PYTHON_SERVICE_REQUEST_TIMEOUT_SECONDS` | `160` | Java-to-Python response/blocking budget; keep it slightly above the Python chat deadline. |
| `DB_URL` | MySQL URL in default profile, SQLite URL in local profile | Java persistence database. |
| `DB_USERNAME` | `root` in default profile, empty in local profile | Database username. |
| `DB_PASSWORD` | empty | Database password. |
| `SPRING_PROFILES_ACTIVE` | empty | Set to `local` for SQLite/local auth mode. |
| `MYAI_AUTH_MODE` | default session login | Set to `local` for automatic local auth. |
| `MYAI_LOCAL_USERNAME` | `local-user` | Local auth display username. |
| `MYAI_LOCAL_EMAIL` | `local-user@myai.local` | Local auth email. |
| `MYAI_LOCAL_PASSWORD` | `local-password` | Local auth internal password. |

## Python Agent

Python config lives in:

```text
myai-python-agent/.env
```

Create it from:

```text
myai-python-agent/.env.example
```

Core model variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYAI_LLM_PROVIDER` | `stub` | Global fallback provider. |
| `MYAI_CHAT_PROVIDER` | `stub` | Chat provider. |
| `MYAI_TASK_PROVIDER` | `stub` | Task planning provider. |
| `MYAI_MEMORY_PROVIDER` | `stub` | Memory extraction provider. |
| `MYAI_EMBEDDING_PROVIDER` | `stub` | Embedding provider. |
| `MYAI_CHAT_MODEL_ID` | empty | Chat model ID. |
| `MYAI_TASK_MODEL_ID` | empty | Task model ID. |
| `MYAI_MEMORY_MODEL_ID` | empty | Memory model ID. |
| `MYAI_EMBEDDING_MODEL_ID` | empty | Embedding model ID. |
| `MYAI_LLM_TEMPERATURE` | `0.7` | Finite generation temperature in the inclusive range `0..2`. |
| `MYAI_LLM_SEED` | `42` | Reproducible generation seed for providers that support it. Empty disables the explicit seed. |
| `MYAI_LLM_MAX_TOKENS` | `512` | Maximum generated tokens for Chat Completions-compatible providers. |
| `MYAI_LLM_REQUEST_TIMEOUT_SECONDS` | `3` | Text-model request timeout. Raise this for local CPU/GPU inference. |
| `MYAI_LLM_MAX_RETRIES` | `0` | Provider SDK retries. Keep `0` for controlled experiments and wait for network/runtime stability before a manual retry. |
| `MYAI_LLM_FALLBACK_TO_STUB` | `true` | Fall back to Stub for text-generation failures. Real embedding providers always fail closed. |
| `MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS` | `3` | Embedding request timeout. |
| `MYAI_EMBEDDING_MAX_RETRIES` | `0` | Embedding provider retries. |
| `MYAI_EMBEDDING_EXPECTED_DIMENSIONS` | `0` | Expected embedding dimensions; `0` disables the explicit dimension check. |
| `MYAI_MODEL_TRUST_ENV_PROXY` | `false` | Whether model SDK clients should inherit `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` from the process environment. Keep `false` unless you intentionally route model traffic through a working local proxy. |

OpenAI-compatible local provider variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYAI_OPENAI_COMPATIBLE_BASE_URL` | `http://127.0.0.1:11434/v1` | Chat Completions endpoint for Ollama, llama.cpp, vLLM, LM Studio, or another compatible local runtime. |
| `MYAI_OPENAI_COMPATIBLE_API_KEY` | empty | Optional local-runtime key. Ollama ignores the placeholder key used internally. |
| `MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL` | chat endpoint | Optional independent embedding endpoint. |
| `MYAI_OPENAI_COMPATIBLE_EMBEDDING_API_KEY` | chat key only when endpoints match; otherwise empty | Optional independent embedding key. A chat credential is never forwarded to a different embedding endpoint. |

The supported local baseline keeps these endpoints on loopback. Sending chat prompts, memories, or document chunks to a non-loopback compatible endpoint is a separate deployment/security decision.

Embedding fallback is intentionally stricter than text generation: `volcengine` and `openai_compatible` embedding failures are propagated and never replaced by Stub vectors. This prevents vectors from incompatible embedding spaces from entering the same persistent Chroma collection. Model status reports this as `real_fail_closed`. Select `MYAI_EMBEDDING_PROVIDER=stub` explicitly only for a disposable Stub-backed index.

Volcengine/Ark variables:

| Variable | Purpose |
| --- | --- |
| `ARK_API_KEY` | API key. Keep private. |
| `ARK_BASE_URL` | API endpoint. |
| `ARK_MODEL_ID` | Default text model. |
| `ARK_EMBEDDING_MODEL_ID` | Default embedding model. |

Memory variables:

| Variable | Purpose |
| --- | --- |
| `MYAI_MEMORY_LLM_EXTRACTOR_ENABLED` | Enable LLM-based memory extraction. |
| `MYAI_MEMORY_PROVIDER` | Provider for memory extraction. |
| `MYAI_MEMORY_MODEL_ID` | Model used for memory extraction. |

Runtime persistence and test-isolation variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYAI_CHROMA_MODE` | `persistent` | Chroma client mode. Use `ephemeral` for isolated tests/evaluation only. |
| `MYAI_CHROMA_DIR` | `./chroma_db` | Persistent Chroma directory, resolved from the Python process working directory. |
| `MYAI_KNOWLEDGE_DATA_DIR` | `./knowledge_data` | Knowledge upload and index-source directory. |
| `MYAI_MEMORY_SETTINGS_DIR` | `./memory_settings` | Per-user memory settings directory. |
| `MYAI_RUNTIME_DB_PATH` | `./.runtime/runtime.db` | Python AgentRun, TaskRun, event, and idempotency SQLite database. Keep it separate from the Java database. |
| `MYAI_RUNTIME_DB_BUSY_TIMEOUT_MS` | `5000` | Maximum SQLite lock wait. The runtime also enables WAL, foreign keys, and `synchronous=NORMAL`. |

Unified-runtime variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYAI_MEMORY_MAINTENANCE_ENABLED` | `true` | Run consolidation/decay in the lifespan-owned background scheduler instead of the chat path. |
| `MYAI_MEMORY_MAINTENANCE_DEBOUNCE_SECONDS` | `30` | Coalescing window and minimum interval for repeated per-user maintenance requests. |
| `MYAI_MEMORY_MAINTENANCE_IDLE_POLL_SECONDS` | `1` | Scheduler idle wake interval. |
| `MYAI_MEMORY_MAINTENANCE_MAX_USERS` | `10000` | Bound on tracked per-user scheduler state. |
| `MYAI_MEMORY_MAINTENANCE_WORKER_COUNT` | `2` | Number of process-local maintenance workers. More workers reduce cross-user blocking but do not make a hung dependency cancellable. |
| `MYAI_MEMORY_MAINTENANCE_DEADLINE_SECONDS` | `60` | Cooperative budget for one maintenance batch. The worker checks it between operations; it cannot forcibly terminate a blocking call. |
| `MYAI_MEMORY_MAINTENANCE_SHUTDOWN_TIMEOUT_SECONDS` | `5` | Bounded total wait for maintenance workers during application shutdown. |
| `MYAI_CIRCUIT_FAILURE_THRESHOLD` | `3` | Consecutive dependency failures before the shared runtime circuit opens. |
| `MYAI_CIRCUIT_RECOVERY_SECONDS` | `30` | Open-circuit cooldown before one half-open probe. |
| `MYAI_RETRY_BASE_DELAY_SECONDS` | `0.25` | Initial backoff for retryable, idempotent work. |
| `MYAI_RETRY_MAX_DELAY_SECONDS` | `2` | Maximum retry backoff. |
| `MYAI_RETRY_JITTER_RATIO` | `0.2` | Bounded jitter ratio; must be in `0..1`. |
| `MYAI_TASK_MAX_PENDING_RUNS` | `100` | Maximum accepted background task runs before the API applies backpressure. |
| `MYAI_TASK_SHUTDOWN_TIMEOUT_SECONDS` | `5` | Maximum graceful-drain wait before shutdown is reported as incomplete. Dependencies stay open when workers have not stopped. |
| `MYAI_CHAT_DEADLINE_SECONDS` | `150` | End-to-end Python chat budget shared by orchestration phases. Provider transport timeouts should remain below this budget. |
| `MYAI_TASK_DEADLINE_SECONDS` | `120` | End-to-end task execution budget; tool timeouts and retry backoff consume the same budget. |

Provider timeouts remain the hard network deadlines. Runtime retry is deliberately narrower: only operations classified as transient and declared safe/read-only/idempotent are retried. A timed-out running thread may still finish later, so side-effecting tools are never automatically retried by default.

The full Python suite sets ephemeral Chroma and redirects all four data locations, including the runtime SQLite database, to a unique temporary test root. Normal development data should therefore remain unchanged by `python -m unittest` and `release-smoke.cmd`.

MCP connector variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `MYAI_MCP_FILESYSTEM_ENABLED` | `false` | Explicitly opt in to the read-only filesystem connector. |
| `MYAI_MCP_FILESYSTEM_ROOTS` | required when enabled | Allowed filesystem roots, separated by the OS path separator. Empty roots fail fast; configure the narrowest practical roots before enabling. |
| `MYAI_MCP_GIT_ENABLED` | `true` | Enable/disable the read-only Git connector. |
| `MYAI_MCP_GIT_ROOT` | project repository root | Git repository root. |
| `MYAI_MCP_GIT_BIN` | `git` | Git executable path or command. |

Filesystem MCP applies two layers of path control:

- resolved paths must remain under a configured root
- hidden and secret-like paths are omitted from lists/searches and rejected on direct reads

Sensitive-path filtering covers dot-prefixed path segments, `.env` files, common SSH credential names, private-key/certificate-store extensions, and filename tokens such as `credential`, `password`, `secret`, and `token`. Rejections use the `sensitive_path` error category. This filter is defense in depth, not an OS sandbox; keep the connector disabled unless it is needed and always use narrow roots.

## Privacy And Sensitive Output

Default API responses redact local absolute paths and secret-like values for task and observability APIs.

Local troubleshooting can explicitly request raw values:

```text
include_sensitive=true
```

Use this only for local debugging. Do not use it in shared screenshots, exported diagnostics, or public demos.

## Recommended Profiles

### First Run

```powershell
.\start-myai.cmd doctor -LocalMode
.\start-myai.cmd -LocalMode
```

### Local Development With Stub Models

```text
MYAI_CHAT_PROVIDER=stub
MYAI_TASK_PROVIDER=stub
MYAI_EMBEDDING_PROVIDER=stub
```

### Local Development With Live Models

```text
MYAI_CHAT_PROVIDER=volcengine
MYAI_TASK_PROVIDER=volcengine
MYAI_EMBEDDING_PROVIDER=volcengine
ARK_API_KEY=...
```

Keep API keys out of Git.

### Local Open-Source Baseline With Ollama

```text
MYAI_LLM_PROVIDER=openai_compatible
MYAI_CHAT_PROVIDER=openai_compatible
MYAI_TASK_PROVIDER=openai_compatible
MYAI_MEMORY_PROVIDER=openai_compatible
MYAI_EMBEDDING_PROVIDER=openai_compatible
MYAI_CHAT_MODEL_ID=qwen2.5:1.5b-instruct-q4_K_M
MYAI_TASK_MODEL_ID=qwen2.5:1.5b-instruct-q4_K_M
MYAI_MEMORY_MODEL_ID=qwen2.5:1.5b-instruct-q4_K_M
MYAI_EMBEDDING_MODEL_ID=bge-m3:latest
MYAI_OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:11434/v1
MYAI_OPENAI_COMPATIBLE_EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
MYAI_LLM_TEMPERATURE=0
MYAI_LLM_SEED=42
MYAI_LLM_MAX_TOKENS=512
MYAI_EMBEDDING_EXPECTED_DIMENSIONS=1024
MYAI_LLM_REQUEST_TIMEOUT_SECONDS=120
MYAI_EMBEDDING_REQUEST_TIMEOUT_SECONDS=60
MYAI_LLM_MAX_RETRIES=0
MYAI_EMBEDDING_MAX_RETRIES=0
MYAI_LLM_FALLBACK_TO_STUB=false
```

The strict thesis experiment does not use application `.env`; its committed spec is under `myai-python-agent/experiments/specs/`, disables text-generation fallback, and verifies that embedding requests fail closed.

If live model probes fail with `network` while TCP connectivity to the provider works, check process proxy variables. A broken proxy such as `HTTP_PROXY=http://127.0.0.1:9` can make the SDK fail even when direct network access works. The default `MYAI_MODEL_TRUST_ENV_PROXY=false` avoids this class of issue.
