"""Shared durable study lifecycle contracts."""
from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from research.contracts import Contract, utc
from research.reports import Digest
from research.store import digest

RequestT=TypeVar('RequestT',bound=Contract)
ResultT=TypeVar('ResultT',bound=Contract)


class StudyIntegrityError(ValueError):
    """Stored study/output corruption; details may contain source text."""


class StudySummary(Contract):
    id: UUID
    kind: Literal['evaluation','experiment']
    status: Literal['queued','running','completed','failed','cancelled']
    created_at: datetime
    updated_at: datetime
    error: str | None

    @field_validator('created_at','updated_at')
    @classmethod
    def aware(cls,value): return utc(value)

    @model_validator(mode='after')
    def times(self):
        if self.updated_at<self.created_at: raise ValueError('Study timestamps out of order')
        if self.status=='failed' and not self.error: raise ValueError('Failed study requires an error')
        return self


class StudyState(StudySummary,Generic[RequestT,ResultT]):
    idempotency_key: str = Field(min_length=1,max_length=160)
    request_hash: Digest
    request: RequestT
    cancelled: int = Field(ge=0,le=1,strict=True)
    result: ResultT | None
    attempt: int = Field(ge=0,strict=True)

    @model_validator(mode='after')
    def consistent(self):
        if self.request_hash!=digest({'kind':self.kind,'request':self.request.model_dump(mode='json')}):
            raise ValueError('Study request identity mismatch')
        if self.status=='completed':
            if self.result is None or self.cancelled or self.error or self.attempt<1:
                raise ValueError('Completed study has inconsistent status metadata')
        elif self.result is not None:
            raise ValueError('Uncompleted study cannot expose an accepted result')
        if self.status=='running' and self.attempt<1: raise ValueError('Running study requires an attempt')
        return self


class StudyList(Contract):
    items: list[StudySummary] = Field(max_length=100)
