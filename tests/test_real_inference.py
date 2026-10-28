"""Explicit actual local integration check; never substitutes fixtures for inference."""
import os
import time
import unittest
from research.configuration import Configuration, register
from workflow_support import WorkflowFixture


@unittest.skipUnless(os.getenv('RUN_REAL_MODEL')=='1','Set RUN_REAL_MODEL=1 to run cached real FinBERT integration')
class RealInferenceTests(WorkflowFixture):
    def test_real_model_and_exact_recorded_replay(self):
        config=register(self.client.app.state.store,Configuration(sentiment_engine='finbert'))
        run=self.submit(configuration_id=config['id'])
        for _ in range(400):
            result=self.client.get('/api/runs/'+run['id']).json()
            if result['status'] not in {'queued','running'}: break
            time.sleep(.1)
        self.assertIn(result['status'],['completed','partial'],result)
        model=result['report']['model']
        self.assertEqual(model['mode'],'real_local_inference')
        self.assertEqual(model['model_id'],'Dipen0210/finbert-finetuned')
        self.assertTrue(model['revision'])
        replay_config=register(self.client.app.state.store,Configuration(sentiment_engine='recorded',recording_id=model['recording_id']))
        replay=self.client.post('/api/runs',json={'snapshot_id':self.snap['id'],'question':'Replay exact inputs','configuration_id':replay_config['id']}).json()
        replay=self.wait(replay['id'])
        self.assertEqual(replay['report']['model']['mode'],'recorded_replay')
        self.assertEqual(model['probabilities'],replay['report']['model']['probabilities'])

    def test_real_model_historical_research_retains_contamination_disclosure(self):
        from research.experiments import DatasetRequest, ExperimentRequest, freeze_dataset, run_experiment
        store=self.client.app.state.store
        dataset=freeze_dataset(store,DatasetRequest(instrument_id='US:AAPL',start='2025-01-02',end='2025-01-06'))
        result=run_experiment(store,ExperimentRequest(dataset_id=dataset['id'],train_end='2025-01-02',validation_end='2025-01-03',test_start='2025-01-06',configuration=Configuration(sentiment_engine='finbert')))
        self.assertEqual(result['validity_tier'],'synthetic_pipeline')
        self.assertTrue(any('contamination' in text for text in result['limitations']))
        reports=[self.client.app.state.jobs.get(ident)['report'] for ident in result['research_run_ids']]
        self.assertTrue(any(r['model']['mode']=='real_local_inference' for r in reports))
        for report in reports:
            self.assertFalse(report['external_execution'])
            self.assertEqual(report['verification']['status'],'passed')
