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


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict('os.environ',{'RESEARCH_DB':str(Path(self.temp.name)/'db.sqlite3')});self.env.start()
        self.client=TestClient(app);self.client.__enter__()
        self.client.post('/api/demo/import',json={}).raise_for_status()
        self.config=register(app.state.store,Configuration(workflow='verified'))
        self.snap=self.client.post('/api/snapshots',json={'instrument_ids':['US:AAPL'],'cutoff':'2025-01-03T22:00:00Z'}).json()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.env.stop();self.temp.cleanup()

    def submit(self,**changes):
        request={'snapshot_id':self.snap['id'],'question':'What does eligible evidence say about Apple?','configuration_id':self.config['id']}|changes
        result=self.client.post('/api/runs',json=request,headers={'Idempotency-Key':'test-run'})
        self.assertEqual(result.status_code,202,result.text)
        return result.json()

    def wait(self,ident):
        for _ in range(200):
            result=self.client.get('/api/runs/'+ident).json()
            if result['status'] not in {'queued','running'}: return result
            time.sleep(.01)
        self.fail('Run did not terminate within test budget')
