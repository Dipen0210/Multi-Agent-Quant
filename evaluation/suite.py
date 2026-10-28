"""Reproducible diagnostics and deterministic release checks. No LLM-generated ground truth."""
from contextlib import nullcontext
from datetime import datetime
import json
import math
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from research.contracts import Document, SnapshotRequest
from research.models import local_finbert
from research.sentiment import analyze_record, evidence_spans, SentimentResult
from research.store import Store, canonical, digest, now
from research.versioning import code_version, dependency_versions
from research.workflow import verify_evidence

ROOT=Path(__file__).parent


def data_document(case):
    return Document(provider='evaluation-fixtures',original_id=case['id'],revision=1,title=case['id'],
        content=case['text'],language=case['language'],instrument_ids=['US:AAPL','US:MSFT'],
        published_at='2025-01-03T15:00:00Z',first_observed_at='2025-01-03T15:01:00Z',
        provenance='synthetic',usage_restrictions='Authored synthetic software evaluation case; not market evidence').model_dump(mode='json')


def classification_metrics(expected,predicted):
    labels=sorted(set(expected)|set(predicted)); matrix={label:{other:0 for other in labels} for label in labels}
    for actual,pred in zip(expected,predicted): matrix[actual][pred]+=1
    classes={}
    for label in labels:
        tp=matrix[label][label];fp=sum(matrix[x][label] for x in labels if x!=label);fn=sum(matrix[label][x] for x in labels if x!=label)
        precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.
        classes[label]={'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.,'support':sum(matrix[label].values())}
    return {'accuracy':sum(x==y for x,y in zip(expected,predicted))/len(expected) if expected else None,
        'class_balance':{k:v['support'] for k,v in classes.items()},'per_class':classes,'confusion_matrix':matrix,
        'macro_f1':sum(v['f1'] for v in classes.values())/len(classes) if classes else None}


def safety_checks(inject_fault=None):
    checks={}
    with tempfile.TemporaryDirectory() as directory:
        store=Store(Path(directory)/'safety.sqlite3')
        example={'id':'safety','text':'Apple reported higher earnings.','language':'en'}
        valid=data_document(example)
        receipt=store.import_records([valid,valid|{'original_id':'future','first_observed_at':'2025-01-04T00:00:00Z'},
            valid|{'revision':2,'first_observed_at':'2025-01-04T01:00:00Z','content':'Apple reported lower earnings.'}])
        snap=store.snapshot(SnapshotRequest(instrument_ids=['US:AAPL'],cutoff='2025-01-03T22:00:00Z'))
        checks['availability_cutoff']=snap['manifest']['document_ids']==[receipt['document_ids'][0]]
        checks['idempotent_import']=store.import_records([valid])['duplicates']==1
        record=store.document(receipt['document_ids'][0])
        result=analyze_record(record,'US:AAPL',snap['request']['cutoff']).model_dump(mode='json')
        checks['valid_citation_accepted']=verify_evidence(store,snap,[result])['status']=='passed'
        invalid=result|{'document_id':'invented'}
        context=patch('evaluation.suite.verify_evidence',return_value={'status':'passed'}) if inject_fault=='invalid-citation' else nullcontext()
        with context:
            try: verify_evidence(store,snap,[invalid]);checks['invalid_citation_rejected']=False
            except ValueError: checks['invalid_citation_rejected']=True
        contaminated=json.loads(json.dumps(snap));contaminated['manifest']['document_ids'].append(receipt['document_ids'][1])
        future=analyze_record(store.document(receipt['document_ids'][1]),'US:AAPL',snap['request']['cutoff']).model_dump(mode='json')
        try: verify_evidence(store,contaminated,[future]);checks['future_data_rejected']=False
        except ValueError: checks['future_data_rejected']=True
        try: SentimentResult.model_validate({'label':'positive'});checks['invalid_schema_rejected']=False
        except ValueError: checks['invalid_schema_rejected']=True
        from agent.tools.alpaca_tool import place_order
        with patch('agent.tools.alpaca_tool._get_client') as broker:
            try: place_order('AAPL','buy',1,95);checks['external_execution_blocked']=False
            except RuntimeError: checks['external_execution_blocked']=not broker.called
    from research.simulation import simulate
    from research.calendar import session_times
    from datetime import timedelta
    bars=[]
    for day in ('2025-01-02','2025-01-03','2025-01-06'):
        start,end=session_times(day)
        bars.append({'instrument_id':'US:AAPL','provider':'synthetic-evaluation','original_id':day,'revision':1,
            'interval_start':start.isoformat(),'interval_end':end.isoformat(),'available_at':(end+timedelta(minutes=1)).isoformat(),
            'open':100,'high':102,'low':99,'close':101,'volume':100000,'adjustment_policy':'raw',
            'provenance':'synthetic','usage_restrictions':'Synthetic release-check fixture'})
    at=bars[1]['interval_start']
    signal={'instrument_id':'US:AAPL','decision_at':at,'information_cutoff':at,'action':'LONG'}
    context=patch('research.simulation.execution_eligible',side_effect=lambda decision,opening: decision<=opening) if inject_fault=='lookahead-fill' else nullcontext()
    with context:
        simulated=simulate(bars[1:],[signal],initial_previous=bars[0])
    fills=[order for order in simulated['orders'] if order['status']=='filled']
    checks['lookahead_fill_rejected']=bool(fills) and all(datetime.fromisoformat(o['decision_at'])<datetime.fromisoformat(o['execution_at']) for o in fills)
    return checks


def run_suite(engine='baseline',split='heldout',inject_fault=None,cancelled=lambda:False):
    if engine not in {'baseline','finbert'} or split not in {'development','heldout'}: raise ValueError('Unknown evaluation configuration')
    dataset=json.loads((ROOT/'datasets/sentiment-v1.json').read_text())
    gates=json.loads((ROOT/'gates.json').read_text());started=time.monotonic()
    cases=[c for c in dataset['cases'] if c['split']==split]
    records=[{'id':digest(data_document(c)),'data':data_document(c)} for c in cases]
    model={'model_id':'lexicon-v1','revision':'lexicon-v1','mode':'deterministic_baseline'}
    probabilities={}
    if engine=='finbert':
        texts=[];indices=[]
        for index,(case,record) in enumerate(zip(cases,records)):
            spans,_=evidence_spans(record,case['instrument_id'])
            if spans: texts.append(' '.join(s.quote for s in spans));indices.append(index)
        model=local_finbert(texts,cancelled);model['mode']='real_local_inference'
        probabilities=dict(zip(indices,model['probabilities']))
    outputs=[];expected=[];predicted=[];schema_pass=0
    for index,(case,record) in enumerate(zip(cases,records)):
        result=analyze_record(record,case['instrument_id'],'2025-01-03T22:00:00Z',
            model_version=model['model_id']+'@'+str(model['revision']),probabilities=probabilities.get(index))
        SentimentResult.model_validate(result.model_dump());schema_pass+=1
        expected.append(case['expected_label'] or case['expected_status'])
        predicted.append(result.label or result.status)
        outputs.append({'case_id':case['id'],'expected_label':case['expected_label'],'expected_status':case['expected_status'],
            'result':result.model_dump(mode='json'),'pass':result.label==case['expected_label'] and result.status==case['expected_status'],
            'human_review':case['human_review']})
    checks=safety_checks(inject_fault)
    elapsed=time.monotonic()-started
    metrics=classification_metrics(expected,predicted)
    metrics.update({'case_accuracy':sum(r['pass'] for r in outputs)/len(outputs),'schema_pass_fraction':schema_pass/len(cases),
        'safety_pass_fraction':sum(checks.values())/len(checks),'abstention_rate':sum(r['result']['label'] is None for r in outputs)/len(outputs),
        'runtime_seconds':elapsed,'token_usage':model.get('token_usage'),'cost':None,'calibration':'not measured; probabilities uncalibrated'})
    thresholds=gates['engineering']
    reference=json.loads((ROOT/'baseline_reference.json').read_text())
    regression=reference['case_accuracy']-metrics['case_accuracy'] if split==reference['split'] and digest(dataset)==reference['dataset_hash'] else None
    metrics['change_from_frozen_baseline']=None if regression is None else -regression
    failures=[key for key,passed in checks.items() if not passed]
    if engine=='baseline' and regression is not None and regression>thresholds['maximum_case_accuracy_regression']:
        failures.append('baseline_regression')
    if metrics['schema_pass_fraction']<thresholds['required_schema_pass_fraction']: failures.append('schema_pass_fraction')
    if metrics['case_accuracy']<thresholds['required_fixture_case_accuracy']: failures.append('fixture_case_accuracy')
    if engine=='baseline' and elapsed>thresholds['maximum_baseline_runtime_seconds']: failures.append('baseline_runtime')
    report={'dataset_version':dataset['version'],'dataset_hash':digest(dataset),'gate_version':gates['version'],'gate_hash':digest(gates),
        'split':split,'engine':engine,'model':model,'application_hash':code_version(),'dependencies':dependency_versions(),
        'metrics':metrics,'cases':outputs,'safety_checks':checks,'engineering_pass':not failures,'gate_failures':failures,
        'full_release_pass':False,'release_blockers':['Human-reviewed semantic cases pending','Historical acceptance pending','Frontend visual acceptance pending','Mandatory requirement audit incomplete'],
        'ground_truth_status':'provisional authored expectations; not human reviewed','created_at':now(),
        'limitations':['Synthetic diagnostic corpus is small and not representative of financial news.','No training/tuning performed on heldout cases.','Results do not establish multi-agent superiority or profitable trading.','Runtime varies by machine; model outputs may vary across library/hardware revisions.'],
        'injected_fault':inject_fault}
    return report


def persist(store,report):
    ident=digest(report)
    with store.connect() as c:
        c.execute('INSERT OR IGNORE INTO evaluation_runs VALUES (?,?,?,?,?,?)',(ident,report['created_at'],report['dataset_hash'],
            canonical({'engine':report['engine'],'split':report['split'],'application_hash':report['application_hash']}),
            'passed' if report['engineering_pass'] else 'failed',canonical(report)))
    return {'id':ident,**report}
