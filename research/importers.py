"""Bounded local content imports. No path traversal or arbitrary URL fetching surface."""
import csv
import io
import json

MAX_BYTES = 2_000_000


def parse_csv(content: str, kind: str):
    if len(content.encode()) > MAX_BYTES:
        raise ValueError('Import exceeds 2 MB')
    if kind not in {'documents','market'}:
        raise ValueError('Unsupported import kind')
    rows = []
    for row in csv.DictReader(io.StringIO(content)):
        if len(rows) >= 500: raise ValueError('Import exceeds 500 rows')
        for key in ('instrument_ids','quality_flags'):
            if key in row:
                row[key] = json.loads(row[key])
        for key in ('source_url','event_at','first_observed_at','latency_assumption_seconds'):
            if key in row and row[key] == '': row[key] = None
        rows.append(row)
    return rows
