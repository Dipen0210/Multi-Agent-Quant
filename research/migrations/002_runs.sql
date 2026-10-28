CREATE TABLE IF NOT EXISTS configurations (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS active_configuration (singleton INTEGER PRIMARY KEY CHECK(singleton=1), configuration_id TEXT REFERENCES configurations(id));
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL,
 snapshot_id TEXT NOT NULL REFERENCES snapshots(id), configuration_id TEXT NOT NULL REFERENCES configurations(id),
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','partial','failed','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0,
 attempt INTEGER NOT NULL DEFAULT 0, request TEXT NOT NULL, report TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS steps (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), parent_step_id TEXT REFERENCES steps(id),
 attempt INTEGER NOT NULL, ordinal INTEGER NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT, latency_ms REAL, data TEXT NOT NULL,
 UNIQUE(run_id,attempt,ordinal)
);
CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inference_recordings (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), input_hash TEXT NOT NULL, output TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS configurations_no_update BEFORE UPDATE ON configurations BEGIN SELECT RAISE(ABORT,'immutable configuration'); END;
CREATE TRIGGER IF NOT EXISTS configurations_no_delete BEFORE DELETE ON configurations BEGIN SELECT RAISE(ABORT,'immutable configuration'); END;
CREATE TRIGGER IF NOT EXISTS recordings_no_update BEFORE UPDATE ON inference_recordings BEGIN SELECT RAISE(ABORT,'immutable recording'); END;
CREATE TRIGGER IF NOT EXISTS recordings_no_delete BEFORE DELETE ON inference_recordings BEGIN SELECT RAISE(ABORT,'immutable recording'); END;
