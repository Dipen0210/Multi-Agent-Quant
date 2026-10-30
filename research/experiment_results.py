"""Typed historical results with accounting and source-backed replay validation."""
from datetime import date, datetime, timedelta
import json
import math
from uuid import UUID
from typing import Annotated, Literal
from pydantic import Field, field_validator, model_validator
from research.contracts import Contract, utc
from research.datasets import DatasetResponse, get_dataset
from research.experiments import ExperimentRequest
from research.reports import Digest
from research.simulation import SimulationPolicy, SimulationSignal, performance
from research.store import digest
from research.study_state import StudyState

Count=Annotated[int,Field(ge=0,strict=True)]
Money=Annotated[float,Field(ge=0,strict=True)]
Partition=Literal['train','validation','test']
Strategy=Literal['non_agent_sentiment','single_pass','verified','without_deduplication']
Variant=Literal['non_agent_sentiment','single_pass','verified','without_deduplication','cash','passive_same_exposure']
STRATEGIES={'non_agent_sentiment','single_pass','verified','without_deduplication'}
VARIANTS=STRATEGIES|{'cash','passive_same_exposure'}


def same_number(left,right):
    if not math.isclose(left,right,rel_tol=1e-10,abs_tol=1e-7): raise ValueError('Simulation accounting mismatch')


class CurvePoint(Contract):
    session: date
    cash: Money
    shares: Count
    close: float = Field(gt=0,strict=True)
    equity: float = Field(gt=0,strict=True)
    exposure: float = Field(ge=0,le=1,strict=True)
    identity_error: float = Field(ge=-1e-7,le=1e-7,strict=True)

    @model_validator(mode='after')
    def accounting(self):
        same_number(self.equity,self.cash+self.shares*self.close)
        same_number(self.exposure,self.shares*self.close/self.equity)
        same_number(self.identity_error,self.equity-(self.cash+self.shares*self.close))
        return self


class Order(Contract):
    instrument_id: str
    decision_at: datetime
    execution_at: datetime
    source_run_id: Digest | None
    action: Literal['LONG','FLAT']
    reason: str = Field(min_length=1)
    quantity: Count
    fee: Money
    notional: Money
    execution_cost: Money
    price_basis: Literal['ex-post daily bar open; never used as a decision input']
    bar_revision: int = Field(ge=1,strict=True)

    @field_validator('decision_at','execution_at')
    @classmethod
    def aware(cls,value): return utc(value)

    @model_validator(mode='after')
    def timing(self):
        if self.decision_at>=self.execution_at: raise ValueError('Order precedes decision availability')
        return self


class FilledOrder(Order):
    status: Literal['filled']
    side: Literal['buy','sell']
    quantity: int = Field(gt=0,strict=True)
    price: float = Field(gt=0,strict=True)
    cash_after: Money
    shares_after: Count

    @model_validator(mode='after')
    def notional_matches(self):
        same_number(self.notional,self.price*self.quantity)
        if self.action=='FLAT' and self.side!='sell': raise ValueError('Flat action cannot buy')
        return self


class UnfilledOrder(Order):
    status: Literal['unfilled']

    @model_validator(mode='after')
    def no_fill(self):
        if any((self.quantity,self.fee,self.notional,self.execution_cost)):
            raise ValueError('Unfilled order cannot change positions or charge costs')
        return self


class PerformanceMetrics(Contract):
    total_return: float = Field(gt=-1,strict=True)
    max_drawdown: float = Field(gt=-1,le=0,strict=True)
    annualized_volatility: Money | None
    sharpe_ratio: float | None
    turnover: Money
    average_exposure: float = Field(ge=0,le=1,strict=True)
    fees: Money
    spread_and_slippage_cost: Money
    filled_orders: Count
    unfilled_orders: Count
    observations: Count
    formulas: dict[str,str]
    uncertainty: str = Field(min_length=1)


class EndPosition(Contract):
    cash: Money
    shares: Count
    mark_to_market: float = Field(gt=0,strict=True)


class SimulationResult(Contract):
    policy: SimulationPolicy
    equity_curve: list[CurvePoint] = Field(min_length=1,max_length=400)
    orders: list[Annotated[FilledOrder|UnfilledOrder,Field(discriminator='status')]] = Field(max_length=400)
    metrics: PerformanceMetrics
    consumed_signals: list[SimulationSignal] = Field(max_length=600)
    unexecuted_signals: list[SimulationSignal] = Field(max_length=600)
    end_position: EndPosition
    assumptions: list[str] = Field(min_length=1,max_length=30)
    validity_tier: Literal['synthetic_pipeline','historical_limited_metadata']
    external_execution: Literal[False]

    @model_validator(mode='after')
    def reconcile(self):
        days=[point.session for point in self.equity_curve]
        if days!=sorted(set(days)): raise ValueError('Equity curve sessions must be unique and chronological')
        times=[order.execution_at for order in self.orders]
        if times!=sorted(set(times)) or any(at.date() not in days for at in times):
            raise ValueError('Orders must align with unique observed sessions')
        by_day={order.execution_at.date():order for order in self.orders}
        cash=self.policy.initial_cash;shares=0
        for point in self.equity_curve:
            order=by_day.get(point.session)
            if isinstance(order,FilledOrder):
                direction=1 if order.side=='buy' else -1
                same_number(order.fee,order.notional*self.policy.fee_bps/10000)
                cash-=direction*order.notional+order.fee;shares+=direction*order.quantity
                same_number(order.cash_after,cash)
                if order.shares_after!=shares: raise ValueError('Order position does not reconcile')
            same_number(point.cash,cash)
            if point.shares!=shares: raise ValueError('Curve position does not reconcile')
        last=self.equity_curve[-1]
        if self.end_position!=EndPosition(cash=last.cash,shares=last.shares,mark_to_market=last.equity):
            raise ValueError('Final position differs from equity curve')
        expected=performance([point.model_dump(mode='json') for point in self.equity_curve],self.policy.initial_cash,
                             [order.model_dump(mode='json') for order in self.orders])
        if self.metrics!=PerformanceMetrics.model_validate(expected):
            raise ValueError('Reported performance differs from reconciled ledger')
        return self


class Partitions(Contract):
    train: list[date] = Field(min_length=1,max_length=400)
    validation: list[date] = Field(min_length=1,max_length=400)
    test: list[date] = Field(min_length=1,max_length=400)
    embargo_sessions: Count
    fitting: str = Field(min_length=1)

    @model_validator(mode='after')
    def chronology(self):
        all_days=self.train+self.validation+self.test
        if all_days!=sorted(set(all_days)): raise ValueError('Partitions overlap or are not chronological')
        return self


class MarketRevision(Contract):
    session: date
    used_revision: int = Field(ge=1,strict=True)
    other_revisions: list[Annotated[int,Field(ge=1,strict=True)]] = Field(min_length=1,max_length=2000)


class ExperimentResult(Contract):
    # Absent only in legacy results; new runs always isolate execution histories.
    execution_id: UUID | None = None
    dataset: DatasetResponse
    request: ExperimentRequest
    partitions: Partitions
    comparisons: dict[Partition,dict[Variant,SimulationResult]]
    signals: dict[Strategy,list[SimulationSignal]]
    research_run_ids: list[Digest] = Field(max_length=1200)
    snapshot_ids: list[Digest] = Field(max_length=600)
    market_revisions: list[MarketRevision] = Field(max_length=600)
    workflow_disagreement_count: Count
    application_hash: Digest
    dependencies: dict[str,str | None]
    validity_tier: Literal['synthetic_pipeline','historical_limited_metadata']
    created_at: datetime
    external_execution: Literal[False]
    limitations: list[str] = Field(min_length=1,max_length=50)

    _aware=field_validator('created_at')(classmethod(lambda cls,value:utc(value)))

    @model_validator(mode='after')
    def consistency(self):
        if self.dataset.id!=self.request.dataset_id or self.validity_tier!=self.dataset.manifest.validity_tier:
            raise ValueError('Experiment dataset identity or validity tier mismatch')
        if set(self.comparisons)!={'train','validation','test'} or set(self.signals)!=STRATEGIES:
            raise ValueError('Experiment is missing a required partition or strategy')
        for partition,variants in self.comparisons.items():
            if set(variants)!=VARIANTS: raise ValueError('Missing required comparison')
            for name,result in variants.items():
                expected_policy=self.request.policy.model_copy(update={'exit_on_horizon':False}) if name=='passive_same_exposure' else self.request.policy
                if result.policy!=expected_policy or result.validity_tier!=self.validity_tier:
                    raise ValueError('Comparison policy or validity mismatch')
                if [point.session for point in result.equity_curve]!=getattr(self.partitions,partition):
                    raise ValueError('Comparison uses different partition sessions')
        reference=[signal.decision_at for signal in self.signals['single_pass']]
        if not reference or len(reference)>600 or reference!=sorted(set(reference)):
            raise ValueError('Invalid experiment decision timeline')
        for signals in self.signals.values():
            if [signal.decision_at for signal in signals]!=reference or any(signal.instrument_id!=self.dataset.request.instrument_id for signal in signals):
                raise ValueError('Strategies must use the same instrument and decision timeline')
        expected_runs=[signal.source_run_id for pair in zip(self.signals['single_pass'],self.signals['verified']) for signal in pair]
        if self.research_run_ids!=expected_runs or len(set(expected_runs))!=len(expected_runs):
            raise ValueError('Research run links differ from workflow signals')
        if self.snapshot_ids!=sorted(set(self.snapshot_ids)): raise ValueError('Snapshot references must be unique and sorted')
        disagreements=sum(a.action!=b.action for a,b in zip(self.signals['single_pass'],self.signals['verified']))
        if self.workflow_disagreement_count!=disagreements: raise ValueError('Workflow disagreement count mismatch')
        return self


class ExperimentStudy(StudyState[ExperimentRequest,ExperimentResult]):
    kind: Literal['experiment']

    @model_validator(mode='after')
    def experiment_matches(self):
        if self.result is not None and self.result.request!=self.request:
            raise ValueError('Experiment result differs from initiating request')
        if self.result is not None and self.result.execution_id is not None and self.result.execution_id!=self.id:
            raise ValueError('Experiment execution identity differs from study')
        return self


def validate_experiment_sources(store,raw,cancelled=lambda:False):
    """Replay deterministic accounting from frozen bars; never rerun model inference."""
    from research.experiments import selected_market, historical_snapshot, simulation_comparisons
    from research.simulation import chronological_partitions
    from research.report_validation import validate_report_sources
    from research.sentiment import analyze_record, aggregate
    from research.signals import research_signal
    from research.workflow import quantitative
    from research.models import Cancelled

    result=ExperimentResult.model_validate(raw)
    frozen=get_dataset(store,result.dataset.id)
    if DatasetResponse.model_validate(frozen)!=result.dataset:
        raise ValueError('Experiment dataset differs from stored frozen inputs')
    selected,revisions=selected_market(store,frozen)
    sessions=[bar.interval_start.date().isoformat() for _,bar in selected
              if frozen['request']['start']<=bar.interval_start.date().isoformat()<=frozen['request']['end']]
    partitions=chronological_partitions(sessions,result.request.train_end.isoformat(),
        result.request.validation_end.isoformat(),result.request.test_start.isoformat())
    if Partitions.model_validate(partitions)!=result.partitions or [MarketRevision.model_validate(item) for item in revisions]!=result.market_revisions:
        raise ValueError('Experiment partitions or revision disclosures differ from source data')
    eligible=[bar for _,bar in selected if bar.interval_start.date()<=result.partitions.test[-1]]
    if [bar.interval_end+timedelta(minutes=1) for bar in eligible]!=[signal.decision_at for signal in result.signals['single_pass']]:
        raise ValueError('Signal decisions do not match the frozen market timeline')
    snapshots=[];instrument=result.dataset.request.instrument_id
    for index,bar in enumerate(eligible):
        if cancelled(): raise Cancelled('Experiment validation cancelled')
        cutoff=bar.interval_end+timedelta(minutes=1)
        snapshot=historical_snapshot(store,frozen,cutoff,persist=False);snapshots.append(snapshot['id'])
        docs=snapshot['manifest']['document_ids']
        sentiments=[analyze_record(store.document(key),instrument,cutoff) for key in docs]
        quant=quantitative(store,snapshot)[instrument]
        for variant,groups in [('non_agent_sentiment',snapshot['manifest']['duplicate_groups']),('without_deduplication',[[key] for key in docs])]:
            action=research_signal(aggregate(sentiments,groups),quant,result.request.configuration.policy)['signal']
            expected=SimulationSignal(instrument_id=instrument,decision_at=cutoff,information_cutoff=cutoff,action=action,evidence_ids=docs)
            if result.signals[variant][index]!=expected: raise ValueError('Direct sentiment signal differs from eligible evidence')
        for variant in ('single_pass','verified'):
            signal=result.signals[variant][index]
            config=result.request.configuration.model_copy(update={'name':'Experiment '+variant,'workflow':variant})
            config_id=digest(config.model_dump(mode='json'))
            identity={'dataset':result.dataset.id,'snapshot':snapshot['id'],'configuration':config_id,'application':result.application_hash}
            if result.execution_id is not None: identity['execution']=str(result.execution_id)
            run_id=digest(identity)
            if signal.source_run_id!=run_id: raise ValueError('Signal links to the wrong frozen research run')
            with store.connect() as c:
                row=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
            if not row or row['status'] not in {'completed','partial'} or not row['report']:
                raise ValueError('Required historical research report is unavailable')
            run=dict(row)|{'request':json.loads(row['request'])}
            report=json.loads(row['report'])
            validate_report_sources(store,report,run)
            if (run['snapshot_id']!=snapshot['id'] or run['configuration_id']!=config_id
                    or signal.information_cutoff!=cutoff or signal.evidence_ids!=docs
                    or signal.action!=report['findings'][instrument]['research_signal']['signal']):
                raise ValueError('Workflow signal differs from linked report')
    if sorted(set(snapshots))!=result.snapshot_ids: raise ValueError('Experiment snapshot references mismatch')
    expected=simulation_comparisons(selected,raw['signals'],partitions,result.request,instrument)
    for partition,variants in expected.items():
        for variant,replayed in variants.items():
            if result.comparisons[partition][variant]!=SimulationResult.model_validate(replayed):
                raise ValueError('Simulation differs from replay using frozen sources and signals')
    return raw
