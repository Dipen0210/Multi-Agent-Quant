"""Strict boundary contracts. Availability is distinct from publication/import time."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=160, pattern=r'^[A-Za-z0-9_.:/-]+$')]
Provenance = Literal['synthetic', 'recorded', 'live', 'historical_approximate']
UNIVERSE = {
    'US:AAPL': {'symbol':'AAPL','name':'Apple Inc.','calendar':'XNYS','currency':'USD'},
    'US:MSFT': {'symbol':'MSFT','name':'Microsoft Corporation','calendar':'XNYS','currency':'USD'},
    'US:SPY': {'symbol':'SPY','name':'SPDR S&P 500 ETF Trust','calendar':'XNYS','currency':'USD'},
}


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('An explicit timezone offset is required')
    return value.astimezone(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, validate_assignment=True)


class Document(Contract):
    provider: Identifier
    original_id: Identifier
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=1000)
    content: str = Field(min_length=1, max_length=100_000)
    source_url: str | None = Field(default=None, max_length=2000)
    language: str = Field(default='en', min_length=2, max_length=16)
    instrument_ids: list[Identifier] = Field(min_length=1, max_length=3)
    entity_status: Literal['resolved','ambiguous','unresolved'] = 'resolved'
    event_at: datetime | None = None
    published_at: datetime
    first_observed_at: datetime | None = None
    provenance: Provenance
    latency_assumption_seconds: int | None = Field(default=None, ge=0, le=604800)
    usage_restrictions: str = Field(min_length=1, max_length=1000)

    @field_validator('event_at','published_at','first_observed_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value is not None else value

    @field_validator('instrument_ids')
    @classmethod
    def known_entities(cls, values):
        if len(set(values)) != len(values) or any(v not in UNIVERSE for v in values):
            raise ValueError('Unsupported or repeated instrument identity')
        return sorted(values)

    @field_validator('source_url')
    @classmethod
    def safe_reference(cls, value):
        if value is not None:
            url = urlsplit(value)
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise ValueError('Source reference must be HTTPS without credentials')
        return value

    @model_validator(mode='after')
    def availability_policy(self):
        if self.first_observed_at is None:
            if self.provenance != 'historical_approximate' or self.latency_assumption_seconds is None:
                raise ValueError('Missing first observation requires historical_approximate and explicit latency')
        elif self.first_observed_at < self.published_at:
            raise ValueError('First observation cannot precede publication')
        return self

    @property
    def available_at(self) -> datetime:
        return self.first_observed_at or self.published_at + timedelta(seconds=self.latency_assumption_seconds or 0)


class MarketObservation(Contract):
    instrument_id: Identifier
    provider: Identifier
    original_id: Identifier
    revision: int = Field(ge=1)
    calendar: Literal['XNYS'] = 'XNYS'
    interval: Literal['1d'] = '1d'
    interval_start: datetime
    interval_end: datetime
    available_at: datetime
    currency: Literal['USD'] = 'USD'
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    adjustment_policy: Literal['raw','split_adjusted','total_return']
    provenance: Provenance
    quality_flags: list[str] = Field(default_factory=list, max_length=20)
    usage_restrictions: str = Field(min_length=1, max_length=1000)

    @field_validator('interval_start','interval_end','available_at')
    @classmethod
    def aware(cls, value):
        return utc(value)

    @field_validator('instrument_id')
    @classmethod
    def known_entity(cls, value):
        if value not in UNIVERSE:
            raise ValueError('Unsupported instrument identity')
        return value

    @model_validator(mode='after')
    def consistent(self):
        if not (self.low <= min(self.open,self.close) <= max(self.open,self.close) <= self.high):
            raise ValueError('Inconsistent OHLC prices')
        if not self.interval_start < self.interval_end <= self.available_at:
            raise ValueError('Bar availability must follow the complete interval')
        from research.calendar import validate_session
        validate_session(self.interval_start,self.interval_end)
        return self


class SnapshotRequest(Contract):
    instrument_ids: list[Identifier] = Field(min_length=1, max_length=3)
    cutoff: datetime
    window_days: int = Field(default=30, ge=1, le=365)
    market_max_age_days: int = Field(default=7, ge=1, le=30)
    provenance: Provenance = 'synthetic'

    _aware = field_validator('cutoff')(classmethod(lambda cls, value: utc(value)))
    _known = field_validator('instrument_ids')(classmethod(lambda cls, value: Document.known_entities(value)))
