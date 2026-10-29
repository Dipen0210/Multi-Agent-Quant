"""Response contracts for evidence, imports, snapshots and configurations."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from research.configuration import Configuration
from research.contracts import Contract, Document, Identifier, MarketObservation, UNIVERSE, utc
from research.reports import Digest
from research.store import digest


class Instrument(Contract):
    id: Identifier
    symbol: str
    name: str
    calendar: Literal['XNYS']
    currency: Literal['USD']

    @model_validator(mode='after')
    def known(self):
        if self.id not in UNIVERSE or self.model_dump(exclude={'id'})!=UNIVERSE[self.id]:
            raise ValueError('Instrument metadata differs from supported universe')
        return self


class InstrumentList(Contract):
    items: list[Instrument] = Field(min_length=3,max_length=3)
    universe_policy: str = Field(min_length=1)
    frequency: Literal['daily']
    timezone: Literal['America/New_York']

    @model_validator(mode='after')
    def complete_universe(self):
        if {item.id for item in self.items}!=set(UNIVERSE): raise ValueError('Incomplete instrument universe')
        return self


class StoredRecord(Contract):
    id: Digest
    provider: Identifier
    original_id: Identifier
    revision: int = Field(ge=1,strict=True)
    available_at: datetime
    ingested_at: datetime

    @field_validator('available_at','ingested_at')
    @classmethod
    def aware(cls,value): return utc(value)

    def verify(self,data):
        if self.id!=digest(data.model_dump(mode='json')):
            raise ValueError('Evidence identity does not match its stored content')
        if any(getattr(self,key)!=getattr(data,key) for key in ('provider','original_id','revision','available_at')):
            raise ValueError('Evidence envelope differs from source metadata')


class DocumentResponse(StoredRecord):
    content_hash: Digest
    data: Document

    @model_validator(mode='after')
    def integrity(self):
        self.verify(self.data)
        if self.content_hash!=digest(self.data.content): raise ValueError('Document content hash mismatch')
        return self


class MarketResponse(StoredRecord):
    instrument_id: Identifier
    data: MarketObservation

    @model_validator(mode='after')
    def integrity(self):
        self.verify(self.data)
        if self.instrument_id!=self.data.instrument_id: raise ValueError('Market instrument mismatch')
        return self


class EvidenceList(Contract):
    documents: list[DocumentResponse] = Field(max_length=500)
    market: list[MarketResponse] = Field(max_length=500)


class Rejection(Contract):
    kind: Literal['document','market','recorded_adapter']
    row: int = Field(ge=0,le=499,strict=True)
    reason: str = Field(min_length=1)


class ImportReceipt(Contract):
    batch_id: UUID
    inserted: int = Field(ge=0,le=500,strict=True)
    duplicates: int = Field(ge=0,le=500,strict=True)
    rejected: list[Rejection] = Field(max_length=500)
    document_ids: list[Digest] = Field(max_length=500)
    market_ids: list[Digest] = Field(max_length=500)

    @model_validator(mode='after')
    def counts(self):
        if self.inserted+self.duplicates!=len(self.document_ids)+len(self.market_ids):
            raise ValueError('Import receipt count mismatch')
        if self.inserted+self.duplicates+len(self.rejected)>500:
            raise ValueError('Import receipt exceeds batch budget')
        return self


class DemoReceipt(ImportReceipt):
    mode: Literal['synthetic']
    description: str = Field(min_length=1)


class SourceHealth(Contract):
    provider: Identifier
    kind: Literal['documents','market']
    latest_available_at: datetime
    latest_import_at: datetime
    records: int = Field(ge=1,strict=True)

    @field_validator('latest_available_at','latest_import_at')
    @classmethod
    def aware(cls,value): return utc(value)


class SourceHealthResponse(Contract):
    sources: list[SourceHealth] = Field(max_length=100)
    rejected_records: int = Field(ge=0,strict=True)
    live_adapters: Literal['not validated']
    freshness_policy: str = Field(min_length=1)


class ConfigurationResponse(Contract):
    id: Digest
    data: Configuration
    created_at: datetime | None = None

    @field_validator('created_at')
    @classmethod
    def aware(cls,value): return utc(value) if value is not None else None

    @model_validator(mode='after')
    def identity(self):
        if self.id!=digest(self.data.model_dump(mode='json')): raise ValueError('Configuration identity mismatch')
        return self


class ConfigurationActivation(Contract):
    active_configuration_id: Digest


class ConfigurationList(ConfigurationActivation):
    items: list[ConfigurationResponse] = Field(max_length=100)
