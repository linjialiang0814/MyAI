CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'chat',
    user_id TEXT NOT NULL,
    conversation_id INTEGER,
    idempotency_key TEXT,
    request_hash TEXT,
    status TEXT NOT NULL,
    response_json TEXT,
    error_code TEXT,
    error_message TEXT,
    retryable INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_steps (
    agent_run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    input_summary TEXT,
    output_summary TEXT,
    metadata_json TEXT NOT NULL,
    PRIMARY KEY (agent_run_id, ordinal),
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_runs (
    task_run_id TEXT PRIMARY KEY,
    agent_run_id TEXT,
    user_id TEXT,
    conversation_id INTEGER,
    idempotency_key TEXT,
    request_hash TEXT,
    idempotency_scope TEXT NOT NULL DEFAULT 'standalone',
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    current_step_id TEXT,
    plan_json TEXT,
    result_json TEXT,
    error TEXT,
    error_code TEXT,
    retryable INTEGER,
    latency_ms REAL,
    success INTEGER,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (agent_run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    scope TEXT NOT NULL,
    user_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    state TEXT NOT NULL,
    response_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    PRIMARY KEY (scope, user_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS task_steps (
    task_run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    description TEXT,
    tool_name TEXT NOT NULL,
    status TEXT NOT NULL,
    tool_args_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    latency_ms REAL,
    started_at TEXT,
    finished_at TEXT,
    PRIMARY KEY (task_run_id, step_id),
    UNIQUE (task_run_id, ordinal),
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_events (
    event_id TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    step_id TEXT,
    message TEXT,
    metadata_json TEXT NOT NULL,
    UNIQUE (task_run_id, sequence_no),
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_owner_conversation_created
    ON agent_runs(user_id, conversation_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_runs_idempotency
    ON agent_runs(kind, user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_runs_owner_created
    ON task_runs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_runs_agent_created
    ON task_runs(agent_run_id, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_task_runs_idempotency
    ON task_runs(idempotency_scope, user_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_task_events_run_sequence
    ON task_events(task_run_id, sequence_no);

CREATE INDEX IF NOT EXISTS idx_idempotency_expiry
    ON idempotency_records(expires_at)
    WHERE expires_at IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_task_run_scope_insert
BEFORE INSERT ON task_runs
WHEN NEW.agent_run_id IS NOT NULL
     AND EXISTS (
        SELECT 1
        FROM agent_runs AS parent
        WHERE parent.run_id = NEW.agent_run_id
          AND (
              parent.user_id IS NOT NEW.user_id
              OR parent.conversation_id IS NOT NEW.conversation_id
          )
     )
BEGIN
    SELECT RAISE(ABORT, 'task_run_parent_scope_mismatch');
END;

CREATE TRIGGER IF NOT EXISTS trg_task_run_scope_update
BEFORE UPDATE OF agent_run_id, user_id, conversation_id ON task_runs
WHEN NEW.agent_run_id IS NOT NULL
     AND EXISTS (
        SELECT 1
        FROM agent_runs AS parent
        WHERE parent.run_id = NEW.agent_run_id
          AND (
              parent.user_id IS NOT NEW.user_id
              OR parent.conversation_id IS NOT NEW.conversation_id
          )
     )
BEGIN
    SELECT RAISE(ABORT, 'task_run_parent_scope_mismatch');
END;
