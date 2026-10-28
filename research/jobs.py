"""Durable bounded local job runner. One server process; no external side effects."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
from pathlib import Path
import threading
import uuid
from pydantic import Field
from research.contracts import Contract
from research.configuration import Configuration, register
from research.models import Cancelled
from research.store import canonical, digest, now
from research.workflow import Workflow


class RunRequest(Contract):
    snapshot_id: str = Field(min_length=64,max_length=64,pattern=r'^[a-f0-9]+$')
    question: str = Field(min_length=1,max_length=2000)
    configuration_id: str | None = Field(default=None,min_length=64,max_length=64,pattern=r'^[a-f0-9]+$')


class Jobs:
    def __init__(self,store):
        self.store=store
        self.lock=open(store.path+'.worker.lock','a')
        try: fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lock.close();raise RuntimeError('Research store already has a worker; use one server process')
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='research')
        self.guard=threading.Lock();self.scheduled=set();self.closed=False
        register(store,Configuration())
        # Interrupted computations are safe to repeat: all external order paths are blocked.
        with store.connect() as c:
            c.execute("UPDATE steps SET status='failed',finished_at=? WHERE status='running'",(now(),))
            interrupted=c.execute("SELECT id,data FROM tool_calls WHERE status='running'").fetchall()
            for call in interrupted:
                metadata=json.loads(call['data']);metadata['validation_failures']=['InterruptedProcess']
                c.execute("UPDATE tool_calls SET status='failed',finished_at=?,data=? WHERE id=?",(now(),canonical(metadata),call['id']))
            c.execute("UPDATE runs SET status='queued',report=NULL,updated_at=?,error='Interrupted process; automatic retry' WHERE status='running' AND cancelled=0",(now(),))
            c.execute("UPDATE runs SET status='cancelled',updated_at=? WHERE cancelled=1 AND status IN ('queued','running')",(now(),))
            pending=[r['id'] for r in c.execute("SELECT id FROM runs WHERE status='queued'").fetchall()]
        for ident in pending: self.schedule(ident)

    def get(self,ident):
        with self.store.connect() as c:
            row=c.execute('SELECT * FROM runs WHERE id=?',(ident,)).fetchone()
        if not row: raise KeyError('Run not found')
        result=dict(row)
        result['request']=json.loads(result['request'])
        result['report']=json.loads(result['report']) if result['report'] else None
        return result

    def create(self,request: RunRequest,key=None):
        self.store.get_snapshot(request.snapshot_id)
        payload=request.model_dump(mode='json')
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            config=request.configuration_id or c.execute('SELECT configuration_id FROM active_configuration WHERE singleton=1').fetchone()[0]
            if not c.execute('SELECT id FROM configurations WHERE id=?',(config,)).fetchone(): raise KeyError('Configuration not found')
            payload['configuration_id']=config
            request_hash=digest(payload);key=key or str(uuid.uuid4())
            if len(key)>160: raise ValueError('Idempotency key too long')
            existing=c.execute('SELECT id,request_hash FROM runs WHERE idempotency_key=?',(key,)).fetchone()
            if existing:
                if existing['request_hash']!=request_hash: raise ValueError('Idempotency key already used with different request')
                ident=existing['id']
            else:
                count=c.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running')").fetchone()[0]
                if count>=20: raise ValueError('Local queue capacity reached')
                ident=str(uuid.uuid4())
                c.execute('INSERT INTO runs(id,idempotency_key,request_hash,snapshot_id,configuration_id,status,created_at,updated_at,request) VALUES (?,?,?,?,?,?,?,?,?)',
                    (ident,key,request_hash,request.snapshot_id,config,'queued',now(),now(),canonical(payload)))
        self.schedule(ident)
        return self.get(ident)

    def schedule(self,ident):
        with self.guard:
            if self.closed: raise RuntimeError('Worker shutting down')
            if ident in self.scheduled: return
            self.scheduled.add(ident)
        self.executor.submit(self.work,ident)

    def work(self,ident):
        try:
            with self.store.connect() as c:
                changed=c.execute("UPDATE runs SET status='running',attempt=attempt+1,updated_at=? WHERE id=? AND status='queued' AND cancelled=0",(now(),ident)).rowcount
                if not changed: return
                row=c.execute('SELECT data FROM configurations WHERE id=(SELECT configuration_id FROM runs WHERE id=?)',(ident,)).fetchone()
            run=self.get(ident);config=Configuration.model_validate_json(row['data'])
            report=Workflow(self.store,run,config).execute()
            with self.store.connect() as c:
                # Cancellation wins a race with final report completion.
                c.execute("UPDATE runs SET status=CASE WHEN cancelled=1 THEN 'cancelled' ELSE ? END,report=CASE WHEN cancelled=1 THEN NULL ELSE ? END,updated_at=?,error=NULL WHERE id=?",
                    (report['status'],canonical(report),now(),ident))
        except Exception as exc:
            status='cancelled' if isinstance(exc,Cancelled) else 'failed'
            with self.store.connect() as c:
                c.execute("UPDATE runs SET status=CASE WHEN cancelled=1 THEN 'cancelled' ELSE ? END,error=?,updated_at=? WHERE id=?",
                    (status,type(exc).__name__+': research computation failed; inspect step validation failures',now(),ident))
        finally:
            with self.guard: self.scheduled.discard(ident)

    def cancel(self,ident):
        self.get(ident)
        with self.store.connect() as c:
            c.execute("UPDATE runs SET cancelled=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,updated_at=? WHERE id=? AND status IN ('queued','running')",(now(),ident))
        return self.get(ident)

    def retry(self,ident):
        with self.guard:
            if ident in self.scheduled: raise ValueError('Run still active')
        self.get(ident)
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            status=c.execute('SELECT status FROM runs WHERE id=?',(ident,)).fetchone()['status']
            if status not in {'failed','cancelled'}: raise ValueError('Only failed or cancelled runs can be retried')
            if c.execute("SELECT count(*) FROM runs WHERE status IN ('queued','running')").fetchone()[0]>=20:
                raise ValueError('Local queue capacity reached')
            changed=c.execute("UPDATE runs SET status='queued',cancelled=0,error=NULL,report=NULL,updated_at=? WHERE id=? AND status IN ('failed','cancelled')",(now(),ident)).rowcount
        if not changed: raise ValueError('Only failed or cancelled runs can be retried')
        self.schedule(ident)
        return self.get(ident)

    def steps(self,ident,limit=100,offset=0):
        self.get(ident)
        with self.store.connect() as c:
            rows=c.execute('SELECT * FROM steps WHERE run_id=? ORDER BY attempt,ordinal LIMIT ? OFFSET ?',(ident,limit,offset)).fetchall()
        calls=self.tool_calls(ident,step_ids=[row['id'] for row in rows])
        return [dict(row)|{'data':json.loads(row['data']),'tool_calls':[call for call in calls if call['step_id']==row['id']]} for row in rows]

    def tool_calls(self,ident,limit=300,offset=0,step_ids=None):
        self.get(ident)
        where='t.run_id=?';parameters=[ident]
        if step_ids is not None:
            if not step_ids: return []
            where+=' AND t.step_id IN ('+','.join('?' for _ in step_ids)+')'
            parameters.extend(step_ids);limit=len(step_ids)*30;offset=0
        with self.store.connect() as c:
            rows=c.execute('SELECT t.* FROM tool_calls t JOIN steps s ON s.id=t.step_id WHERE '+where+' ORDER BY t.attempt,s.ordinal,t.ordinal LIMIT ? OFFSET ?',(*parameters,limit,offset)).fetchall()
        return [dict(row)|{'data':json.loads(row['data'])} for row in rows]

    def close(self):
        with self.guard: self.closed=True
        with self.store.connect() as c:
            c.execute("UPDATE runs SET cancelled=1 WHERE status IN ('queued','running')")
        self.executor.shutdown(wait=True,cancel_futures=False)
        with self.store.connect() as c:
            c.execute("UPDATE runs SET status='cancelled' WHERE cancelled=1 AND status IN ('queued','running')")
        fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()
