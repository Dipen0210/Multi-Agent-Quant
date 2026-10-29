"""Frozen dataset corruption must stop API reads and experiment admission."""
from copy import deepcopy
from unittest.mock import patch
from research.datasets import DatasetResponse
from research.store import canonical, digest, now
from workflow_support import WorkflowFixture


class DatasetContractTests(WorkflowFixture):
    payload={'instrument_id':'US:AAPL','start':'2025-01-02','end':'2025-01-21'}

    def create_dataset(self):
        response=self.client.post('/api/datasets',json=self.payload)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def assert_invalid(self,response):
        self.assertEqual(response.status_code,500,response.text)
        self.assertEqual(response.json()['error']['code'],'invalid_response')
        self.assertNotIn('manifest',response.text)

    def test_round_trip_identity_idempotency_and_pagination(self):
        first=self.create_dataset()
        self.assertEqual(first,self.create_dataset())
        self.assertEqual(first,self.client.get('/api/datasets/'+first['id']).json())
        parsed=DatasetResponse.model_validate(first)
        self.assertEqual(first,parsed.model_dump(mode='json'))
        second=self.client.post('/api/datasets',json=self.payload|{'instrument_id':'US:MSFT'})
        second.raise_for_status()
        page1=self.client.get('/api/datasets?limit=1').json()['items']
        page2=self.client.get('/api/datasets?limit=1&offset=1').json()['items']
        self.assertEqual(len(page1),1);self.assertEqual(len(page2),1)
        self.assertNotEqual(page1[0]['id'],page2[0]['id'])
        self.assertEqual(self.client.get('/api/datasets?limit=101').status_code,422)
        self.assertEqual(self.client.get('/api/datasets?offset=-1').status_code,422)
        self.assertEqual(self.client.get('/api/datasets/missing').status_code,404)

    def test_declared_response_rejects_invalid_hash_duplicates_and_tier(self):
        original=self.create_dataset()
        for corruption in ('hash','duplicates','tier'):
            with self.subTest(corruption=corruption):
                damaged=deepcopy(original)
                if corruption=='hash': damaged['id']='0'*64
                else:
                    if corruption=='duplicates': damaged['manifest']['market_ids']*=2
                    else: damaged['manifest']['validity_tier']='historical_limited_metadata'
                    damaged['id']=digest({key:damaged[key] for key in ('request','manifest')})
                with patch('api.research_routes.freeze_dataset',return_value=damaged):
                    self.assert_invalid(self.client.post('/api/datasets',json=self.payload))

    def test_missing_membership_blocks_reads_repeat_freeze_and_job_admission(self):
        frozen=self.create_dataset();ident=frozen['id']
        with self.client.app.state.store.connect() as c:
            c.execute('DELETE FROM dataset_documents WHERE dataset_id=? AND document_id=?',
                      (ident,frozen['manifest']['document_ids'][0]))
            before=c.execute('SELECT count(*) FROM studies').fetchone()[0]
        self.assert_invalid(self.client.get('/api/datasets/'+ident))
        self.assert_invalid(self.client.get('/api/datasets'))
        # Idempotent creation must detect damage, not silently repair audit links.
        self.assert_invalid(self.client.post('/api/datasets',json=self.payload))
        self.assert_invalid(self.client.post('/api/experiments',json={
            'dataset_id':ident,'train_end':'2025-01-07','validation_end':'2025-01-14','test_start':'2025-01-15'}))
        with self.client.app.state.store.connect() as c:
            self.assertEqual(before,c.execute('SELECT count(*) FROM studies').fetchone()[0])

    def test_valid_hash_cannot_hide_sources_outside_declared_scope(self):
        frozen=self.create_dataset()
        for changes in ({'instrument_id':'US:MSFT'}, {'start':'2024-01-02','end':'2024-01-21'}, {'provenance':'recorded'}):
            with self.subTest(changes=changes):
                payload=deepcopy(frozen);payload['request'].update(changes)
                if changes.get('provenance'): payload['manifest']['validity_tier']='historical_limited_metadata'
                ident=digest({key:payload[key] for key in ('request','manifest')})
                with self.client.app.state.store.connect() as c:
                    c.execute('INSERT INTO datasets VALUES (?,?,?,?)',
                              (ident,now(),canonical(payload['request']),canonical(payload['manifest'])))
                    c.executemany('INSERT INTO dataset_documents VALUES (?,?)',[(ident,x) for x in payload['manifest']['document_ids']])
                    c.executemany('INSERT INTO dataset_market VALUES (?,?)',[(ident,x) for x in payload['manifest']['market_ids']])
                self.assert_invalid(self.client.get('/api/datasets/'+ident))

    def test_altered_source_fails_even_with_unchanged_membership(self):
        frozen=self.create_dataset();ident=frozen['manifest']['document_ids'][0]
        with self.client.app.state.store.connect() as c:
            # Deliberate fault injection in this isolated test database only.
            c.execute('DROP TRIGGER documents_no_update')
            c.execute('UPDATE documents SET content_hash=? WHERE id=?',('0'*64,ident))
        self.assert_invalid(self.client.get('/api/datasets/'+frozen['id']))
