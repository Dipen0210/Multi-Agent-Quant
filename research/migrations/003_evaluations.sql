CREATE TABLE IF NOT EXISTS evaluation_runs (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, dataset_hash TEXT NOT NULL,
 configuration TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS experiment_runs (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
 request TEXT NOT NULL, result TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS review_decisions (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, dataset_hash TEXT NOT NULL,
 case_id TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, rationale TEXT NOT NULL
);
