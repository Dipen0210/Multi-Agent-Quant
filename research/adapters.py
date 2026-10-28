"""Normalize recorded payloads from existing providers without initiating network requests.
Publication/observation timestamps must be supplied; a date-only string is not silently promoted to a timestamp.
"""
from datetime import datetime, timedelta
import hashlib
from research.calendar import session_times
from research.contracts import Document, MarketObservation, utc


def normalize_text(provider, raw, instrument_ids, captured_at, usage_restrictions):
    captured_at=utc(captured_at)
    if provider=='tavily':
        title=raw.get('title');content=raw.get('raw_content') or raw.get('content');url=raw.get('url')
        original=raw.get('id') or hashlib.sha256(str(url).encode()).hexdigest()
        published=raw.get('published_at') or raw.get('published_date')
    elif provider=='sec_edgar':
        title=raw.get('form');content=raw.get('text');url=raw.get('url');original=raw.get('accession')
        published=raw.get('acceptanceDateTime') or raw.get('accepted_at')
    elif provider=='reddit':
        title=raw.get('title');content=(raw.get('title') or '')+'\n'+(raw.get('selftext') or '')
        permalink=raw.get('permalink','');url='https://www.reddit.com'+permalink if permalink.startswith('/r/') else None
        original=raw.get('id')
        created=raw.get('created_utc')
        from datetime import timezone
        published=datetime.fromtimestamp(created,tz=timezone.utc) if isinstance(created,(int,float)) else None
    else:
        raise ValueError('Unsupported recorded text provider')
    return Document(provider=provider,original_id=original,revision=raw.get('revision',1),title=title,content=content,
        source_url=url,instrument_ids=instrument_ids,published_at=published,first_observed_at=captured_at,
        provenance='recorded',usage_restrictions=usage_restrictions).model_dump(mode='json')


def normalize_yfinance(raw,instrument_id,latency_seconds,usage_restrictions):
    """Historical availability is an explicit approximation, never the import/download time."""
    if not isinstance(latency_seconds,int) or not 0<=latency_seconds<=604800:
        raise ValueError('Explicit bounded historical latency assumption required')
    start,end=session_times(raw['session'])
    return MarketObservation(instrument_id=instrument_id,provider='yfinance',original_id=instrument_id+'/'+raw['session'],
        revision=raw.get('revision',1),interval_start=start,interval_end=end,available_at=end+timedelta(seconds=latency_seconds),
        open=raw['Open'],high=raw['High'],low=raw['Low'],close=raw['Close'],volume=raw['Volume'],
        adjustment_policy=raw['adjustment_policy'],provenance='historical_approximate',
        usage_restrictions=usage_restrictions+'; historical availability assumes '+str(latency_seconds)+' seconds after session close.').model_dump(mode='json')
