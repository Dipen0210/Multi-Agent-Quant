import json
import time
import unittest
from unittest.mock import patch
from research.jobs import Jobs, RunRequest
from research.models import local_finbert, Cancelled
from research.outputs import validate_output
from research.sentiment import analyze_record
from research.workflow import verify_evidence, quantitative
from workflow_support import WorkflowFixture


class ResilienceTests(WorkflowFixture):
    def test_retry_cannot_bypass_queue_capacity(self):
        jobs=self.client.app.state.jobs
        payload=RunRequest(snapshot_id=self.snap['id'],question='Fixture queue admission')
        # Hold scheduling, exercising the real durable admission path without
        # consuming a slot before the capacity assertion.
        with patch.object(jobs,'schedule'):
            retryable=jobs.create(payload)
            jobs.cancel(retryable['id'])
            queued=[jobs.create(payload) for _ in range(20)]
            with self.assertRaisesRegex(ValueError,'capacity'):
                jobs.retry(retryable['id'])
            self.assertEqual(jobs.get(retryable['id'])['status'],'cancelled')
            self.assertEqual(jobs.get(retryable['id'])['attempt'],0)
            with self.assertRaisesRegex(ValueError,'capacity'):
                jobs.create(payload)
            jobs.cancel(queued[0]['id'])
            self.assertEqual(jobs.retry(retryable['id'])['status'],'queued')
            with jobs.store.connect() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running')").fetchone()[0],20)

    def test_recovery_and_retry_preserve_attempt_history(self):
        with patch('research.workflow.Workflow.collect',side_effect=ValueError('fixture fail')):
            run=self.wait(self.submit()['id'])
        self.assertEqual(run['status'],'failed')
        retried=self.client.post('/api/runs/'+run['id']+'/retry',json={})
        self.assertEqual(retried.status_code,200,retried.text)
        done=self.wait(run['id']);self.assertEqual(done['attempt'],2)
        self.assertIn(done['status'],['partial','completed'])
        self.assertEqual({s['attempt'] for s in self.client.app.state.jobs.steps(run['id'])},{1,2})
        jobs=self.client.app.state.jobs; jobs.close()
        with self.client.app.state.store.connect() as c:
            c.execute("UPDATE runs SET status='running',cancelled=0 WHERE id=?",(run['id'],))
        self.client.app.state.jobs=Jobs(self.client.app.state.store)
        recovered=self.wait(run['id'])
        self.assertEqual(recovered['attempt'],3)
        self.assertIn(recovered['status'],['partial','completed'])

    def test_exact_quote_from_wrong_entity_is_rejected(self):
        store=self.client.app.state.store
        doc=next(d for d in store.records('documents') if d['data']['original_id']=='multi')
        result=analyze_record(doc,'US:MSFT',self.snap['request']['cutoff']).model_dump(mode='json')
        result['instrument_id']='US:AAPL'
        with self.assertRaisesRegex(ValueError,'entity-specific'): verify_evidence(store,self.snap,[result])

    def test_intermediate_schema_and_trace_contract(self):
        with self.assertRaises(ValueError): validate_output('sentiment',{'sentiments':[],'model':{'model_id':'fake'}})
        with self.assertRaises(ValueError): validate_output('evidence',{'document_ids':[],'unexpected':True})
        run=self.wait(self.submit()['id'])
        for step in self.client.app.state.jobs.steps(run['id']):
            trace=step['data']
            self.assertEqual(len(trace['application_hash']),64)
            self.assertEqual(len(trace['input_state_hash']),64)
            self.assertIn('langgraph',trace['dependencies'])
            self.assertIn('input_state',trace)

    def test_local_model_cancelled_before_inference_starts(self):
        with self.assertRaises(Cancelled): local_finbert(['Apple grew.'],cancelled=lambda:True)

    def test_trace_failure_prevents_successful_report(self):
        with patch('research.workflow.validate_output',side_effect=ValueError('fixture invalid output')):
            run=self.wait(self.submit()['id'])
        self.assertEqual(run['status'],'failed');self.assertIsNone(run['report'])
