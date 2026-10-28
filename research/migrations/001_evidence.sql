CREATE TABLE IF NOT EXISTS instruments (id TEXT PRIMARY KEY, symbol TEXT NOT NULL UNIQUE, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
 id TEXT PRIMARY KEY, provider TEXT NOT NULL, original_id TEXT NOT NULL, revision INTEGER NOT NULL,
 content_hash TEXT NOT NULL, available_at TEXT NOT NULL, ingested_at TEXT NOT NULL, data TEXT NOT NULL,
 UNIQUE(provider, original_id, revision)
);
CREATE TABLE IF NOT EXISTS document_instruments (
 document_id TEXT REFERENCES documents(id), instrument_id TEXT REFERENCES instruments(id),
 PRIMARY KEY(document_id,instrument_id)
);
CREATE TABLE IF NOT EXISTS market (
 id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL REFERENCES instruments(id), provider TEXT NOT NULL,
 original_id TEXT NOT NULL, revision INTEGER NOT NULL, available_at TEXT NOT NULL,
 ingested_at TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(provider,original_id,revision)
);
CREATE TABLE IF NOT EXISTS import_batches (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rejections (
 id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL, kind TEXT NOT NULL, row_number INTEGER NOT NULL,
 input_hash TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, request TEXT NOT NULL, manifest TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshot_documents (
 snapshot_id TEXT REFERENCES snapshots(id), document_id TEXT REFERENCES documents(id),
 PRIMARY KEY(snapshot_id,document_id)
);
CREATE TABLE IF NOT EXISTS snapshot_market (
 snapshot_id TEXT REFERENCES snapshots(id), market_id TEXT REFERENCES market(id),
 PRIMARY KEY(snapshot_id,market_id)
);
CREATE INDEX IF NOT EXISTS documents_availability ON documents(available_at);
CREATE INDEX IF NOT EXISTS market_availability ON market(available_at);
CREATE TRIGGER IF NOT EXISTS documents_no_update BEFORE UPDATE ON documents BEGIN SELECT RAISE(ABORT,'immutable document'); END;
CREATE TRIGGER IF NOT EXISTS documents_no_delete BEFORE DELETE ON documents BEGIN SELECT RAISE(ABORT,'immutable document'); END;
CREATE TRIGGER IF NOT EXISTS market_no_update BEFORE UPDATE ON market BEGIN SELECT RAISE(ABORT,'immutable market observation'); END;
CREATE TRIGGER IF NOT EXISTS market_no_delete BEFORE DELETE ON market BEGIN SELECT RAISE(ABORT,'immutable market observation'); END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
