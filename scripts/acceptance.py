"""Actual API acceptance walkthrough in an isolated temporary local database.
Run from project root: venv/bin/python -m scripts.acceptance [--real-model]
"""
import argparse
import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from evaluation.suite import run_suite
from research.models import Cancelled
from research.versioning import code_version,dependency_versions


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real-model',action='store_true');parser.add_argument('--output',default='runtime/acceptance.json');args=parser.parse_args()
    checks={};details={}
    with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ',{'RESEARCH_DB':str(Path(directory)/'acceptance.sqlite3')}), TestClient(app) as client:
        def post(path,data={}):
            response=client.post(path,json=data);response.raise_for_status();return response.json()
        def wait(path,timeout=180):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                response=client.get(path);response.raise_for_status();value=response.json()
                if value['status'] not in {'running','queued'}: return value
                time.sleep(.05)
            raise TimeoutError('Acceptance computation did not terminate')
        first=post('/api/demo/import');again=post('/api/demo/import')
        checks['idempotent_fixture_import']=first['inserted']>0 and again['inserted']==0 and not again['rejected']
        snapshot=post('/api/snapshots',{'instrument_ids':['US:AAPL'],'cutoff':'2025-01-03T22:00:00Z'})
        docs={key:client.get('/api/evidence/'+key).json()['data'] for key in snapshot['manifest']['document_ids']}
        checks['future_and_revision_cutoff']=all(d['original_id']!='late' and d['revision']==1 for d in docs.values())
        run=post('/api/runs',{'snapshot_id':snapshot['id'],'question':'Acceptance: sentiment, uncertainty and source evidence'})
        run=wait('/api/runs/'+run['id']);report=run['report']
        checks['research_report']=run['status']=='partial' and report['findings']['US:AAPL']['sentiment']['status']=='conflicting'
        checks['citations_resolve']=all(docs[s['document_id']]['content'][span['start']:span['end']]==span['quote'] for s in report['sentiments'] for span in s['evidence'])
        steps=client.get('/api/runs/'+run['id']+'/steps').json()['items']
        checks['trace_complete']=bool(steps) and all(s['status']=='completed' and s['data']['application_hash'] and s['tool_calls']
            and all(call['status']=='completed' and call['finished_at'] and call['data'].get('output') is not None for call in s['tool_calls']) for s in steps)
        missing=post('/api/snapshots',{'instrument_ids':['US:AAPL'],'cutoff':'2024-12-31T22:00:00Z'})
        missing_run=post('/api/runs',{'snapshot_id':missing['id'],'question':'Acceptance missing data'})
        missing_run=wait('/api/runs/'+missing_run['id'])
        checks['insufficient_evidence_abstains']=missing_run['status']=='partial' and missing_run['report']['findings']['US:AAPL']['research_signal']['signal']=='NO_SIGNAL'
        cfg=post('/api/configurations',{'sentiment_engine':'finbert','inference_retries':1})
        with patch('research.workflow.local_finbert',side_effect=TimeoutError('explicit acceptance failure fixture')) as provider:
            failing=post('/api/runs',{'snapshot_id':snapshot['id'],'configuration_id':cfg['id'],'question':'Injected provider failure fixture'})
            failing=wait('/api/runs/'+failing['id'])
        checks['bounded_failure_fixture']=failing['status']=='failed' and provider.call_count==2
        entered=threading.Event()
        def cancellable(texts,cancelled,timeout):
            entered.set()
            while not cancelled(): time.sleep(.01)
            raise Cancelled('Explicit cancellation fixture')
        with patch('research.workflow.local_finbert',side_effect=cancellable):
            cancelling=post('/api/runs',{'snapshot_id':snapshot['id'],'configuration_id':cfg['id'],'question':'Cancellation fixture'})
            if not entered.wait(5): raise TimeoutError('Provider fixture never entered')
            post('/api/runs/'+cancelling['id']+'/cancel')
            cancelling=wait('/api/runs/'+cancelling['id'])
        checks['cancellation_fixture']=cancelling['status']=='cancelled' and cancelling['report'] is None
        dataset=post('/api/datasets',{'instrument_id':'US:SPY','start':'2025-01-02','end':'2025-01-21'})
        experiment=post('/api/experiments',{'dataset_id':dataset['id'],'train_end':'2025-01-07','validation_end':'2025-01-14','test_start':'2025-01-15'})
        experiment=wait('/api/studies/'+experiment['id'])
        if experiment['status']!='completed': raise RuntimeError(experiment.get('error'))
        comparisons=experiment['result']['comparisons']
        checks['simulation_reconciles']=all(abs(p['equity']-p['cash']-p['shares']*p['close'])<1e-6 for partition in comparisons.values() for variant in partition.values() for p in variant['equity_curve'])
        checks['strategy_exercises_fills']=comparisons['test']['verified']['metrics']['filled_orders']>0
        details['synthetic_test_metrics']={name:variant['metrics'] for name,variant in comparisons['test'].items()}
        details['synthetic_dataset_id']=dataset['id']
        evaluation=post('/api/evaluations');evaluation=wait('/api/studies/'+evaluation['id'])
        checks['evaluation_integrated']=evaluation['status']=='completed' and evaluation['result']['engineering_pass']
        for fault in ('invalid-citation','lookahead-fill'):
            mutated=run_suite(inject_fault=fault);checks['reject_'+fault]=not mutated['engineering_pass']
        checks['restored_gates']=run_suite()['engineering_pass']
        checks['external_execution_disabled']=client.post('/trade',json={}).status_code==403
        if args.real_model:
            actual=post('/api/runs',{'snapshot_id':snapshot['id'],'configuration_id':cfg['id'],'question':'Actual local model integration'})
            actual=wait('/api/runs/'+actual['id'])
            checks['real_model']=actual['status'] in {'completed','partial'} and actual['report']['model']['mode']=='real_local_inference'
            details['real_model']=actual['report']['model'] if actual['report'] else actual['error']
        else:
            details['real_model']='not run; --real-model is required to claim actual inference validation'
    artifact={'checks':checks,'passed':all(checks.values()),'application_hash':code_version(),'dependencies':dependency_versions(),
        'mode':'actual application with synthetic fixtures; provider failures/cancellation explicitly mocked','details':details,
        'remaining':['Human semantic review','Visual browser verification','Final requirement-by-requirement audit']}
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':artifact['passed'],'checks':checks,'artifact':str(path),'remaining':artifact['remaining']},indent=2))
    return 0 if artifact['passed'] else 1


if __name__=='__main__': raise SystemExit(main())
