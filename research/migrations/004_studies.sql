CREATE TABLE IF NOT EXISTS datasets (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, request TEXT NOT NULL, manifest TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dataset_documents (
 dataset_id TEXT REFERENCES datasets(id), document_id TEXT REFERENCES documents(id),
 PRIMARY KEY(dataset_id,document_id)
);
CREATE TABLE IF NOT EXISTS dataset_market (
 dataset_id TEXT REFERENCES datasets(id), market_id TEXT REFERENCES market(id),
 PRIMARY KEY(dataset_id,market_id)
);
CREATE TABLE IF NOT EXISTS studies (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('evaluation','experiment')),
 idempotency_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL, request TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled')),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0,
 result TEXT, error TEXT, attempt INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER IF NOT EXISTS datasets_no_update BEFORE UPDATE ON datasets BEGIN SELECT RAISE(ABORT,'immutable dataset'); END;
CREATE TRIGGER IF NOT EXISTS datasets_no_delete BEFORE DELETE ON datasets BEGIN SELECT RAISE(ABORT,'immutable dataset'); END;
