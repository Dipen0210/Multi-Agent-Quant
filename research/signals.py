"""Versioned research policy; outputs are hypotheses, never broker instructions."""
from typing import Literal
from pydantic import Field
from research.contracts import Contract


class SignalPolicy(Contract):
    version: Literal['long-flat-v1']='long-flat-v1'
    horizon_sessions: int = Field(default=5,ge=1,le=20)
    min_independent_sources: int = Field(default=2,ge=2,le=20)
    positive_fraction: float = Field(default=.75,ge=.5,le=1)
    max_position_fraction: float = Field(default=.10,gt=0,le=.10)
    timing: Literal['next_regular_session_open_after_availability']='next_regular_session_open_after_availability'
    shorting: Literal[False]=False
    leverage: Literal[False]=False


def research_signal(summary, market, policy: SignalPolicy):
    common={'policy':policy.model_dump(),'hypothesis_only':True,'external_execution':False}
    if summary['status']!='supported' or summary['independent_sources']<policy.min_independent_sources:
        return common | {'signal':'NO_SIGNAL','reason':'Insufficient independent, nonconflicting sentiment evidence'}
    if market.get('status')!='supported' or market.get('last_close') is None:
        return common | {'signal':'NO_SIGNAL','reason':'Required eligible market observation unavailable'}
    fraction=summary['positive']/summary['independent_sources']
    return common | {'signal':'LONG' if fraction>=policy.positive_fraction else 'FLAT',
                     'reason':'Configured sentiment hypothesis; predictive validity unestablished'}
