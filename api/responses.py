"""Validated research/run/trace response boundaries, including persisted output."""
from datetime import datetime
from typing import Literal
from pydantic import Field, field_validator, model_validator
from research.contracts import Contract, Identifier, utc
from research.jobs import RunRequest
from research.outputs import validate_output
from research.reports import Digest, ResearchReport
from research.store import digest

RunStatus = Literal['queued','running','completed','partial','failed','cancelled']


class RunSummary(Contract):
    id: Identifier
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    configuration_id: Digest
    snapshot_id: Digest

    @field_validator('created_at','updated_at')
    @classmethod
    def aware(cls, value): return utc(value)


class RunResponse(RunSummary):
    idempotency_key: str = Field(min_length=1,max_length=160)
    request_hash: Digest
    cancelled: Literal[0,1]
    attempt: int = Field(ge=0,strict=True)
    request: RunRequest
    report: ResearchReport | None
    error: str | None

    @model_validator(mode='after')
    def report_matches_run(self):
        if self.request.snapshot_id!=self.snapshot_id or self.request.configuration_id!=self.configuration_id:
            raise ValueError('Run input references do not match request')
        if self.request_hash!=digest(self.request.model_dump(mode='json')):
            raise ValueError('Stored request identity mismatch')
        if self.status in {'completed','partial'}:
            if self.report is None: raise ValueError('Finished research run requires its report')
            if (self.report.run_id!=self.id or self.report.snapshot.id!=self.snapshot_id
                    or self.report.configuration_id!=self.configuration_id
                    or self.report.question!=self.request.question or self.report.status!=self.status):
                raise ValueError('Report does not belong to this run')
        elif self.report is not None:
            raise ValueError('Unfinished or rejected run cannot serve an accepted report')
        return self


class RunList(Contract):
    items: list[RunSummary] = Field(max_length=100)


class ToolData(Contract):
    role: Literal['evidence','sentiment','quantitative','verification','report','model']
    tool_schema_version: Literal['v1']
    snapshot_id: Digest
    configuration_id: Digest
    input: dict
    input_hash: Digest
    resource_budget_seconds: float = Field(ge=0,le=180)
    validation_failures: list[str]
    tokens: int | None = Field(ge=0,strict=True)
    cost: float | None = Field(ge=0)
    output: dict | None = None
    model_identifier: dict | None = None
    model_parameters: dict | None = None

    @model_validator(mode='after')
    def input_identity(self):
        if self.input_hash!=digest(self.input): raise ValueError('Tool input identity mismatch')
        return self


class ToolCall(Contract):
    id: Identifier
    run_id: Identifier
    step_id: Identifier
    parent_call_id: Identifier | None
    attempt: int = Field(ge=1)
    ordinal: int = Field(ge=0,lt=30)
    tool_name: str = Field(min_length=1)
    status: Literal['running','completed','failed','cancelled']
    started_at: datetime
    finished_at: datetime | None
    latency_ms: float | None = Field(ge=0)
    data: ToolData

    @field_validator('started_at','finished_at')
    @classmethod
    def aware(cls, value): return utc(value) if value is not None else None

    @model_validator(mode='after')
    def completion(self):
        if self.status=='completed':
            if self.data.output is None or self.data.validation_failures or self.finished_at is None or self.latency_ms is None:
                raise ValueError('Completed tool call needs validated output and timing')
            validate_output(self.data.role,self.data.output)
        if self.finished_at is not None and self.finished_at<self.started_at:
            raise ValueError('Tool timestamps are reversed')
        return self


class ToolList(Contract):
    items: list[ToolCall] = Field(max_length=300)


class StepResponse(Contract):
    id: Identifier
    run_id: Identifier
    parent_step_id: Identifier | None
    attempt: int = Field(ge=1)
    ordinal: int = Field(ge=0)
    role: Literal['evidence','sentiment','quantitative','verification','report','research']
    status: Literal['running','completed','failed','cancelled']
    started_at: datetime
    finished_at: datetime | None
    latency_ms: float | None = Field(ge=0)
    data: dict
    tool_calls: list[ToolCall] = Field(max_length=30)

    @model_validator(mode='after')
    def child_references(self):
        if any(call.run_id!=self.run_id or call.step_id!=self.id or call.attempt!=self.attempt for call in self.tool_calls):
            raise ValueError('Tool trace attached to wrong step')
        identifiers={call.id for call in self.tool_calls}
        if any(call.parent_call_id is not None and call.parent_call_id not in identifiers for call in self.tool_calls):
            raise ValueError('Tool trace parent is outside its step')
        return self


class StepList(Contract):
    items: list[StepResponse] = Field(max_length=100)
