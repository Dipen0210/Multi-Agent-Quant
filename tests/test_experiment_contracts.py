from copy import deepcopy
import time
from unittest.mock import patch
from pydantic import ValidationError
from research.experiments import ExperimentRequest, run_experiment, selected_market, simulation_comparisons
from research.experiment_results import ExperimentResult, validate_experiment_sources
from workflow_support import WorkflowFixture


class ExperimentContractTests(WorkflowFixture):
    def request(self):
        response=self.client.post('/api/datasets',json={'instrument_id':'US:AAPL','start':'2025-01-02','end':'2025-01-21'})
        response.raise_for_status()
        return ExperimentRequest(dataset_id=response.json()['id'],train_end='2025-01-07',validation_end='2025-01-14',test_start='2025-01-15')

    def result(self):
        return run_experiment(self.client.app.state.store,self.request())

    def wait_study(self,ident):
        for _ in range(600):
            response=self.client.get('/api/studies/'+ident)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            if result['status'] not in {'queued','running'}: return result
            time.sleep(.02)
        self.fail('Experiment did not terminate')

    def test_completed_experiment_api_round_trip_idempotency_and_list_bounds(self):
        payload=self.request().model_dump(mode='json')
        response=self.client.post('/api/experiments',json=payload,headers={'Idempotency-Key':'experiment-contract'})
        self.assertEqual(response.status_code,202,response.text)
        study=self.wait_study(response.json()['id'])
        self.assertEqual(study['status'],'completed',study)
        validate_experiment_sources(self.client.app.state.store,study['result'])
        repeated=self.client.post('/api/experiments',json=payload,headers={'Idempotency-Key':'experiment-contract'})
        self.assertEqual(repeated.status_code,202,repeated.text)
        self.assertEqual(study['result'],repeated.json()['result'])
        self.assertEqual(self.client.get('/api/studies?limit=1').json()['items'][0]['id'],study['id'])
        self.assertEqual(self.client.get('/api/studies?limit=101').status_code,422)
        self.assertEqual(self.client.get('/api/studies?offset=-1').status_code,422)
        cancelled=self.client.post('/api/studies/'+study['id']+'/cancel',json={})
        self.assertEqual(cancelled.status_code,200,cancelled.text)
        self.assertEqual(cancelled.json()['status'],'completed')

    def test_metrics_and_ledger_corruption_fail_structural_validation(self):
        original=self.result()
        mutations={
            'metrics':lambda r:r['comparisons']['test']['cash']['metrics'].update(total_return=.5),
            'cash':lambda r:r['comparisons']['test']['cash']['equity_curve'][0].update(cash=99),
            'end_position':lambda r:r['comparisons']['test']['cash']['end_position'].update(shares=3),
            'policy':lambda r:r['comparisons']['test']['cash']['policy'].update(fee_bps=77),
            'missing_variant':lambda r:r['comparisons']['test'].pop('cash'),
            'run_link':lambda r:r['research_run_ids'].pop(),
            'disagreement':lambda r:r.update(workflow_disagreement_count=999),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                damaged=deepcopy(original);mutate(damaged)
                with self.assertRaises(ValidationError): ExperimentResult.model_validate(damaged)

    def test_consistent_fake_price_is_rejected_against_frozen_market(self):
        damaged=self.result()
        # Cash has no position, so a changed close leaves its ledger/metrics consistent.
        damaged['comparisons']['test']['cash']['equity_curve'][0]['close']*=2
        ExperimentResult.model_validate(damaged)
        with self.assertRaisesRegex(ValueError,'frozen sources'):
            validate_experiment_sources(self.client.app.state.store,damaged)

    def test_recomputed_accounting_cannot_hide_a_changed_evidence_signal(self):
        damaged=self.result();signal=damaged['signals']['non_agent_sentiment'][0]
        signal['action']='LONG' if signal['action']!='LONG' else 'FLAT'
        selected,_=selected_market(self.client.app.state.store,damaged['dataset'])
        damaged['comparisons']=simulation_comparisons(selected,damaged['signals'],damaged['partitions'],
            ExperimentRequest.model_validate(damaged['request']),'US:AAPL')
        ExperimentResult.model_validate(damaged)
        with self.assertRaisesRegex(ValueError,'eligible evidence'):
            validate_experiment_sources(self.client.app.state.store,damaged)

    def test_worker_rejects_wrong_source_results_before_persistence(self):
        damaged=self.result();damaged['comparisons']['test']['cash']['equity_curve'][0]['close']*=2
        with patch('research.studies.run_experiment',return_value=damaged):
            response=self.client.post('/api/experiments',json=damaged['request']);response.raise_for_status()
            study=self.wait_study(response.json()['id'])
        self.assertEqual(study['status'],'failed',study)
        self.assertIsNone(study['result'])
        with self.client.app.state.store.connect() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM experiment_runs').fetchone()[0],0)

    def test_missing_linked_report_prevents_serving_completed_result(self):
        response=self.client.post('/api/experiments',json=self.request().model_dump(mode='json'))
        response.raise_for_status();study=self.wait_study(response.json()['id'])
        self.assertEqual(study['status'],'completed',study)
        with self.client.app.state.store.connect() as c:
            c.execute('UPDATE runs SET report=NULL WHERE id=?',(study['result']['research_run_ids'][0],))
        refused=self.client.get('/api/studies/'+study['id'])
        self.assertEqual(refused.status_code,500,refused.text)
        self.assertEqual(refused.json()['error']['code'],'invalid_response')
        self.assertNotIn('Apple',refused.text)
