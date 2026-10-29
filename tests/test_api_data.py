from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
from fastapi.testclient import TestClient
from api.main import app


class DataAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict('os.environ',{'RESEARCH_DB':str(Path(self.temp.name)/'research.sqlite3')})
        self.env.start()
        self.client=TestClient(app)
        self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None); self.env.stop(); self.temp.cleanup()

    def test_actual_import_snapshot_and_citations(self):
        response=self.client.post('/api/demo/import',json={})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['rejected'],[])
        again=self.client.post('/api/demo/import',json={}).json()
        self.assertEqual(again['inserted'],0)
        self.assertGreater(again['duplicates'],0)
        snap=self.client.post('/api/snapshots',json={'instrument_ids':['US:AAPL'],'cutoff':'2025-01-03T22:00:00Z'}).json()
        docs=[self.client.get('/api/evidence/'+x).json()['data'] for x in snap['manifest']['document_ids']]
        self.assertNotIn('late',[x['original_id'] for x in docs])
        self.assertTrue(all(x['revision']==1 for x in docs))
        self.assertEqual(self.client.get('/api/snapshots/'+snap['id']).json()['manifest'],snap['manifest'])

    def test_boundaries_and_structured_errors(self):
        self.assertEqual(self.client.get('/api/evidence/missing').status_code,404)
        self.assertEqual(self.client.post('/api/demo/import',json={},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/demo/import',content='{}',headers={'Content-Type':'text/plain'}).status_code,415)
        self.assertEqual(self.client.post('/api/imports',content='x'*2000001,headers={'Content-Type':'application/json'}).status_code,413)
        self.assertEqual(self.client.get('/api/evidence?limit=100000').status_code,422)
        self.assertEqual(self.client.get('/health',headers={'Host':'evil.example'}).status_code,400)
        self.assertEqual(self.client.post('/trade',json={}).status_code,403)

    def test_recorded_adapter_is_integrated_and_quarantines_missing_metadata(self):
        result=self.client.post('/api/imports/recorded',json={'provider':'tavily','instrument_ids':['US:AAPL'],
            'captured_at':'2025-01-03T17:00:00Z','usage_restrictions':'Authorized local recording',
            'records':[{'title':'Recorded article','content':'Apple grew.','url':'https://example.com/a','published_at':'2025-01-03T16:00:00Z'},
                       {'title':'Missing publication','content':'Apple grew.','url':'https://example.com/b'}]})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['inserted'],1)
        self.assertEqual(len(result.json()['rejected']),1)
        self.assertEqual(self.client.get('/api/source-health').json()['rejected_records'],1)

    def test_data_responses_reject_corrupted_identity_without_echoing_source(self):
        imported=self.client.post('/api/demo/import',json={}).json()
        ident=imported['document_ids'][0]
        original=self.client.app.state.store.document(ident)
        for field,value in [('content_hash','a'*64),('provider','wrong-provider')]:
            with self.subTest(field=field):
                corrupted=deepcopy(original);corrupted[field]=value
                with patch.object(self.client.app.state.store,'document',return_value=corrupted):
                    response=self.client.get('/api/evidence/'+ident)
                self.assertEqual(response.status_code,500)
                self.assertEqual(response.json()['error']['code'],'invalid_response')
                self.assertNotIn(original['data']['content'],response.text)

    def test_receipt_count_and_configuration_hash_are_validated(self):
        with patch.object(self.client.app.state.store,'import_records',return_value={
            'batch_id':'00000000-0000-0000-0000-000000000000','inserted':5,'duplicates':0,
            'rejected':[],'document_ids':[],'market_ids':[]}):
            self.assertEqual(self.client.post('/api/imports',json={}).status_code,500)
        response=self.client.post('/api/configurations',json={'name':'Valid configuration'})
        response.raise_for_status()
        corrupted=response.json();corrupted['id']='a'*64
        with patch('api.research_routes.register',return_value=corrupted):
            invalid=self.client.post('/api/configurations',json={})
        self.assertEqual(invalid.status_code,500)
        self.assertEqual(invalid.json()['error']['code'],'invalid_response')

    def test_source_health_includes_market_and_configuration_lists_are_bounded(self):
        self.client.post('/api/demo/import',json={}).raise_for_status()
        response=self.client.get('/api/source-health');response.raise_for_status()
        self.assertEqual({item['kind'] for item in response.json()['sources']},{'documents','market'})
        self.assertEqual(len(self.client.get('/api/source-health?limit=1').json()['sources']),1)
        self.assertEqual(self.client.get('/api/source-health?limit=101').status_code,422)
        configs=self.client.get('/api/configurations?limit=1');configs.raise_for_status()
        self.assertEqual(len(configs.json()['items']),1)
        self.assertEqual(self.client.get('/api/configurations?limit=101').status_code,422)
        self.assertEqual(self.client.get('/api/configurations?offset=-1').status_code,422)
