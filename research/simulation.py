"""Transparent daily long/flat simulator. Execution prices are ex-post bar-open observations.
Strategy decisions never receive future bars. Missing inputs produce explicit unfilled orders.
"""
from __future__ import annotations
from datetime import datetime
import math
from typing import Literal
from pydantic import Field, field_validator, model_validator
from research.contracts import Contract, MarketObservation, utc


class SimulationPolicy(Contract):
    version: Literal['daily-long-flat-simulation-v1']='daily-long-flat-simulation-v1'
    initial_cash: float = Field(default=100000,gt=0,le=1e9)
    max_position_fraction: float = Field(default=.10,gt=0,le=1)
    fee_bps: float = Field(default=1,ge=0,le=100)
    spread_bps: float = Field(default=2,ge=0,le=200)
    slippage_bps: float = Field(default=5,ge=0,le=500)
    max_previous_volume_fraction: float = Field(default=.01,gt=0,le=.10)
    horizon_sessions: int = Field(default=5,ge=1,le=20)
    exit_on_horizon: bool = True
    missing_data: Literal['no_fill']='no_fill'
    dividends: Literal['excluded_price_return_only']='excluded_price_return_only'


class SimulationSignal(Contract):
    instrument_id: str
    decision_at: datetime
    information_cutoff: datetime
    action: Literal['LONG','FLAT','NO_SIGNAL']
    source_run_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list,max_length=100)

    @field_validator('decision_at','information_cutoff')
    @classmethod
    def aware(cls,value): return utc(value)

    @model_validator(mode='after')
    def timing(self):
        if self.information_cutoff>self.decision_at: raise ValueError('Information cutoff cannot follow decision time')
        return self


def performance(equity_curve, initial_cash, orders):
    values=[initial_cash]+[p['equity'] for p in equity_curve]
    returns=[values[i]/values[i-1]-1 for i in range(1,len(values))]
    mean=sum(returns)/len(returns) if returns else 0
    variance=sum((r-mean)**2 for r in returns)/(len(returns)-1) if len(returns)>1 else None
    std=math.sqrt(variance) if variance is not None else None
    peak=initial_cash;drawdown=0.
    for value in values:
        peak=max(peak,value);drawdown=min(drawdown,value/peak-1)
    filled=[o for o in orders if o['status']=='filled']
    turnover=sum(o['notional'] for o in filled)/initial_cash
    return {'total_return':values[-1]/initial_cash-1,'max_drawdown':drawdown,
        'annualized_volatility':std*math.sqrt(252) if std is not None else None,
        'sharpe_ratio':mean/std*math.sqrt(252) if std and std>1e-12 else None,
        'turnover':turnover,'average_exposure':sum(p['exposure'] for p in equity_curve)/len(equity_curve) if equity_curve else 0.,
        'fees':sum(o['fee'] for o in filled),'spread_and_slippage_cost':sum(o['execution_cost'] for o in filled),
        'filled_orders':len(filled),'unfilled_orders':len(orders)-len(filled),'observations':len(returns),
        'formulas':{'total_return':'ending_equity / initial_cash - 1','sharpe_ratio':'mean(daily_return) / sample_std(daily_return) * sqrt(252), risk-free=0',
            'annualized_volatility':'sample_std(daily_return) * sqrt(252)','turnover':'sum(abs(filled_notional)) / initial_cash',
            'max_drawdown':'minimum(equity / running_peak_equity - 1)'},
        'uncertainty':'Small samples are descriptive only. No significance or calibrated interval claimed.'}


def execution_eligible(decision_at,opening):
    return decision_at < opening


def simulate(observations, signals, policy=None, *, initial_previous=None):
    policy=policy or SimulationPolicy()
    bars=sorted([MarketObservation.model_validate(x) for x in observations],key=lambda b:b.interval_start)
    if not bars: raise ValueError('Simulation requires market observations')
    if len(bars)>400: raise ValueError('Simulation limited to 400 daily sessions')
    if len({b.instrument_id for b in bars})!=1 or len({b.interval_start for b in bars})!=len(bars):
        raise ValueError('Require one instrument and one canonical observation per session')
    if len({b.adjustment_policy for b in bars})!=1 or bars[0].adjustment_policy=='total_return':
        raise ValueError('Use consistent raw synthetic or split-adjusted price-only bars; total-return accounting unsupported')
    if any(b.provenance!='synthetic' and b.adjustment_policy!='split_adjusted' for b in bars):
        raise ValueError('Historical studies require split-adjusted bars; raw corporate-action accounting is not validated')
    if any(b.quality_flags for b in bars): raise ValueError('Flagged observations cannot produce simulated fills')
    # A daily equity curve cannot silently skip missing sessions and then annualize gaps as daily returns.
    from research.calendar import calendar
    cal=calendar()
    for left,right in zip(bars,bars[1:]):
        expected=cal.next_session(left.interval_start.date().isoformat()).date()
        if right.interval_start.date()!=expected: raise ValueError('Missing market session: import complete daily observations')
    sigs=sorted([SimulationSignal.model_validate(s) for s in signals],key=lambda s:s.decision_at)
    if any(s.instrument_id!=bars[0].instrument_id for s in sigs): raise ValueError('Signal instrument mismatch')
    if len({s.decision_at for s in sigs})!=len(sigs): raise ValueError('Ambiguous simultaneous decisions')
    previous=MarketObservation.model_validate(initial_previous) if initial_previous else None
    if previous and (previous.instrument_id!=bars[0].instrument_id or previous.interval_end>=bars[0].interval_start):
        raise ValueError('Invalid previous observation')
    cash=policy.initial_cash;shares=0;orders=[];curve=[];index=0;holding_since=None;consumed=[]
    for session,bar in enumerate(bars):
        eligible=[]
        while index<len(sigs) and execution_eligible(sigs[index].decision_at,bar.interval_start):
            eligible.append(sigs[index]);index+=1
        signal=eligible[-1] if eligible else None
        consumed.extend(s.model_dump(mode='json') for s in eligible)
        expiry=policy.exit_on_horizon and shares>0 and holding_since is not None and session-holding_since>=policy.horizon_sessions
        action='FLAT' if expiry else signal.action if signal else 'NO_SIGNAL'
        if action in {'LONG','FLAT'}:
            decision=signal.decision_at if signal else previous.available_at if previous else None
            order={'instrument_id':bar.instrument_id,'decision_at':decision.isoformat() if decision else None,
                'execution_at':bar.interval_start.isoformat(),'source_run_id':signal.source_run_id if signal else None,
                'action':action,'status':'unfilled','reason':None,'quantity':0,'fee':0.,'notional':0.,'execution_cost':0.,
                'price_basis':'ex-post daily bar open; never used as a decision input','bar_revision':bar.revision}
            if decision is None or not execution_eligible(decision,bar.interval_start):
                raise ValueError('Look-ahead: fill cannot precede or coincide with decision availability')
            if not previous or previous.available_at>=bar.interval_start:
                order['reason']='Required previous-session liquidity observation unavailable'
            elif cal.next_session(previous.interval_start.date().isoformat()).date()!=bar.interval_start.date():
                order['reason']='Required previous-session observation stale'
            else:
                equity=cash+shares*bar.open
                friction=(policy.slippage_bps+policy.spread_bps/2)/10000
                buy_price=bar.open*(1+friction)
                target=math.floor(equity*policy.max_position_fraction/(buy_price*(1+policy.fee_bps/10000))) if action=='LONG' else 0
                change=target-shares
                liquidity=math.floor(previous.volume*policy.max_previous_volume_fraction)
                quantity=min(abs(change),liquidity)
                if change>0:
                    quantity=min(quantity,math.floor(cash/(buy_price*(1+policy.fee_bps/10000))))
                if quantity<=0:
                    order['reason']='No affordable/liquid adjustment required'
                else:
                    direction=1 if change>0 else -1
                    price=bar.open*(1+direction*friction);notional=quantity*price;fee=notional*policy.fee_bps/10000
                    cash-=direction*notional+fee;shares+=direction*quantity
                    if cash < -1e-7 or shares<0: raise ValueError('Cash or position accounting violated')
                    if direction>0:
                        if holding_since is None: holding_since=session
                        if shares*price>equity*policy.max_position_fraction+1e-7:
                            raise ValueError('Concentration limit violated at purchase')
                    if shares==0: holding_since=None
                    order.update(status='filled',reason='horizon exit' if expiry else 'policy signal',side='buy' if direction>0 else 'sell',
                        quantity=quantity,price=price,fee=fee,notional=notional,execution_cost=quantity*abs(price-bar.open),
                        cash_after=cash,shares_after=shares)
            orders.append(order)
        equity=cash+shares*bar.close
        if not math.isfinite(equity) or equity<=0: raise ValueError('Invalid portfolio equity')
        curve.append({'session':bar.interval_start.date().isoformat(),'cash':cash,'shares':shares,'close':bar.close,'equity':equity,
                      'exposure':shares*bar.close/equity,'identity_error':equity-(cash+shares*bar.close)})
        previous=bar
    unexecuted=[s.model_dump(mode='json') for s in sigs[index:]]
    return {'policy':policy.model_dump(),'equity_curve':curve,'orders':orders,'metrics':performance(curve,policy.initial_cash,orders),
        'consumed_signals':consumed,'unexecuted_signals':unexecuted,'end_position':{'cash':cash,'shares':shares,'mark_to_market':curve[-1]['equity']},
        'assumptions':['Long/flat; no borrowing, shorts, or external orders.','Fills use the next eligible regular-session open strictly after decision time.',
            'Spread/slippage and fees are charged on every fill. Liquidity limit uses the previous available session volume.',
            'Prices are an ex-post execution oracle. Imported bar availability is not proof of an executable historical quote.',
            'Open positions are marked to the last close, not fictitiously liquidated.','Dividends excluded; split-adjusted historical bars express constant adjusted units.',
            'Position cap applies when purchasing; market drift can change subsequent exposure.'],
        'validity_tier':'synthetic_pipeline' if all(b.provenance=='synthetic' for b in bars) else 'historical_limited_metadata',
        'external_execution':False}


def chronological_partitions(sessions, train_end, validation_end, test_start, embargo_sessions=0):
    """Explicit chronological splits. Purge/embargo are needed only when fitting overlapping labels."""
    if not train_end<validation_end<test_start: raise ValueError('Partitions must be chronological and disjoint')
    train=[s for s in sessions if s<=train_end]
    validation=[s for s in sessions if train_end<s<=validation_end]
    test=[s for s in sessions if s>=test_start]
    if embargo_sessions:
        train=train[:-embargo_sessions] if len(train)>embargo_sessions else []
        validation=validation[embargo_sessions:-embargo_sessions] if len(validation)>2*embargo_sessions else []
        test=test[embargo_sessions:]
    if not train or not validation or not test: raise ValueError('Insufficient observations after chronological partition/purge')
    return {'train':train,'validation':validation,'test':test,'embargo_sessions':embargo_sessions,
            'fitting':'No learned preprocessing, calibration or threshold optimization in fixed-policy mode; any future fitting must use train only.'}
