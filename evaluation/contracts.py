"""Evaluation results are checked against frozen cases, gates and recorded outputs.

This validates diagnostic accounting and provenance, not human semantic approval.
"""
from datetime import datetime
from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, PrivateAttr, StrictBool, field_validator, model_validator, model_serializer
from research.contracts import Contract, utc
from research.outputs import ModelOutput
from research.reports import Digest
from research.sentiment import SentimentResult, evidence_spans, analyze_record
from research.store import digest

Ratio = Annotated[float, Field(ge=0,le=1,strict=True)]
Count = Annotated[int, Field(ge=0,strict=True)]
Label = Literal['positive','negative','neutral']
Status = Literal['supported','uncertain','conflicting','insufficient_evidence','failed']
ROOT=Path(__file__).parent


class EvaluationRequest(Contract):
    engine: Literal['baseline','finbert']='baseline'
    split: Literal['development','heldout']='heldout'


class Review(Contract):
    status: Literal['pending','accepted','rejected']
    reviewer: str | None


class CaseResult(Contract):
    case_id: str = Field(min_length=1,max_length=160)
    expected_label: Label | None
    expected_status: Status
    result: SentimentResult
    passed: StrictBool = Field(alias='pass')
    human_review: Review

    @model_validator(mode='after')
    def outcome(self):
        if self.passed!=(self.result.label==self.expected_label and self.result.status==self.expected_status):
            raise ValueError('Case pass flag differs from expected and observed outcomes')
        return self


class ClassMetrics(Contract):
    precision: Ratio
    recall: Ratio
    f1: Ratio
    support: Count


class EvaluationMetrics(Contract):
    accuracy: Ratio
    class_balance: dict[str,Count]
    per_class: dict[str,ClassMetrics]
    confusion_matrix: dict[str,dict[str,Count]]
    macro_f1: Ratio
    case_accuracy: Ratio
    schema_pass_fraction: Ratio
    safety_pass_fraction: Ratio
    abstention_rate: Ratio
    runtime_seconds: float = Field(ge=0,strict=True)
    token_usage: Count | None
    cost: None
    calibration: Literal['not measured; probabilities uncalibrated']
    change_from_frozen_baseline: float | None = Field(ge=-1,le=1,strict=True)


class SafetyChecks(Contract):
    availability_cutoff: StrictBool
    idempotent_import: StrictBool
    valid_citation_accepted: StrictBool
    invalid_citation_rejected: StrictBool
    future_data_rejected: StrictBool
    invalid_schema_rejected: StrictBool
    external_execution_blocked: StrictBool
    lookahead_fill_rejected: StrictBool


class EvaluationModel(ModelOutput):
    # Older baseline records predate this explicit field; baseline has no calibration.
    calibrated: Literal[False] = False


def require_equal(actual,expected):
    """Compare nested metrics without permitting absent keys or changed counts."""
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or actual.keys()!=expected.keys():
            raise ValueError('Evaluation metric keys differ from recorded outcomes')
        for key,value in expected.items(): require_equal(actual[key],value)
    elif isinstance(expected,float):
        if not isinstance(actual,(int,float)) or not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-12):
            raise ValueError('Evaluation metric differs from recorded outcomes')
    elif actual!=expected:
        raise ValueError('Evaluation result differs from recorded outcomes')


class EvaluationResult(Contract):
    _raw_payload: dict | None = PrivateAttr(default=None)
    id: Digest | None = None
    dataset_version: str = Field(min_length=1)
    dataset_hash: Digest
    gate_version: str = Field(min_length=1)
    gate_hash: Digest
    split: Literal['development','heldout']
    engine: Literal['baseline','finbert']
    model: EvaluationModel
    application_hash: Digest
    dependencies: dict[str,str | None]
    metrics: EvaluationMetrics
    cases: list[CaseResult] = Field(min_length=1,max_length=100)
    safety_checks: SafetyChecks
    engineering_pass: StrictBool
    gate_failures: list[str] = Field(max_length=20)
    full_release_pass: Literal[False]
    release_blockers: list[str] = Field(min_length=1,max_length=50)
    ground_truth_status: Literal['provisional authored expectations; not human reviewed']
    created_at: datetime
    limitations: list[str] = Field(min_length=1,max_length=50)
    injected_fault: Literal['invalid-citation','lookahead-fill'] | None

    _aware=field_validator('created_at')(classmethod(lambda cls,value:utc(value)))

    @model_validator(mode='wrap')
    @classmethod
    def preserve_record(cls,value,handler):
        result=handler(value)
        if isinstance(value,dict): result._raw_payload=deepcopy(value)
        return result

    @model_serializer(mode='wrap')
    def serialize_record(self,handler):
        # Defaults/timestamp reformatting must not change a content-addressed result.
        return self._raw_payload if self._raw_payload is not None else handler(self)

    @model_validator(mode='before')
    @classmethod
    def persisted_identity(cls,value):
        if isinstance(value,dict) and value.get('id') is not None:
            if value['id']!=digest({key:item for key,item in value.items() if key!='id'}):
                raise ValueError('Evaluation identity differs from recorded result')
        return value

    @model_validator(mode='after')
    def reconcile(self):
        # Keep versioned artifacts when adding new versions. Unknown hashes fail
        # closed rather than substituting a current dataset/gate for historical ones.
        dataset=json.loads((ROOT/'datasets/sentiment-v1.json').read_text())
        gates=json.loads((ROOT/'gates.json').read_text())
        reference=json.loads((ROOT/'baseline_reference.json').read_text())
        if (self.dataset_hash!=digest(dataset) or self.dataset_version!=dataset['version']
                or self.gate_hash!=digest(gates) or self.gate_version!=gates['version']):
            raise ValueError('Unknown evaluation dataset or gate identity')
        expected_cases=[case for case in dataset['cases'] if case['split']==self.split]
        if [case.case_id for case in self.cases]!=[case['id'] for case in expected_cases]:
            raise ValueError('Evaluation must contain the exact frozen partition')
        from evaluation.suite import classification_metrics, data_document
        expected=[];predicted=[];inference_inputs=0
        for case,source in zip(self.cases,expected_cases):
            if (case.expected_label!=source['expected_label'] or case.expected_status!=source['expected_status']
                    or case.human_review.model_dump()!=source['human_review']):
                raise ValueError('Expected labels or review state differ from frozen cases')
            document=data_document(source);ident=digest(document)
            spans,_=evidence_spans({'id':ident,'data':document},source['instrument_id'])
            inference_inputs+=bool(spans)
            result=case.result
            if (result.instrument_id!=source['instrument_id'] or result.document_id!=ident
                    or result.cutoff!=datetime.fromisoformat('2025-01-03T22:00:00+00:00')
                    or result.model_version!=self.model.model_id+'@'+str(self.model.revision)
                    or result.preprocessing_version!='entity-sentence-v1'
                    or result.evidence!=spans):
                raise ValueError('Evaluation result provenance or evidence differs from case')
            probabilities=None
            if self.engine=='finbert' and spans and inference_inputs<=len(self.model.probabilities):
                probabilities=self.model.probabilities[inference_inputs-1].model_dump()
            derived_result=analyze_record({'id':ident,'data':document},source['instrument_id'],result.cutoff,
                model_version=result.model_version,probabilities=probabilities)
            derived_result.created_at=result.created_at
            if derived_result!=result:
                raise ValueError('Case output differs from recorded inference and preprocessing')
            expected.append(case.expected_label or case.expected_status)
            predicted.append(result.label or result.status)
        if self.engine=='baseline':
            if (self.model.mode!='deterministic_baseline' or self.model.model_id!='lexicon-v1'
                    or self.model.revision!='lexicon-v1' or self.model.probabilities):
                raise ValueError('Baseline evaluation has incompatible model metadata')
        elif self.model.mode!='real_local_inference' or not self.model.revision or len(self.model.probabilities)!=inference_inputs:
            raise ValueError('Real evaluation requires matching actual inference outputs')
        metrics=self.metrics.model_dump()
        for key,value in classification_metrics(expected,predicted).items(): require_equal(metrics[key],value)
        checks=self.safety_checks.model_dump()
        derived={'case_accuracy':sum(case.passed for case in self.cases)/len(self.cases),
            'schema_pass_fraction':1.,'safety_pass_fraction':sum(checks.values())/len(checks),
            'abstention_rate':sum(case.result.label is None for case in self.cases)/len(self.cases),
            'token_usage':self.model.token_usage}
        regression=reference['case_accuracy']-derived['case_accuracy'] if self.split==reference['split'] and self.dataset_hash==reference['dataset_hash'] else None
        derived['change_from_frozen_baseline']=None if regression is None else -regression
        for key,value in derived.items(): require_equal(metrics[key],value)
        failures=[key for key,value in checks.items() if not value]
        thresholds=gates['engineering']
        if self.engine=='baseline' and regression is not None and regression>thresholds['maximum_case_accuracy_regression']: failures.append('baseline_regression')
        if self.metrics.schema_pass_fraction<thresholds['required_schema_pass_fraction']: failures.append('schema_pass_fraction')
        if self.metrics.case_accuracy<thresholds['required_fixture_case_accuracy']: failures.append('fixture_case_accuracy')
        if self.engine=='baseline' and self.metrics.runtime_seconds>thresholds['maximum_baseline_runtime_seconds']: failures.append('baseline_runtime')
        if self.gate_failures!=failures or self.engineering_pass!=(not failures):
            raise ValueError('Engineering gate decision does not match frozen thresholds')
        return self


class StudyIntegrityError(ValueError):
    """Stored study/output corruption; details may contain source text."""


class EngineeringSummary(Contract):
    id: Digest
    status: Literal['passed','failed']


class ReleaseStatus(Contract):
    full_release_pass: Literal[False]
    latest_engineering_evaluation: EngineeringSummary | None
    blockers: list[str] = Field(min_length=1,max_length=50)
    approval_status: Literal['provisional engineering targets, not user-approved release requirements']


class EvaluationStudy(Contract):
    id: UUID
    kind: Literal['evaluation']
    idempotency_key: str = Field(min_length=1,max_length=160)
    request_hash: Digest
    request: EvaluationRequest
    status: Literal['queued','running','completed','failed','cancelled']
    created_at: datetime
    updated_at: datetime
    cancelled: int = Field(ge=0,le=1,strict=True)
    result: EvaluationResult | None
    error: str | None
    attempt: int = Field(ge=0,strict=True)

    @field_validator('created_at','updated_at')
    @classmethod
    def aware(cls,value): return utc(value)

    @model_validator(mode='after')
    def consistent(self):
        if self.request_hash!=digest({'kind':self.kind,'request':self.request.model_dump(mode='json')}):
            raise ValueError('Study request identity mismatch')
        if self.updated_at<self.created_at: raise ValueError('Study timestamps out of order')
        if self.status=='completed':
            if self.result is None or self.result.id is None or self.cancelled or self.error or self.attempt<1:
                raise ValueError('Completed evaluation has inconsistent status metadata')
            if (self.result.engine,self.result.split)!=(self.request.engine,self.request.split):
                raise ValueError('Evaluation result does not match its initiating request')
        elif self.result is not None:
            raise ValueError('Uncompleted evaluation cannot expose an accepted result')
        if self.status=='failed' and not self.error: raise ValueError('Failed study requires an error')
        if self.status=='running' and self.attempt<1: raise ValueError('Running study requires an attempt')
        return self
