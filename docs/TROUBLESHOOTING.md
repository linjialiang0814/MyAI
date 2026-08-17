# Troubleshooting

Start with diagnostics:

```powershell
.\start-myai.cmd doctor -LocalMode
```

Use `status` to inspect running services:

```powershell
.\start-myai.cmd status
```

## Startup Fails

### Python dependencies are missing

Symptom:

- doctor reports Python import failures
- Python service log mentions missing modules

Check:

```powershell
myai-python-agent\.venv\Scripts\python.exe -c "import fastapi, uvicorn, dotenv"
```

Fix:

- recreate or repair `myai-python-agent/.venv`
- install dependencies from `myai-python-agent/requirements.txt`

### Java does not start

Check:

```powershell
scripts\logs\java-service.log
```

Common causes:

- wrong JDK
- database connection failure
- port already in use
- Python Agent URL mismatch

Try local mode:

```powershell
.\start-myai.cmd -LocalMode
```

### Port already in use

Check:

```powershell
.\start-myai.cmd status
```

Stop current services:

```powershell
.\start-myai.cmd stop
```

Or use alternate ports:

```powershell
.\start-myai.cmd -LocalMode -PythonPort 8011 -JavaPort 8091
```

## Database Problems

### MySQL access denied

Use local mode first:

```powershell
.\start-myai.cmd -LocalMode
```

For MySQL mode, set:

```text
scripts/start-myai.env
```

with:

```text
DB_USERNAME=...
DB_PASSWORD=...
```

Do not commit real passwords.

### SQLite/local auth expected but login page appears

Confirm local profile is active:

```powershell
.\start-myai.cmd doctor -LocalMode
```

Local mode sets:

```text
SPRING_PROFILES_ACTIVE=local
MYAI_AUTH_MODE=local
```

## Model Problems

### Live model calls fail

Check:

```text
myai-python-agent/.env
```

Required for live providers:

- provider values such as `volcengine`
- model IDs
- API key
- base URL

If you need a reliable local baseline, switch to stub providers:

```text
MYAI_CHAT_PROVIDER=stub
MYAI_TASK_PROVIDER=stub
MYAI_EMBEDDING_PROVIDER=stub
```

## Knowledge Problems

### Upload succeeds but retrieval is weak

Try:

- smaller documents first
- direct Knowledge query before asking in Chat
- knowledge maintenance check/rebuild
- confirm embedding provider is configured

### Stored file is missing

Use Knowledge maintenance. The maintenance report should mark missing stored files or indexes that need rebuild.

## Memory Problems

### Memory was not written

Check:

- pending queue
- confidence score
- sensitive memory policy
- memory settings in Settings
- whether the input was a negative memory command

### Wrong memory is current

Use:

- current/history filter
- correction-aware update
- edit-before-accept
- delete or disable retrieval for the memory item

## Task And Connector Problems

### Tool does not run

Check:

- task timeline
- tool policy
- connector health
- permission/confirmation status
- retry/recovery events

### Filesystem/git connector path looks hidden

This is expected. Default API/UI views redact local absolute paths.

For local troubleshooting only, API calls can use:

```text
include_sensitive=true
```

Do not use sensitive output in shared screenshots or exported reports.

## Observability Problems

### Eval history is empty

Run an eval:

```text
Observability -> Run Eval
```

or use the API through the Java frontend controls.

### Quality gate fails

Open Observability and inspect:

- failed reports
- failed cases
- recent events
- connector health

Then rerun the relevant suite after fixing.

## Logs

Startup logs:

```text
scripts/logs/python-service.log
scripts/logs/java-service.log
```

Logs may contain local paths, prompts, stack traces, or environment hints. Treat them as local/private artifacts.
