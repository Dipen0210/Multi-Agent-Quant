from typing import Literal
from pydantic import Field
from research.contracts import Contract
from research.signals import SignalPolicy
from research.store import canonical, digest, now


class Configuration(Contract):
    version: Literal['research-v1']='research-v1'
    name: str = Field(default='Conservative research baseline',min_length=1,max_length=100)
    sentiment_engine: Literal['baseline','finbert','recorded']='baseline'
    recording_id: str | None = Field(default=None,max_length=64)
    workflow: Literal['verified','single_pass']='single_pass'
    max_documents: int = Field(default=50,ge=1,le=100)
    run_timeout_seconds: int = Field(default=120,ge=1,le=180)
    step_timeout_seconds: int = Field(default=60,ge=1,le=90)
    inference_retries: int = Field(default=1,ge=0,le=2)
    policy: SignalPolicy = Field(default_factory=SignalPolicy)
    report_template: Literal['evidence-report-v1']='evidence-report-v1'
    retrieval: Literal['direct-eligible-evidence-v1']='direct-eligible-evidence-v1'


def register(store, config: Configuration):
    data=config.model_dump(mode='json'); ident=digest(data)
    with store.connect() as c:
        c.execute('INSERT OR IGNORE INTO configurations VALUES (?,?,?)',(ident,now(),canonical(data)))
        c.execute('INSERT OR IGNORE INTO active_configuration VALUES (1,?)',(ident,))
    return {'id':ident,'data':data}


def activate(store, ident):
    with store.connect() as c:
        if not c.execute('SELECT 1 FROM configurations WHERE id=?',(ident,)).fetchone(): raise KeyError('Configuration not found')
        c.execute('UPDATE active_configuration SET configuration_id=? WHERE singleton=1',(ident,))
        c.execute('INSERT INTO audit_events(created_at,kind,data) VALUES (?,?,?)',(now(),'configuration_activated',canonical({'configuration_id':ident})))
    return {'active_configuration_id':ident}
