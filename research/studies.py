"""Evaluation/experiment jobs share the bounded single local research worker."""
import json
import time
import uuid
from pydantic import ValidationError
from research.experiments import ExperimentRequest, run_experiment
from research.datasets import get_dataset
from research.models import Cancelled
from research.store import canonical,digest,now
from evaluation.suite import run_suite,persist
from evaluation.contracts import EvaluationRequest, EvaluationStudy, StudyIntegrityError
from evaluation.storage import get_evaluation


class Studies:
    def __init__(self,store,jobs):
        self.store=store;self.jobs=jobs
        with store.connect() as c:
            c.execute("UPDATE studies SET status='queued',result=NULL,error='Interrupted; restarting immutable inputs' WHERE status='running' AND cancelled=0")
            c.execute("UPDATE studies SET status='cancelled',result=NULL WHERE cancelled=1 AND status IN ('queued','running')")
            pending=[r['id'] for r in c.execute("SELECT id FROM studies WHERE status='queued'")]
        for ident in pending: jobs.executor.submit(self.work,ident)

    def get(self,ident):
        with self.store.connect() as c: row=c.execute('SELECT * FROM studies WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError('Study not found')
        try:
            result=dict(row)|{'request':json.loads(row['request']),'result':json.loads(row['result']) if row['result'] else None}
            if row['kind']=='evaluation':
                EvaluationStudy.model_validate(result)
                if result['result'] is not None and get_evaluation(self.store,result['result']['id'])!=result['result']:
                    raise ValueError('Study result differs from persisted evaluation')
        except (ValueError,TypeError) as exc:
            raise StudyIntegrityError('Stored study failed validation') from exc
        return result

    def create(self,kind,payload,key=None):
        if kind=='experiment': get_dataset(self.store,payload.dataset_id)
        data=payload.model_dump(mode='json');request_hash=digest({'kind':kind,'request':data});key=key or str(uuid.uuid4())
        if len(key)>160: raise ValueError('Idempotency key too long')
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM studies WHERE idempotency_key=?',(key,)).fetchone()
            if row:
                if row['request_hash']!=request_hash: raise ValueError('Idempotency key conflict')
                ident=row['id'];created=False
            else:
                if c.execute("SELECT count(*) FROM studies WHERE status IN ('queued','running')").fetchone()[0]>=10: raise ValueError('Study queue capacity reached')
                ident=str(uuid.uuid4());created=True
                c.execute('INSERT INTO studies(id,kind,idempotency_key,request_hash,request,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                    (ident,kind,key,request_hash,canonical(data),'queued',now(),now()))
        if created: self.jobs.executor.submit(self.work,ident)
        return self.get(ident)

    def cancel(self,ident):
        self.get(ident)
        with self.store.connect() as c: c.execute("UPDATE studies SET cancelled=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated_at=? WHERE id=? AND status IN ('queued','running')",(now(),ident))
        return self.get(ident)

    def work(self,ident):
        with self.store.connect() as c:
            changed=c.execute("UPDATE studies SET status='running',attempt=attempt+1,result=NULL,error=NULL,updated_at=? WHERE id=? AND status='queued' AND cancelled=0",(now(),ident)).rowcount
        if not changed: return
        start=time.monotonic()
        def cancelled():
            if time.monotonic()-start>180: raise TimeoutError('Study exceeded 180 second budget')
            with self.store.connect() as c: return bool(c.execute('SELECT cancelled FROM studies WHERE id=?',(ident,)).fetchone()[0])
        try:
            study=self.get(ident)
            if cancelled(): raise Cancelled('Study cancelled')
            if study['kind']=='evaluation':
                payload=EvaluationRequest.model_validate(study['request'])
                result=run_suite(payload.engine,payload.split,cancelled=cancelled)
                if cancelled(): raise Cancelled('Study cancelled')
                result=persist(self.store,result)
            else:
                result=run_experiment(self.store,ExperimentRequest.model_validate(study['request']),cancelled)
                if cancelled(): raise Cancelled('Study cancelled')
                with self.store.connect() as c:
                    c.execute('INSERT INTO experiment_runs VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,result=excluded.result,error=NULL',
                        (ident,now(),'completed',canonical(study['request']),canonical(result),None))
            with self.store.connect() as c: c.execute("UPDATE studies SET status=CASE WHEN cancelled=1 THEN 'cancelled' ELSE 'completed' END,result=CASE WHEN cancelled=1 THEN NULL ELSE ? END,error=NULL,updated_at=? WHERE id=?",(canonical(result),now(),ident))
        except Exception as exc:
            message='Study output failed validation' if isinstance(exc,(ValidationError,StudyIntegrityError)) else type(exc).__name__+': '+str(exc)[:300]
            with self.store.connect() as c: c.execute("UPDATE studies SET status=CASE WHEN cancelled=1 THEN 'cancelled' ELSE ? END,result=NULL,error=?,updated_at=? WHERE id=?",('cancelled' if isinstance(exc,Cancelled) else 'failed',message,now(),ident))

    def close(self):
        with self.store.connect() as c: c.execute("UPDATE studies SET cancelled=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE status IN ('queued','running')")
