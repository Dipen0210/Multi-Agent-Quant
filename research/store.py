"""Single-user SQLite evidence store with immutable versions and explicit receipts."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import uuid
from pydantic import ValidationError
from research.contracts import Document, MarketObservation, SnapshotRequest, UNIVERSE


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalized(text):
    return re.sub(r'\W+', ' ', text.casefold()).strip()


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path == ':memory:':
            raise ValueError('Use a temporary file for tests; each connection is independent')
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA journal_mode=WAL')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self):
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, checksum TEXT NOT NULL)')
            for file in sorted(Path(__file__).with_name('migrations').glob('*.sql')):
                sql = file.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                row = conn.execute('SELECT checksum FROM schema_migrations WHERE name=?',(file.name,)).fetchone()
                if row:
                    if row['checksum'] != checksum:
                        raise RuntimeError('Applied migration checksum changed')
                    continue
                # SQL is trusted versioned application code, never supplied by users/models.
                conn.executescript('BEGIN IMMEDIATE;\n'+sql+'\nCOMMIT;')
                conn.execute('INSERT INTO schema_migrations VALUES (?,?)',(file.name,checksum))
            for key,value in UNIVERSE.items():
                conn.execute('INSERT OR IGNORE INTO instruments VALUES (?,?,?)',(key,value['symbol'],canonical(value)))

    def import_records(self, documents=None, market=None, external_rejections=None):
        documents, market = documents or [], market or []
        if len(documents)+len(market) > 500:
            raise ValueError('Import limited to 500 records per batch')
        batch = str(uuid.uuid4())
        result = {'batch_id':batch,'inserted':0,'duplicates':0,'rejected':[], 'document_ids':[], 'market_ids':[]}
        with self.connect() as conn:
            for rejection in external_rejections or []:
                result['rejected'].append({key:rejection[key] for key in ('kind','row','reason')})
                conn.execute('INSERT INTO rejections(batch_id,kind,row_number,input_hash,reason) VALUES (?,?,?,?,?)',
                    (batch,rejection['kind'],rejection['row'],rejection['input_hash'],rejection['reason']))
            for kind,records,model in [('document',documents,Document),('market',market,MarketObservation)]:
                for index,raw in enumerate(records):
                    try:
                        value = model.model_validate(raw)
                        data = value.model_dump(mode='json')
                        ident = digest(data)
                        table = 'documents' if kind=='document' else 'market'
                        revisions = conn.execute(f'SELECT revision,available_at,data FROM {table} WHERE provider=? AND original_id=?', (value.provider,value.original_id)).fetchall()
                        for previous in revisions:
                            old = json.loads(previous['data'])
                            if old['provenance'] != value.provenance:
                                raise ValueError('Provenance must remain stable across revisions')
                            if kind == 'market' and (old['instrument_id'] != value.instrument_id or old['interval_start'] != data['interval_start']):
                                raise ValueError('Market identity and interval must remain stable across revisions')
                            if ((previous['revision'] < value.revision and previous['available_at'] > value.available_at.isoformat()) or
                                (previous['revision'] > value.revision and previous['available_at'] < value.available_at.isoformat())):
                                raise ValueError('Revision availability order is inconsistent')
                        exists = conn.execute(f'SELECT id FROM {table} WHERE provider=? AND original_id=? AND revision=?',
                            (value.provider,value.original_id,value.revision)).fetchone()
                        if exists:
                            if exists['id'] != ident:
                                raise ValueError('Immutable version conflict; import a new revision identity')
                            result['duplicates'] += 1
                        elif kind == 'document':
                            conn.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',
                                (ident,value.provider,value.original_id,value.revision,digest(value.content),value.available_at.isoformat(),now(),canonical(data)))
                            for instrument in value.instrument_ids:
                                conn.execute('INSERT INTO document_instruments VALUES (?,?)',(ident,instrument))
                            result['inserted'] += 1
                        else:
                            conn.execute('INSERT INTO market VALUES (?,?,?,?,?,?,?,?)',
                                (ident,value.instrument_id,value.provider,value.original_id,value.revision,value.available_at.isoformat(),now(),canonical(data)))
                            result['inserted'] += 1
                        result[kind+'_ids'].append(ident)
                    except (ValidationError, ValueError) as exc:
                        reason = '; '.join(f"{'.'.join(str(x) for x in e['loc'])}: {e['type']}" for e in exc.errors()) if isinstance(exc,ValidationError) else str(exc)
                        result['rejected'].append({'kind':kind,'row':index,'reason':reason})
                        # Retain a fingerprint, not raw rejected content (which can contain secrets).
                        raw_hash = hashlib.sha256(json.dumps(raw,sort_keys=True,default=str).encode()).hexdigest()
                        conn.execute('INSERT INTO rejections(batch_id,kind,row_number,input_hash,reason) VALUES (?,?,?,?,?)',
                            (batch,kind,index,raw_hash,reason))
            conn.execute('INSERT INTO import_batches VALUES (?,?,?)',(batch,now(),canonical(result)))
        return result

    def records(self, table, limit=100):
        if table not in {'documents','market'}:
            raise ValueError('Unsupported record collection')
        with self.connect() as conn:
            rows = conn.execute(f'SELECT * FROM {table} ORDER BY available_at DESC,id LIMIT ?', (min(max(limit,1),500),)).fetchall()
        return [dict(row) | {'data':json.loads(row['data'])} for row in rows]

    def document(self, ident):
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM documents WHERE id=?',(ident,)).fetchone()
        if not row:
            raise KeyError('Document not found')
        return dict(row) | {'data':json.loads(row['data'])}

    def snapshot(self, request: SnapshotRequest):
        lower = request.cutoff - timedelta(days=request.window_days)
        market_lower = request.cutoff - timedelta(days=request.market_max_age_days)
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            # Filtering happens BEFORE latest-version selection. Later revisions never replace past evidence.
            rows = conn.execute('SELECT * FROM documents WHERE available_at BETWEEN ? AND ? ORDER BY revision DESC,available_at DESC,id LIMIT 10001',
                                (lower.isoformat(),request.cutoff.isoformat())).fetchall()
            if len(rows)>10000: raise ValueError('Snapshot scan budget exceeded; narrow the window')
            docs, seen = [], set()
            for row in rows:
                data = Document.model_validate_json(row['data'])
                key = (data.provider,data.original_id)
                if key in seen: continue
                seen.add(key)
                if (data.provenance != request.provenance or data.available_at < lower or data.entity_status != 'resolved'
                        or not set(data.instrument_ids).intersection(request.instrument_ids)):
                    continue
                docs.append(dict(row) | {'data':data.model_dump(mode='json')})
            if len(docs)>500:
                raise ValueError('Evidence window exceeds 500 documents; narrow the window')
            bars, seen = [], set()
            market_rows=conn.execute('SELECT * FROM market WHERE available_at BETWEEN ? AND ? ORDER BY revision DESC,id LIMIT 10001',(market_lower.isoformat(),request.cutoff.isoformat())).fetchall()
            if len(market_rows)>10000: raise ValueError('Market scan budget exceeded; narrow the window')
            for row in market_rows:
                data = MarketObservation.model_validate_json(row['data'])
                key = (data.provider,data.original_id)
                if key in seen: continue
                seen.add(key)
                if data.provenance == request.provenance and data.instrument_id in request.instrument_ids and data.available_at >= market_lower and not data.quality_flags:
                    bars.append(row['id'])
            # Conservative near-duplicate grouping keeps every version/provenance reference.
            groups = []
            for row in sorted(docs,key=lambda d:(d['available_at'],d['id'])):
                text = normalized(row['data']['content'])
                tokens = text.split()[:1000]
                shingles = {tuple(tokens[i:i+5]) for i in range(max(0,len(tokens)-4))}
                for group in groups:
                    similarity = len(shingles & group['shingles']) / max(1,len(shingles | group['shingles']))
                    if text == group['text'] or (len(shingles) >= 10 and similarity >= .90):
                        group['document_ids'].append(row['id'])
                        break
                else:
                    groups.append({'text':text,'shingles':shingles,'document_ids':[row['id']]})
            manifest = {'document_ids':sorted(d['id'] for d in docs),'market_ids':sorted(bars),
                        'duplicate_groups':[g['document_ids'] for g in groups],
                        'availability_policy':'first-observed-or-explicit-latency-v1',
                        'deduplication_policy':'normalized-exact-or-five-word-jaccard-0.90-first-1000-words-v1',
                        'validity_tier':'synthetic_pipeline' if request.provenance=='synthetic' else 'historical_limited_metadata',
                        'limitations':['Imported timestamps are supplied metadata, not independently certified point-in-time capture.']}
            payload = request.model_dump(mode='json')
            ident = digest({'request':payload,'manifest':manifest})
            conn.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?)',(ident,now(),canonical(payload),canonical(manifest)))
            for doc in manifest['document_ids']:
                conn.execute('INSERT OR IGNORE INTO snapshot_documents VALUES (?,?)',(ident,doc))
            for bar in manifest['market_ids']:
                conn.execute('INSERT OR IGNORE INTO snapshot_market VALUES (?,?)',(ident,bar))
        return {'id':ident,'request':payload,'manifest':manifest}

    def get_snapshot(self, ident):
        with self.connect() as conn:
            row = conn.execute('SELECT * FROM snapshots WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError('Snapshot not found')
        return {'id':row['id'],'created_at':row['created_at'],'request':json.loads(row['request']),'manifest':json.loads(row['manifest'])}
