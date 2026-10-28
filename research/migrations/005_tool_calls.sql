CREATE TABLE IF NOT EXISTS tool_calls (
 id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES runs(id),
 step_id TEXT NOT NULL REFERENCES steps(id),
 parent_call_id TEXT REFERENCES tool_calls(id),
 attempt INTEGER NOT NULL,
 ordinal INTEGER NOT NULL,
 tool_name TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
 started_at TEXT NOT NULL,
 finished_at TEXT,
 latency_ms REAL,
 data TEXT NOT NULL,
 UNIQUE(step_id, ordinal)
);
CREATE INDEX IF NOT EXISTS tool_calls_run ON tool_calls(run_id, attempt, step_id, ordinal);
