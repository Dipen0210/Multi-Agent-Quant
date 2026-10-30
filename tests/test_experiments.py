import copy
from datetime import datetime
import json
import time
from unittest.mock import patch
from research.experiments import DatasetRequest, ExperimentRequest, freeze_dataset, run_experiment, historical_snapshot
from research.store import digest
from workflow_support import WorkflowFixture


class ExperimentTests(WorkflowFixture):
    def dataset(self):
        return freeze_dataset(self.client.app.state.store,DatasetRequest(instrument_id='US:AAPL',start='2025-01-02',end='2025-01-21'))

    def test_frozen_inputs_comparisons_and_accounting(self):
        data=self.dataset();request=ExperimentRequest(dataset_id=data['id'],train_end='2025-01-07',validation_end='2025-01-14',test_start='2025-01-15')
        result=run_experiment(self.client.app.state.store,request)
        self.assertEqual(result['validity_tier'],'synthetic_pipeline')
        self.assertEqual(result['workflow_disagreement_count'],0)
        self.assertGreater(len(result['research_run_ids']),0)
        for partition,variants in result['comparisons'].items():
            self.assertEqual(set(variants),{'cash','passive_same_exposure','non_agent_sentiment','single_pass','verified','without_deduplication'})
            self.assertEqual(variants['cash']['metrics']['total_return'],0)
            self.assertEqual(variants['verified']['metrics'],variants['single_pass']['metrics'])
            for variant in variants.values():
                for point in variant['equity_curve']:
                    self.assertAlmostEqual(point['equity'],point['cash']+point['shares']*point['close'])
        again=run_experiment(self.client.app.state.store,request)
        def accounting(value):
            if isinstance(value,dict): return {key:accounting(item) for key,item in value.items() if key!='source_run_id'}
            if isinstance(value,list): return [accounting(item) for item in value]
            return value
        self.assertEqual(accounting(result['comparisons']),accounting(again['comparisons']))
        self.assertNotEqual(result['execution_id'],again['execution_id'])
        self.assertTrue(set(result['research_run_ids']).isdisjoint(again['research_run_ids']))
        # Identical frozen inputs reproduce accounting while preserving both histories.
        self.assertEqual(result['snapshot_ids'],again['snapshot_ids'])
        from research.experiment_results import validate_experiment_sources
        validate_experiment_sources(self.client.app.state.store,result)
        validate_experiment_sources(self.client.app.state.store,again)

    def test_future_revision_not_visible_in_historical_snapshot(self):
        data=self.dataset()
        snapshot=historical_snapshot(self.client.app.state.store,data,datetime.fromisoformat('2025-01-03T22:00:00+00:00'))
        docs=[self.client.app.state.store.document(ident)['data'] for ident in snapshot['manifest']['document_ids']]
        self.assertTrue(all(d['revision']==1 for d in docs))
        self.assertNotIn('late',[d['original_id'] for d in docs])

    def test_study_api_evaluation_and_idempotency(self):
        first=self.client.post('/api/evaluations',json={},headers={'Idempotency-Key':'evaluation'}).json()
        second=self.client.post('/api/evaluations',json={},headers={'Idempotency-Key':'evaluation'}).json()
        self.assertEqual(first['id'],second['id'])
        for _ in range(300):
            result=self.client.get('/api/studies/'+first['id']).json()
            if result['status'] not in {'queued','running'}: break
            time.sleep(.01)
        self.assertEqual(result['status'],'completed',result)
        self.assertTrue(result['result']['engineering_pass'])
        self.assertFalse(self.client.get('/api/release-status').json()['full_release_pass'])
