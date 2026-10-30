from copy import deepcopy
import json
import time
from unittest.mock import patch
from pydantic import ValidationError
from evaluation.contracts import EvaluationResult
from evaluation.suite import run_suite, persist
from research.studies import Studies
from research.store import canonical, digest
from workflow_support import WorkflowFixture


class EvaluationContractTests(WorkflowFixture):
    def wait_study(self,ident):
        for _ in range(300):
            response=self.client.get('/api/studies/'+ident)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            if result['status'] not in {'queued','running'}: return result
            time.sleep(.01)
        self.fail('Study did not terminate')

    def evaluate(self):
        response=self.client.post('/api/evaluations',json={},headers={'Idempotency-Key':'contract-evaluation'})
        self.assertEqual(response.status_code,202,response.text)
        return self.wait_study(response.json()['id'])

    def assert_invalid(self,response):
        self.assertEqual(response.status_code,500,response.text)
        self.assertEqual(response.json()['error']['code'],'invalid_response')
        self.assertNotIn('Apple',response.text)

    def test_completed_result_identity_survives_api_and_typed_serialization(self):
        study=self.evaluate()
        self.assertEqual(study['status'],'completed',study)
        result=study['result']
        self.assertEqual(result['id'],digest({key:value for key,value in result.items() if key!='id'}))
        self.assertEqual(EvaluationResult.model_validate(result).model_dump(mode='json'),result)
        repeated=self.client.post('/api/evaluations',json={},headers={'Idempotency-Key':'contract-evaluation'})
        self.assertEqual(repeated.status_code,202,repeated.text)
        self.assertEqual(repeated.json()['result'],result)
        release=self.client.get('/api/release-status').json()
        self.assertEqual(release['latest_engineering_evaluation'],{'id':result['id'],'status':'passed'})
        self.assertFalse(release['full_release_pass'])

    def test_wrong_metrics_ground_truth_and_inference_are_rejected_before_persist(self):
        original=run_suite()
        mutations={
            'case_accuracy':lambda r:r['metrics'].update(case_accuracy=.5),
            'matrix':lambda r:r['metrics']['confusion_matrix']['positive'].update(positive=99),
            'gate':lambda r:r.update(engineering_pass=False,gate_failures=['invented_failure']),
            'review':lambda r:r['cases'][0]['human_review'].update(status='accepted',reviewer='fabricated'),
            'source':lambda r:r['cases'][0]['result'].update(document_id='0'*64),
            'inference':lambda r:r['cases'][0]['result'].update(score=.345),
            'missing_case':lambda r:r['cases'].pop(),
            'gate_identity':lambda r:r.update(gate_hash='0'*64),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                damaged=deepcopy(original);mutate(damaged)
                with self.assertRaises(ValidationError): persist(self.client.app.state.store,damaged)
        with self.client.app.state.store.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM evaluation_runs').fetchone()[0],0)

    def test_worker_refuses_malformed_output_and_redacts_validation_details(self):
        damaged=run_suite();damaged['cases'][0]['result']['score']=999
        with patch('research.studies.run_suite',return_value=damaged):
            result=self.evaluate()
        self.assertEqual(result['status'],'failed')
        self.assertIsNone(result['result'])
        self.assertEqual(result['error'],'Study output failed validation')
        with self.client.app.state.store.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM evaluation_runs').fetchone()[0],0)

    def test_persisted_status_corruption_blocks_release_and_study_reads(self):
        study=self.evaluate()
        with self.client.app.state.store.connect() as c:
            c.execute("UPDATE evaluation_runs SET status='failed' WHERE id=?",(study['result']['id'],))
        self.assert_invalid(self.client.get('/api/release-status'))
        self.assert_invalid(self.client.get('/api/studies/'+study['id']))

    def test_changed_request_cannot_relabel_a_completed_evaluation(self):
        study=self.evaluate();request={'engine':'baseline','split':'development'}
        with self.client.app.state.store.connect() as c:
            c.execute('UPDATE studies SET request=?,request_hash=? WHERE id=?',
                (canonical(request),digest({'kind':'evaluation','request':request}),study['id']))
        self.assert_invalid(self.client.get('/api/studies/'+study['id']))

    def test_interrupted_attempt_clears_stale_result_and_error(self):
        jobs=self.client.app.state.jobs;store=self.client.app.state.store
        with patch.object(jobs.executor,'submit'):
            response=self.client.post('/api/evaluations',json={});response.raise_for_status()
            ident=response.json()['id']
            with store.connect() as c:
                c.execute("UPDATE studies SET status='running',attempt=1,result=?,error='old interruption' WHERE id=?",(json.dumps({'stale':True}),ident))
            recovered=Studies(store,jobs)
        self.assertEqual(recovered.get(ident)['status'],'queued')
        self.assertIsNone(recovered.get(ident)['result'])
        recovered.work(ident)
        result=recovered.get(ident)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(result['attempt'],2)
        self.assertIsNone(result['error'])
