"""Frozen historical research with time-aware evidence and explicitly limited validity."""
from datetime import date, datetime, timedelta, timezone
import json
from typing import Literal
from pydantic import Field, model_validator
from research.calendar import calendar
from research.configuration import Configuration, register
from research.contracts import Contract, Document, MarketObservation, UNIVERSE
from research.models import Cancelled
from research.sentiment import analyze_record, aggregate
from research.signals import research_signal
from research.simulation import SimulationPolicy, SimulationSignal, simulate, chronological_partitions
from research.store import canonical, digest, normalized, now
from research.versioning import code_version, dependency_versions
from research.workflow import verify_evidence, quantitative


class DatasetRequest(Contract):
    instrument_id: str
    start: date
    end: date
    provenance: Literal['synthetic','historical_approximate','recorded','live']='synthetic'
    document_lookback_days: int = Field(default=30,ge=1,le=365)

    @model_validator(mode='after')
    def bounds(self):
        if self.instrument_id not in UNIVERSE: raise ValueError('Unsupported instrument')
        if not self.start<self.end or (self.end-self.start).days>550: raise ValueError('Dataset must cover 2–550 calendar days')
        return self


class ExperimentRequest(Contract):
    dataset_id: str = Field(min_length=64,max_length=64,pattern=r'^[a-f0-9]+$')
    train_end: date
    validation_end: date
    test_start: date
    policy: SimulationPolicy = Field(default_factory=SimulationPolicy)
    configuration: Configuration = Field(default_factory=Configuration)
    parameter_search_history: list[str] = Field(default_factory=lambda:['One frozen policy; no parameter search'],max_length=50)

    @model_validator(mode='after')
    def controls(self):
        if not self.train_end<self.validation_end<self.test_start: raise ValueError('Partitions must be chronological')
        if self.policy.max_position_fraction>.1: raise ValueError('Research strategy concentration is capped at 10%')
        if self.configuration.sentiment_engine=='recorded':
            raise ValueError('Historical replay requires per-cutoff recordings; use baseline or actual local FinBERT')
        if self.configuration.policy.horizon_sessions!=self.policy.horizon_sessions:
            raise ValueError('Signal and simulation horizons must agree')
        return self


def freeze_dataset(store,request: DatasetRequest):
    end=datetime.combine(request.end,datetime.max.time(),tzinfo=timezone.utc)
    begin=datetime.combine(request.start-timedelta(days=request.document_lookback_days),datetime.min.time(),tzinfo=timezone.utc)
    with store.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        docs=[];bars=[]
        for row in c.execute('SELECT id,data FROM documents WHERE available_at BETWEEN ? AND ?',(begin.isoformat(),end.isoformat())):
            doc=Document.model_validate_json(row['data'])
            if request.instrument_id in doc.instrument_ids and doc.provenance==request.provenance: docs.append(row['id'])
        for row in c.execute('SELECT id,data FROM market WHERE instrument_id=?',(request.instrument_id,)):
            bar=MarketObservation.model_validate_json(row['data'])
            if request.start-timedelta(days=10)<=bar.interval_start.date()<=request.end and bar.provenance==request.provenance:
                bars.append(row['id'])
        if len(docs)>2000 or len(bars)>2000: raise ValueError('Dataset record budget exceeded')
        if not bars: raise ValueError('No market records in requested dataset')
        manifest={'document_ids':sorted(docs),'market_ids':sorted(bars),'revision_policy':'all_versions_preserved',
            'universe':'Fixed current AAPL/MSFT/SPY universe; excludes delisted names; survivorship and universe-selection bias apply.',
            'validity_tier':'synthetic_pipeline' if request.provenance=='synthetic' else 'historical_limited_metadata'}
        payload=request.model_dump(mode='json');ident=digest({'request':payload,'manifest':manifest})
        c.execute('INSERT OR IGNORE INTO datasets VALUES (?,?,?,?)',(ident,now(),canonical(payload),canonical(manifest)))
        for key in docs: c.execute('INSERT OR IGNORE INTO dataset_documents VALUES (?,?)',(ident,key))
        for key in bars: c.execute('INSERT OR IGNORE INTO dataset_market VALUES (?,?)',(ident,key))
    return {'id':ident,'request':payload,'manifest':manifest}


def get_dataset(store,ident):
    with store.connect() as c: row=c.execute('SELECT * FROM datasets WHERE id=?',(ident,)).fetchone()
    if not row: raise KeyError('Dataset not found')
    return {'id':row['id'],'request':json.loads(row['request']),'manifest':json.loads(row['manifest'])}


def historical_snapshot(store,dataset,cutoff):
    instrument=dataset['request']['instrument_id']
    lower=cutoff-timedelta(days=dataset['request']['document_lookback_days'])
    latest={};bars={}
    for ident in dataset['manifest']['document_ids']:
        row=store.document(ident);doc=Document.model_validate(row['data'])
        if doc.available_at>cutoff: continue
        key=(doc.provider,doc.original_id)
        if key not in latest or latest[key][1].revision<doc.revision: latest[key]=(ident,doc)
    docs=sorted(ident for ident,doc in latest.values() if doc.available_at>=lower and doc.entity_status=='resolved')
    with store.connect() as c:
        for ident in dataset['manifest']['market_ids']:
            row=c.execute('SELECT data FROM market WHERE id=?',(ident,)).fetchone()
            bar=MarketObservation.model_validate_json(row['data'])
            if bar.available_at>cutoff or bar.interval_end<cutoff-timedelta(days=7) or bar.quality_flags: continue
            key=(bar.provider,bar.original_id)
            if key not in bars or bars[key][1].revision<bar.revision: bars[key]=(ident,bar)
    groups={}
    for ident in docs:
        text=normalized(store.document(ident)['data']['content'])
        groups.setdefault(text,[]).append(ident)
    request={'instrument_ids':[instrument],'cutoff':cutoff.isoformat(),'window_days':dataset['request']['document_lookback_days'],
        'market_max_age_days':7,'provenance':dataset['request']['provenance']}
    manifest={'document_ids':docs,'market_ids':sorted(ident for ident,_ in bars.values()),'duplicate_groups':list(groups.values()),
        'availability_policy':'first-observed-or-explicit-latency-v1','deduplication_policy':'normalized-exact-historical-v1',
        'validity_tier':dataset['manifest']['validity_tier'],'limitations':['Frozen historical subset; supplied availability metadata is not certified.']}
    ident=digest({'request':request,'manifest':manifest})
    with store.connect() as c:
        c.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?)',(ident,now(),canonical(request),canonical(manifest)))
        for key in docs: c.execute('INSERT OR IGNORE INTO snapshot_documents VALUES (?,?)',(ident,key))
        for key in manifest['market_ids']: c.execute('INSERT OR IGNORE INTO snapshot_market VALUES (?,?)',(ident,key))
    return {'id':ident,'request':request,'manifest':manifest}


def run_experiment(store,request: ExperimentRequest,cancelled=lambda:False):
    dataset=get_dataset(store,request.dataset_id);instrument=dataset['request']['instrument_id']
    observations=[]
    with store.connect() as c:
        for ident in dataset['manifest']['market_ids']:
            row=c.execute('SELECT data FROM market WHERE id=?',(ident,)).fetchone()
            observations.append((ident,MarketObservation.model_validate_json(row['data'])))
    # Execution oracle: earliest recorded revision per regular session. Later corrections are disclosed, never spliced silently.
    grouped={}
    for ident,bar in observations: grouped.setdefault(bar.interval_start,[]).append((ident,bar))
    selected=[];revised=[]
    for _,items in sorted(grouped.items()):
        if len({b.provider for _,b in items})>1: raise ValueError('Competing market providers require explicit resolution')
        items.sort(key=lambda item:(item[1].available_at,item[1].revision))
        selected.append(items[0])
        if len(items)>1: revised.append({'session':items[0][1].interval_start.date().isoformat(),'used_revision':items[0][1].revision,'other_revisions':[b.revision for _,b in items[1:]]})
    sessions=[b.interval_start.date().isoformat() for _,b in selected if dataset['request']['start']<=b.interval_start.date().isoformat()<=dataset['request']['end']]
    split=chronological_partitions(sessions,request.train_end.isoformat(),request.validation_end.isoformat(),request.test_start.isoformat())
    signals={'non_agent_sentiment':[],'single_pass':[],'verified':[],'without_deduplication':[]}
    research_runs=[];snapshots=[];disagreements=0
    from research.workflow import Workflow
    import uuid
    configs={variant:register(store,request.configuration.model_copy(update={'name':'Experiment '+variant,'workflow':variant})) for variant in ('single_pass','verified')}
    for ident,bar in selected:
        if cancelled(): raise Cancelled('Experiment cancelled')
        if bar.interval_start.date().isoformat()>split['test'][-1]: continue
        # Fixed close + 1 minute decision; later market/text arrivals remain ineligible until a later decision.
        cutoff=bar.interval_end+timedelta(minutes=1)
        snap=historical_snapshot(store,dataset,cutoff);snapshots.append(snap['id'])
        results=[analyze_record(store.document(key),instrument,cutoff).model_dump(mode='json') for key in snap['manifest']['document_ids']]
        from research.sentiment import SentimentResult
        quant=quantitative(store,snap)[instrument]
        for variant,groups in [('non_agent_sentiment',snap['manifest']['duplicate_groups']),('without_deduplication',[[key] for key in snap['manifest']['document_ids']])]:
            summary=aggregate([SentimentResult.model_validate(x) for x in results],groups)
            signal=research_signal(summary,quant,request.configuration.policy)
            signals[variant].append(SimulationSignal(instrument_id=instrument,decision_at=cutoff,information_cutoff=cutoff,
                action=signal['signal'],evidence_ids=snap['manifest']['document_ids']).model_dump(mode='json'))
        outputs=[]
        for variant,config in configs.items():
            if cancelled(): raise Cancelled('Experiment cancelled')
            run_id=digest({'dataset':dataset['id'],'snapshot':snap['id'],'configuration':config['id'],'application':code_version()});payload={'snapshot_id':snap['id'],'question':'Frozen historical sentiment policy','configuration_id':config['id']}
            with store.connect() as c:
                c.execute('INSERT INTO runs(id,idempotency_key,request_hash,snapshot_id,configuration_id,status,created_at,updated_at,attempt,request) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,cancelled=0,attempt=runs.attempt+1,updated_at=excluded.updated_at,error=NULL,report=NULL',
                    (run_id,run_id,digest(payload),snap['id'],config['id'],'running',now(),now(),1,canonical(payload)))
                attempt=c.execute('SELECT attempt FROM runs WHERE id=?',(run_id,)).fetchone()[0]
            workflow=Workflow(store,{'id':run_id,'snapshot_id':snap['id'],'configuration_id':config['id'],'attempt':attempt,'request':payload},Configuration.model_validate(config['data']))
            workflow.cancelled=cancelled
            try:
                report=workflow.execute()
            except Exception as exc:
                with store.connect() as c: c.execute('UPDATE runs SET status=?,error=?,updated_at=? WHERE id=?',('cancelled' if isinstance(exc,Cancelled) else 'failed',type(exc).__name__,now(),run_id))
                raise
            with store.connect() as c: c.execute('UPDATE runs SET status=?,report=?,updated_at=? WHERE id=?',(report['status'],canonical(report),now(),run_id))
            action=report['findings'][instrument]['research_signal']['signal'];outputs.append(action);research_runs.append(run_id)
            signals[variant].append(SimulationSignal(instrument_id=instrument,decision_at=cutoff,information_cutoff=cutoff,action=action,
                source_run_id=run_id,evidence_ids=snap['manifest']['document_ids']).model_dump(mode='json'))
        disagreements+=outputs[0]!=outputs[1]
    comparisons={}
    for partition in ('train','validation','test'):
        days=split[partition];bars=[b for _,b in selected if b.interval_start.date().isoformat() in days]
        prior=[b for _,b in selected if b.interval_end<bars[0].interval_start];previous=prior[-1] if prior else None
        cutoff_floor=previous.interval_end if previous else bars[0].interval_start
        variants={}
        for name,values in signals.items():
            used=[s for s in values if cutoff_floor<=datetime.fromisoformat(s['decision_at'])<=bars[-1].interval_end+timedelta(minutes=1)]
            variants[name]=simulate([b.model_dump(mode='json') for b in bars],used,request.policy,initial_previous=previous.model_dump(mode='json') if previous else None)
        variants['cash']=simulate([b.model_dump(mode='json') for b in bars],[],request.policy,initial_previous=previous.model_dump(mode='json') if previous else None)
        passive_signal=SimulationSignal(instrument_id=instrument,decision_at=bars[0].interval_start-timedelta(seconds=1),information_cutoff=bars[0].interval_start-timedelta(seconds=1),action='LONG')
        # Buy once and retain the adjusted units; no horizon exits in the passive comparator.
        passive_policy=request.policy.model_copy(update={'exit_on_horizon':False})
        variants['passive_same_exposure']=simulate([b.model_dump(mode='json') for b in bars],[passive_signal],passive_policy,
            initial_previous=previous.model_dump(mode='json') if previous else None)
        comparisons[partition]=variants
    return {'dataset':dataset,'request':request.model_dump(mode='json'),'partitions':split,'comparisons':comparisons,
        'signals':signals,'research_run_ids':research_runs,'snapshot_ids':sorted(set(snapshots)),'market_revisions':revised,
        'workflow_disagreement_count':disagreements,'application_hash':code_version(),'dependencies':dependency_versions(),
        'validity_tier':dataset['manifest']['validity_tier'],'created_at':now(),'external_execution':False,
        'limitations':[dataset['manifest']['universe'],'Synthetic fixtures establish accounting behavior only, not historical profitability.',
            'No learned model, threshold fitting or parameter search; fixed policies are compared without optimizing on the test partition.',
            'Single-pass and verified variants share deterministic evidence/sentiment logic; this is an orchestration ablation, not an independent generative-agent benchmark.',
            'Pretrained-model historical outcome contamination is unresolved. Timestamp filtering does not establish leakage-free historical inference.',
            'No predictive confidence interval: sample size and observed paths are reported, without statistical significance claims.',
            'Dividends excluded; historical imported metadata has limited availability validity. Prospective frozen-policy validation is the stronger follow-up.']}
