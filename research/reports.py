"""Final report contracts and cross-field invariants.

These validate structured research output, not the semantic correctness of a
sentiment label. Human grounding review remains a separate release requirement.
"""
from datetime import datetime
from typing import Annotated, Literal
from pydantic import Field, PrivateAttr, StrictBool, field_serializer, field_validator, model_validator

from research.contracts import Contract, Identifier, Provenance, SnapshotRequest, utc
from research.outputs import ModelOutput, QuantitativeResult, VerificationResult
from research.sentiment import SentimentResult, aggregate
from research.signals import SignalPolicy, research_signal
from research.store import digest

Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class SnapshotManifest(Contract):
    document_ids: list[Digest] = Field(max_length=500)
    market_ids: list[Digest] = Field(max_length=10000)
    duplicate_groups: list[list[Digest]] = Field(max_length=500)
    availability_policy: Literal['first-observed-or-explicit-latency-v1']
    deduplication_policy: Literal['normalized-exact-or-five-word-jaccard-0.90-first-1000-words-v1', 'normalized-exact-historical-v1']
    validity_tier: Literal['synthetic_pipeline', 'historical_limited_metadata']
    limitations: list[str] = Field(min_length=1)

    @model_validator(mode='after')
    def references(self):
        grouped = [item for group in self.duplicate_groups for item in group]
        if (len(set(self.document_ids)) != len(self.document_ids)
                or len(set(self.market_ids)) != len(self.market_ids)
                or any(not group for group in self.duplicate_groups)
                or sorted(grouped) != sorted(self.document_ids)):
            raise ValueError('Snapshot duplicate groups must partition unique document references')
        return self


class ReportSnapshot(Contract):
    id: Digest
    created_at: datetime | None = None
    request: SnapshotRequest
    manifest: SnapshotManifest
    _raw_request: dict | None = PrivateAttr(default=None)

    @model_validator(mode='wrap')
    @classmethod
    def preserve_frozen_request(cls, value, handler):
        result=handler(value)
        if isinstance(value,dict): result._raw_request=dict(value['request'])
        return result

    @field_serializer('request')
    def serialized_request(self, value):
        # Historical snapshots may use +00:00 rather than Z. Reformatting their
        # request would change the immutable snapshot hash on an API round trip.
        return self._raw_request if self._raw_request is not None else value.model_dump(mode='json')

    @model_validator(mode='before')
    @classmethod
    def identity(cls, value):
        # Check original timestamp representations before Pydantic normalizes them.
        if isinstance(value, dict) and {'id', 'request', 'manifest'} <= value.keys():
            if value['id'] != digest({'request': value['request'], 'manifest': value['manifest']}):
                raise ValueError('Snapshot identity does not match its frozen inputs')
        return value

    @field_validator('created_at')
    @classmethod
    def aware(cls, value):
        return utc(value) if value is not None else None


class SentimentSummary(Contract):
    status: Literal['supported', 'conflicting', 'insufficient_evidence']
    score: float | None = Field(ge=-1, le=1, strict=True)
    independent_sources: int = Field(ge=0, le=500, strict=True)
    raw_documents: int = Field(ge=0, le=500, strict=True)
    directional_sources: int = Field(ge=0, le=500, strict=True)
    positive: int = Field(ge=0, le=500, strict=True)
    negative: int = Field(ge=0, le=500, strict=True)
    excluded_or_uncertain: int = Field(ge=0, le=500, strict=True)
    policy: str = Field(min_length=1)


class ResearchSignal(Contract):
    policy: SignalPolicy
    hypothesis_only: StrictBool
    external_execution: StrictBool
    signal: Literal['NO_SIGNAL', 'LONG', 'FLAT']
    reason: str = Field(min_length=1)

    @model_validator(mode='after')
    def research_only(self):
        if not self.hypothesis_only or self.external_execution:
            raise ValueError('Research signals must be hypotheses with external execution disabled')
        return self


class Finding(Contract):
    sentiment: SentimentSummary
    quantitative: QuantitativeResult
    research_signal: ResearchSignal
    counterevidence: list[Digest] = Field(max_length=500)
    hypothesis: str = Field(min_length=1)
    alternative_interpretation: str = Field(min_length=1)


class ResearchReport(Contract):
    run_id: Identifier
    question: str = Field(min_length=1, max_length=2000)
    snapshot: ReportSnapshot
    configuration_id: Digest
    execution_mode: Literal['deterministic_baseline', 'real_local_inference', 'recorded_replay']
    data_provenance: Provenance
    created_at: datetime
    status: Literal['partial', 'completed']
    findings: dict[str, Finding] = Field(min_length=1, max_length=3)
    sentiments: list[SentimentResult] = Field(max_length=300)
    model: ModelOutput
    verification: VerificationResult
    trace_reference: str
    template: Literal['evidence-report-v1']
    limitations: list[str] = Field(min_length=1)
    external_execution: StrictBool

    @field_validator('created_at')
    @classmethod
    def aware(cls, value):
        return utc(value)

    @model_validator(mode='after')
    def consistent(self):
        request, manifest = self.snapshot.request, self.snapshot.manifest
        if self.external_execution:
            raise ValueError('Reports cannot enable external execution')
        if set(self.findings) != set(request.instrument_ids):
            raise ValueError('Findings must cover exactly the requested instruments')
        if self.execution_mode != self.model.mode or self.data_provenance != request.provenance:
            raise ValueError('Report mode/provenance does not match its inputs')
        expected_tier = 'synthetic_pipeline' if request.provenance == 'synthetic' else 'historical_limited_metadata'
        if manifest.validity_tier != expected_tier:
            raise ValueError('Unsupported historical validity claim')
        if self.trace_reference != '/api/runs/' + self.run_id + '/steps':
            raise ValueError('Trace reference must point to this run')
        required_checks = {'existence', 'snapshot_membership', 'availability', 'entity', 'content_hash', 'exact_spans'}
        if (self.verification.checked_results != len(self.sentiments)
                or not required_checks <= set(self.verification.checks)):
            raise ValueError('Verification coverage does not match the report')
        seen = set()
        for sentiment in self.sentiments:
            pair = (sentiment.instrument_id, sentiment.document_id)
            if pair in seen:
                raise ValueError('Duplicate sentiment result')
            seen.add(pair)
            if (sentiment.instrument_id not in self.findings
                    or sentiment.document_id not in manifest.document_ids
                    or sentiment.cutoff != request.cutoff):
                raise ValueError('Sentiment is outside the requested evidence/entity/cutoff')
        partial = False
        for instrument, finding in self.findings.items():
            results = [result for result in self.sentiments if result.instrument_id == instrument]
            summary = aggregate(results, manifest.duplicate_groups)
            if finding.sentiment.model_dump() != summary:
                raise ValueError('Aggregate finding does not match cited sentiment results')
            expected_counterevidence = [result.document_id for result in results
                if result.label == 'negative' or result.status in {'conflicting', 'uncertain'}]
            if finding.counterevidence != expected_counterevidence:
                raise ValueError('Counterevidence is missing or unsupported')
            quant = finding.quantitative
            if quant.status == 'supported':
                if quant.observation_id not in manifest.market_ids or utc(datetime.fromisoformat(quant.available_at)) > request.cutoff:
                    raise ValueError('Quantitative evidence is outside snapshot/cutoff')
            expected_signal = research_signal(summary, quant.model_dump(), finding.research_signal.policy)
            if finding.research_signal.model_dump() != expected_signal:
                raise ValueError('Research signal does not follow its declared policy')
            partial |= summary['status'] == 'insufficient_evidence' or summary['excluded_or_uncertain'] > 0 or quant.status != 'supported'
        if self.status != ('partial' if partial else 'completed'):
            raise ValueError('Report completion status hides unavailable evidence')
        return self


class ReportOutput(Contract):
    report: ResearchReport
