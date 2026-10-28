import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from research.configuration import Configuration, register
from research.workflow import verify_evidence
from research.sentiment import analyze_record


from workflow_support import WorkflowFixture


class WorkflowTests(WorkflowFixture):
    def test_integrated_report_idempotency_trace_and_conflict(self):
        first=self.submit();again=self.submit()
        self.assertEqual(first['id'],again['id'])
        result=self.wait(first['id'])
        self.assertEqual(result['status'],'partial',result)
        report=result['report'];finding=report['findings']['US:AAPL']
        self.assertEqual(finding['sentiment']['status'],'conflicting')
        self.assertEqual(finding['research_signal']['signal'],'NO_SIGNAL')
        self.assertFalse(report['external_execution'])
        self.assertEqual(report['verification']['status'],'passed')
        steps=self.client.get('/api/runs/'+first['id']+'/steps').json()['items']
        self.assertEqual([s['role'] for s in steps],['evidence','sentiment','quantitative','verification','report'])
        self.assertTrue(all(s['status']=='completed' and s['latency_ms']>=0 for s in steps))
        self.assertTrue(all(s['data']['cost'] is None for s in steps))
        self.assertEqual(self.client.post('/api/runs',json={'snapshot_id':self.snap['id'],'question':'different'},headers={'Idempotency-Key':'test-run'}).status_code,422)

    def test_invalid_citation_and_future_snapshot_rejected(self):
        record=app.state.store.document(self.snap['manifest']['document_ids'][0])
        result=analyze_record(record,'US:AAPL',self.snap['request']['cutoff']).model_dump(mode='json')
        result['document_id']='nonexistent'
        with self.assertRaisesRegex(ValueError,'Invalid citation'): verify_evidence(app.state.store,self.snap,[result])
        all_docs=app.state.store.records('documents')
        late=next(r for r in all_docs if r['data']['original_id']=='late')
        result=analyze_record(late,'US:AAPL',self.snap['request']['cutoff']).model_dump(mode='json')
        corrupted=json.loads(json.dumps(self.snap));corrupted['manifest']['document_ids'].append(late['id'])
        with self.assertRaisesRegex(ValueError,'Future evidence'): verify_evidence(app.state.store,corrupted,[result])

    def test_bounded_provider_failure(self):
        config=register(app.state.store,Configuration(sentiment_engine='finbert',inference_retries=1))
        with patch('research.workflow.local_finbert',side_effect=TimeoutError('fixture timeout')) as provider:
            result=self.wait(self.submit(configuration_id=config['id'])['id'])
        self.assertEqual(result['status'],'failed')
        self.assertEqual(provider.call_count,2)
        steps=app.state.jobs.steps(result['id'])
        self.assertEqual(steps[-1]['status'],'failed')
        self.assertIn('TimeoutError',steps[-1]['data']['validation_failures'])

    def test_cancellation_stops_model_and_no_duplicate_jobs(self):
        from research.models import Cancelled
        import threading
        entered=threading.Event()
        def provider(texts,cancelled,timeout):
            entered.set()
            for _ in range(1000):
                if cancelled(): raise Cancelled('fixture cancellation')
                time.sleep(.005)
            raise AssertionError('Cancellation not observed')
        config=register(app.state.store,Configuration(sentiment_engine='finbert'))
        with patch('research.workflow.local_finbert',side_effect=provider) as model:
            run=self.submit(configuration_id=config['id'])
            self.assertTrue(entered.wait(2))
            self.client.post('/api/runs/'+run['id']+'/cancel',json={}).raise_for_status()
            result=self.wait(run['id'])
        self.assertEqual(result['status'],'cancelled');self.assertEqual(model.call_count,1)
        self.assertIsNone(result['report'])

    def test_empty_evidence_abstains(self):
        self.snap=self.client.post('/api/snapshots',json={'instrument_ids':['US:SPY'],'cutoff':'2024-12-31T22:00:00Z'}).json()
        result=self.wait(self.submit()['id'])
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['report']['findings']['US:SPY']['research_signal']['signal'],'NO_SIGNAL')
