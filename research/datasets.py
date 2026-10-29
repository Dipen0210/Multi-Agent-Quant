"""Frozen historical dataset identities and authoritative membership checks."""
from datetime import date, datetime, timedelta, timezone
import json
from typing import Literal
from pydantic import Field, field_validator, model_validator
from research.contracts import Contract, Document, MarketObservation, UNIVERSE, utc
from research.reports import Digest
from research.store import canonical, digest, now


class DatasetRequest(Contract):
    instrument_id: str
    start: date
    end: date
    provenance: Literal['synthetic','historical_approximate','recorded','live']='synthetic'
    document_lookback_days: int = Field(default=30,ge=1,le=365)

    @model_validator(mode='after')
    def bounds(self):
        if self.instrument_id not in UNIVERSE: raise ValueError('Unsupported instrument')
        if not self.start<self.end or (self.end-self.start).days>550: raise ValueError('Dataset must cover 2–550 calendar days')
        return self


class DatasetManifest(Contract):
    document_ids: list[Digest] = Field(max_length=2000)
    market_ids: list[Digest] = Field(min_length=1,max_length=2000)
    revision_policy: Literal['all_versions_preserved']
    universe: Literal['Fixed current AAPL/MSFT/SPY universe; excludes delisted names; survivorship and universe-selection bias apply.']
    validity_tier: Literal['synthetic_pipeline','historical_limited_metadata']

    @field_validator('document_ids','market_ids')
    @classmethod
    def unique_sorted(cls,value):
        if value!=sorted(set(value)): raise ValueError('Dataset references must be sorted and unique')
        return value


class DatasetResponse(Contract):
    id: Digest
    created_at: datetime
    request: DatasetRequest
    manifest: DatasetManifest

    _aware = field_validator('created_at')(classmethod(lambda cls,value:utc(value)))

    @model_validator(mode='after')
    def identity(self):
        payload={'request':self.request.model_dump(mode='json'),'manifest':self.manifest.model_dump(mode='json')}
        if self.id!=digest(payload): raise ValueError('Dataset identity differs from frozen inputs')
        expected='synthetic_pipeline' if self.request.provenance=='synthetic' else 'historical_limited_metadata'
        if self.manifest.validity_tier!=expected: raise ValueError('Dataset validity tier differs from provenance')
        return self


class DatasetList(Contract):
    items: list[DatasetResponse] = Field(max_length=100)


class DatasetIntegrityError(ValueError):
    """Stored data corruption; never expose raw validation inputs to clients."""


def freeze_dataset(store,request: DatasetRequest):
    end=datetime.combine(request.end,datetime.max.time(),tzinfo=timezone.utc)
    begin=datetime.combine(request.start-timedelta(days=request.document_lookback_days),datetime.min.time(),tzinfo=timezone.utc)
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        docs=[];bars=[]
        for row in c.execute('SELECT id,data FROM documents WHERE available_at BETWEEN ? AND ?',(begin.isoformat(),end.isoformat())):
            doc=Document.model_validate_json(row['data'])
            if request.instrument_id in doc.instrument_ids and doc.provenance==request.provenance: docs.append(row['id'])
        for row in c.execute('SELECT id,data FROM market WHERE instrument_id=?',(request.instrument_id,)):
            bar=MarketObservation.model_validate_json(row['data'])
            if request.start-timedelta(days=10)<=bar.interval_start.date()<=request.end and bar.provenance==request.provenance:
                bars.append(row['id'])
        if len(docs)>2000 or len(bars)>2000: raise ValueError('Dataset record budget exceeded')
        if not bars: raise ValueError('No market records in requested dataset')
        manifest={'document_ids':sorted(docs),'market_ids':sorted(bars),'revision_policy':'all_versions_preserved',
            'universe':'Fixed current AAPL/MSFT/SPY universe; excludes delisted names; survivorship and universe-selection bias apply.',
            'validity_tier':'synthetic_pipeline' if request.provenance=='synthetic' else 'historical_limited_metadata'}
        payload=request.model_dump(mode='json');ident=digest({'request':payload,'manifest':manifest})
        created=c.execute('INSERT OR IGNORE INTO datasets VALUES (?,?,?,?)',(ident,now(),canonical(payload),canonical(manifest))).rowcount
        if created:
            for key in docs: c.execute('INSERT INTO dataset_documents VALUES (?,?)',(ident,key))
            for key in bars: c.execute('INSERT INTO dataset_market VALUES (?,?)',(ident,key))
    return get_dataset(store,ident)


def get_dataset(store,ident):
    with store.connect() as c:
        # One read transaction covers the manifest, membership links and sources.
        c.execute('BEGIN')
        row=c.execute('SELECT * FROM datasets WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError('Dataset not found')
        try:
            data=DatasetResponse.model_validate(dict(row)|{
                'request':json.loads(row['request']),'manifest':json.loads(row['manifest'])})
            request=data.request
            begin=datetime.combine(request.start-timedelta(days=request.document_lookback_days),datetime.min.time(),tzinfo=timezone.utc)
            end=datetime.combine(request.end,datetime.max.time(),tzinfo=timezone.utc)
            for kind,table,source,model,expected in (
                ('document','dataset_documents','documents',Document,data.manifest.document_ids),
                ('market','dataset_market','market',MarketObservation,data.manifest.market_ids),
            ):
                # Names above are fixed application constants, never user input.
                rows=c.execute(f'SELECT links.{kind}_id linked_id,records.* FROM {table} links LEFT JOIN {source} records ON records.id=links.{kind}_id WHERE links.dataset_id=? ORDER BY links.{kind}_id LIMIT 2001',(ident,)).fetchall()
                if [r['linked_id'] for r in rows]!=expected:
                    raise ValueError('Dataset membership differs from frozen manifest')
                for record in rows:
                    if record['data'] is None: raise ValueError('Dataset source is missing')
                    item=model.model_validate_json(record['data'])
                    if digest(item.model_dump(mode='json'))!=record['id']:
                        raise ValueError('Dataset source identity mismatch')
                    if any(record[key]!=getattr(item,key) for key in ('provider','original_id','revision')) or datetime.fromisoformat(record['available_at'])!=item.available_at:
                        raise ValueError('Dataset source envelope mismatch')
                    if item.provenance!=request.provenance:
                        raise ValueError('Dataset source provenance mismatch')
                    if kind=='document':
                        if record['content_hash']!=digest(item.content): raise ValueError('Document content hash mismatch')
                        if request.instrument_id not in item.instrument_ids or not begin<=item.available_at<=end:
                            raise ValueError('Document is outside dataset scope')
                    elif record['instrument_id']!=item.instrument_id or item.instrument_id!=request.instrument_id or not request.start-timedelta(days=10)<=item.interval_start.date()<=request.end:
                        raise ValueError('Market observation is outside dataset scope')
        except (ValueError,TypeError,OverflowError) as exc:
            raise DatasetIntegrityError('Stored dataset failed integrity validation') from exc
    return data.model_dump(mode='json')


