"""Validated intermediate contracts, separate from persistence/UI serialization."""
from typing import Literal
from pydantic import Field, model_validator
from research.contracts import Contract
from research.sentiment import SentimentResult


class Probability(Contract):
    positive: float = Field(ge=0,le=1,strict=True)
    negative: float = Field(ge=0,le=1,strict=True)
    neutral: float = Field(ge=0,le=1,strict=True)

    @model_validator(mode='after')
    def normalized(self):
        if abs(self.positive+self.negative+self.neutral-1)>1e-4:
            raise ValueError('Class probabilities must sum to one')
        return self


class ModelOutput(Contract):
    model_id: str = Field(min_length=1,max_length=200)
    revision: str | None
    calibrated: Literal[False]
    token_usage: int | None = Field(default=None,ge=0)
    cost: float | None = Field(default=None,ge=0)
    mode: Literal['deterministic_baseline','real_local_inference','recorded_replay']
    probabilities: list[Probability] = Field(default_factory=list,max_length=100)
    parameters: dict = Field(default_factory=dict)
    status: Literal['completed'] = 'completed'
    cost_note: str | None = None
    preprocessing: str | None = None
    retry_failures: list[str] = Field(default_factory=list,max_length=2)
    recording_id: str | None = None


class EvidenceOutput(Contract):
    document_ids: list[str] = Field(max_length=100)


class SentimentOutput(Contract):
    sentiments: list[SentimentResult] = Field(max_length=300)
    model: ModelOutput


class QuantitativeResult(Contract):
    status: Literal['supported','insufficient_evidence']
    tool: Literal['eligible-close-summary-v1']
    last_close: float | None = Field(default=None,gt=0)
    reason: str | None = None
    available_at: str | None = None
    observation_id: str | None = None
    observations: int | None = Field(default=None,ge=1)
    currency: Literal['USD'] | None = None
    previous_observation_return: float | None = None
    return_interval: str | None = None
    adjustment_policy: Literal['raw','split_adjusted','total_return'] | None = None

    @model_validator(mode='after')
    def supported_has_evidence(self):
        if self.status=='supported' and any(getattr(self,key) is None for key in ('last_close','available_at','observation_id','observations','currency','adjustment_policy')):
            raise ValueError('Supported quantitative result requires market evidence')
        if self.status=='insufficient_evidence':
            if not self.reason or any(getattr(self,key) is not None for key in ('last_close','available_at','observation_id','previous_observation_return','observations')):
                raise ValueError('Unavailable market evidence cannot claim numerical findings')
        return self


class QuantitativeOutput(Contract):
    quantitative: dict[str,QuantitativeResult]


class VerificationResult(Contract):
    status: Literal['passed']
    checked_results: int = Field(ge=0)
    checks: list[str]
    semantic_support: str


class VerificationOutput(Contract):
    verification: VerificationResult


def validate_output(role,output):
    contracts={'evidence':EvidenceOutput,'sentiment':SentimentOutput,'quantitative':QuantitativeOutput,'verification':VerificationOutput,'model':ModelOutput}
    if role in contracts:
        return contracts[role].model_validate(output).model_dump(mode='json')
    if role in {'report','research'}:
        from research.reports import ReportOutput
        ReportOutput.model_validate(output)
        # Preserve exact frozen snapshot serialization and its content identity.
        return output
    raise ValueError('Unknown workflow role')
