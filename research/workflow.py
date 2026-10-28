"""Bounded LangGraph research workflow. Roles use narrow functions, no arbitrary tools."""
from __future__ import annotations
from datetime import datetime
import json
import time
import uuid
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langsmith import tracing_context
from research.contracts import Contract, SnapshotRequest, MarketObservation, Document
from research.configuration import Configuration
from research.models import local_finbert, Cancelled
from research.outputs import validate_output
from research.versioning import code_version, dependency_versions
from research.sentiment import SentimentResult, analyze_record, aggregate, evidence_spans
from research.signals import research_signal
from research.store import canonical, digest, now


class WorkflowState(TypedDict, total=False):
    document_ids: list[str]
    sentiments: list[dict]
    model: dict
    quantitative: dict
    verification: dict
    report: dict


def verify_evidence(store, snapshot, sentiments):
    eligible=set(snapshot['manifest']['document_ids']); cutoff=datetime.fromisoformat(snapshot['request']['cutoff'])
    for raw in sentiments:
        result=SentimentResult.model_validate(raw)
        if result.document_id not in eligible: raise ValueError('Invalid citation: document outside snapshot')
        record=store.document(result.document_id); doc=Document.model_validate(record['data'])
        if doc.available_at>cutoff: raise ValueError('Future evidence contamination')
        if result.instrument_id not in snapshot['request']['instrument_ids'] or result.instrument_id not in doc.instrument_ids:
            raise ValueError('Incompatible citation entity')
        if digest(record['data']) != record['id'] or digest(doc.content)!=record['content_hash']:
            raise ValueError('Evidence content hash mismatch')
        if result.cutoff != cutoff: raise ValueError('Mismatched sentiment cutoff')
        if result.status=='supported' and not result.evidence: raise ValueError('Supported claim has no evidence')
        allowed_spans,_ = evidence_spans(record,result.instrument_id)
        allowed={(span.start,span.end,span.quote) for span in allowed_spans}
        for span in result.evidence:
            if (span.start,span.end,span.quote) not in allowed:
                raise ValueError('Citation span is not eligible entity-specific evidence')
            if span.document_id != result.document_id or doc.content[span.start:span.end] != span.quote:
                raise ValueError('Invalid citation span')
    return {'status':'passed','checked_results':len(sentiments),'checks':['existence','snapshot_membership','availability','entity','content_hash','exact_spans'],
            'semantic_support':'Exact excerpts support attribution only; sentiment interpretation remains an uncalibrated model/rule judgment.'}


def quantitative(store, snapshot):
    rows=[]
    with store.connect() as c:
        for ident in snapshot['manifest']['market_ids']:
            row=c.execute('SELECT data FROM market WHERE id=?',(ident,)).fetchone()
            if not row: raise ValueError('Missing market evidence')
            rows.append((ident,MarketObservation.model_validate_json(row['data'])))
    result={}
    for instrument in snapshot['request']['instrument_ids']:
        bars=sorted([(key,bar) for key,bar in rows if bar.instrument_id==instrument],key=lambda item:item[1].interval_end)
        ambiguous=len({bar.interval_end for _,bar in bars})!=len(bars)
        if not bars or ambiguous:
            result[instrument]={'status':'insufficient_evidence','reason':'Missing or competing market observations','last_close':None,'tool':'eligible-close-summary-v1'}
            continue
        key,last=bars[-1]
        cutoff=datetime.fromisoformat(snapshot['request']['cutoff'])
        if last.available_at>cutoff:
            raise ValueError('Future market observation contamination')
        if len({bar.adjustment_policy for _,bar in bars})!=1:
            result[instrument]={'status':'insufficient_evidence','reason':'Mixed price adjustment policies','last_close':None,'tool':'eligible-close-summary-v1'}
            continue
        result[instrument]={'status':'supported','last_close':last.close,'available_at':last.available_at.isoformat(),
             'observation_id':key,'observations':len(bars),'currency':last.currency,
             'previous_observation_return':last.close/bars[-2][1].close-1 if len(bars)>1 else None,
             'return_interval':'Between the last two eligible observations; not necessarily consecutive sessions',
             'tool':'eligible-close-summary-v1','adjustment_policy':last.adjustment_policy}
    return result


class Workflow:
    def __init__(self, store, run, config: Configuration):
        self.store=store;self.run=run;self.config=config
        self.snapshot=store.get_snapshot(run['snapshot_id'])
        self.started=time.monotonic();self.parent=None
        self.active_step=None;self.step_deadline=None;self.tool_stack=[];self.tool_ordinal=0
        self.cancelled=lambda: self._cancelled()

    def _cancelled(self):
        with self.store.connect() as c:
            row=c.execute('SELECT cancelled FROM runs WHERE id=?',(self.run['id'],)).fetchone()
        return bool(row['cancelled'])

    def check(self):
        if self.cancelled(): raise Cancelled('Cancelled by user')
        if self.remaining()<=0: raise TimeoutError('Run, step or tool budget exhausted')

    def remaining(self):
        deadlines=[self.started+self.config.run_timeout_seconds]
        if self.step_deadline is not None: deadlines.append(self.step_deadline)
        deadlines.extend(deadline for _,deadline in self.tool_stack)
        return max(0,min(deadlines)-time.monotonic())

    def call_tool(self,role,function,inputs,tool):
        """Durably record narrow tools before use, including nested model attempts.

        A call receives the remaining parent/run budget, not a fresh timeout on
        retry. There is no dynamic tool dispatch or source-controlled tool name.
        """
        self.check()
        if self.active_step is None: raise RuntimeError('Tool requires a durable parent step')
        if self.tool_ordinal>=30: raise ValueError('Tool call budget exceeded')
        ident=str(uuid.uuid4());start=time.monotonic()
        budget=min(self.config.step_timeout_seconds,self.remaining())
        parent=self.tool_stack[-1][0] if self.tool_stack else None
        ordinal=self.tool_ordinal;self.tool_ordinal+=1
        metadata={'role':role,'tool_schema_version':'v1','snapshot_id':self.snapshot['id'],
            'configuration_id':self.run['configuration_id'],'input':inputs,'input_hash':digest(inputs),
            'resource_budget_seconds':budget,'validation_failures':[],'tokens':None,'cost':None}
        with self.store.connect() as c:
            c.execute('INSERT INTO tool_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (ident,self.run['id'],self.active_step,parent,self.run['attempt'],ordinal,tool,'running',now(),None,None,canonical(metadata)))
        # Freeze inputs before the caller mutates a shared workflow state.
        metadata=json.loads(canonical(metadata));status='failed'
        self.tool_stack.append((ident,start+budget))
        try:
            output=validate_output(role,function(inputs))
            if role=='report':
                from research.report_validation import validate_report_sources
                validate_report_sources(self.store,output['report'],self.run)
            self.check()
            metadata['output']=output
            if role=='model':
                metadata['tokens']=output.get('token_usage')
                metadata['cost']=output.get('cost')
                metadata['model_identifier']={'id':output['model_id'],'revision':output.get('revision')}
                metadata['model_parameters']=output.get('parameters',{})
            status='completed'
            return output
        except Exception as exc:
            metadata['validation_failures']=[type(exc).__name__]
            status='cancelled' if isinstance(exc,Cancelled) else 'failed'
            raise
        finally:
            self.tool_stack.pop()
            with self.store.connect() as c:
                c.execute('UPDATE tool_calls SET status=?,finished_at=?,latency_ms=?,data=? WHERE id=?',
                    (status,now(),round((time.monotonic()-start)*1000,2),canonical(metadata),ident))

    def step(self, ordinal, role, function, tool):
        def wrapped(state):
            self.check(); ident=str(uuid.uuid4()); start=time.monotonic()
            step_budget=self.config.run_timeout_seconds if role=='research' else self.config.step_timeout_seconds
            metadata={'role':role,'tool':tool,'tool_schema_version':'v1','configuration_id':self.run['configuration_id'],
                'snapshot_id':self.snapshot['id'],'evidence_ids':self.snapshot['manifest']['document_ids'],
                'application_hash':code_version(),'dependencies':dependency_versions(),
                'input_state_hash':digest(state),'input_state':state,
                'prompt_version':'not_applicable_deterministic_role','prompt_hash':None,
                'tokens':None,'cost':None,'resource_budget_seconds':step_budget,'validation_failures':[]}
            with self.store.connect() as c:
                c.execute('INSERT INTO steps VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (ident,self.run['id'],self.parent,self.run['attempt'],ordinal,role,'running',now(),None,None,canonical(metadata)))
            self.parent=ident
            self.active_step=ident;self.step_deadline=start+step_budget;self.tool_ordinal=0
            status='failed'
            try:
                output=validate_output(role,function(state)) if role=='research' else self.call_tool(role,function,state,tool)
                self.check()
                if time.monotonic()-start>step_budget: raise TimeoutError('Step budget exhausted')
                metadata['output']=output
                served_model=output.get('model') or output.get('report',{}).get('model')
                if served_model:
                    metadata['tokens']=served_model.get('token_usage')
                    metadata['model_identifier']={'id':served_model['model_id'],'revision':served_model.get('revision')}
                    metadata['model_parameters']=served_model.get('parameters',{})
                status='completed'
                return output
            except Exception as exc:
                metadata['validation_failures']=[type(exc).__name__]
                status='cancelled' if isinstance(exc,Cancelled) else 'failed'
                raise
            finally:
                self.active_step=None;self.step_deadline=None
                with self.store.connect() as c:
                    c.execute('UPDATE steps SET status=?,finished_at=?,latency_ms=?,data=? WHERE id=?',
                        (status,now(),round((time.monotonic()-start)*1000,2),canonical(metadata),ident))
        return wrapped

    def collect(self,state):
        docs=self.snapshot['manifest']['document_ids']
        if len(docs)>self.config.max_documents: raise ValueError('Document budget exceeded; narrow the snapshot')
        # Assert source membership and availability before inference, including ablation workflows.
        cutoff=datetime.fromisoformat(self.snapshot['request']['cutoff'])
        for ident in docs:
            self.check()
            record=self.store.document(ident)
            if Document.model_validate(record['data']).available_at>cutoff: raise ValueError('Future evidence before inference')
        return {'document_ids':docs}

    def sentiment(self,state):
        pairs=[];texts=[]
        for ident in state['document_ids']:
            record=self.store.document(ident)
            for instrument in self.snapshot['request']['instrument_ids']:
                if instrument not in record['data']['instrument_ids']: continue
                spans,_=evidence_spans(record,instrument)
                pairs.append((record,instrument, bool(spans)))
                if spans:
                    text=' '.join(s.quote for s in spans)
                    if len(text)>10000: raise ValueError('Evidence text exceeds inference budget')
                    texts.append(text)
        model={'model_id':'lexicon-v1','revision':'lexicon-v1','calibrated':False,'token_usage':None,'cost':None,'mode':'deterministic_baseline'}
        scores=[]
        if texts and self.config.sentiment_engine=='finbert':
            errors=[]
            for attempt in range(self.config.inference_retries+1):
                self.check()
                try:
                    def infer(payload):
                        return local_finbert(payload['texts'],self.cancelled,self.remaining()) | {'mode':'real_local_inference'}
                    model=self.call_tool('model',infer,{'texts':texts},'local-finbert-inference')
                    model['mode']='real_local_inference';model['retry_failures']=errors
                    break
                except (RuntimeError,TimeoutError) as exc:
                    if isinstance(exc,Cancelled): raise
                    errors.append(type(exc).__name__)
                    if attempt==self.config.inference_retries: raise
            scores=model['probabilities']
            recording_id=digest({'inputs':texts,'output':model})
            with self.store.connect() as c:
                c.execute('INSERT OR IGNORE INTO inference_recordings VALUES (?,?,?,?,?)',
                    (recording_id,self.run['id'],digest(texts),canonical(model),now()))
            model['recording_id']=recording_id
        elif texts and self.config.sentiment_engine=='recorded':
            with self.store.connect() as c:
                row=c.execute('SELECT * FROM inference_recordings WHERE id=?',(self.config.recording_id,)).fetchone()
            if not row or row['input_hash']!=digest(texts): raise ValueError('Recording missing or incompatible with exact inference inputs')
            model=json.loads(row['output']);model['mode']='recorded_replay';model['recording_id']=row['id'];scores=model['probabilities']
        results=[];i=0
        for record,instrument,has_spans in pairs:
            self.check()
            probability=scores[i] if scores and has_spans else None
            if has_spans: i+=1
            result=analyze_record(record,instrument,self.snapshot['request']['cutoff'],
                model_version=model['model_id']+'@'+str(model.get('revision') or 'unknown'),probabilities=probability)
            results.append(result.model_dump(mode='json'))
        return {'sentiments':results,'model':model}

    def quantify(self,state): return {'quantitative':quantitative(self.store,self.snapshot)}

    def verify(self,state):
        return {'verification':verify_evidence(self.store,self.snapshot,state['sentiments'])}

    def report(self,state):
        self.check()
        # Citation validity is a mandatory boundary even when the semantic verifier is ablated.
        mandatory=self.call_tool('verification',self.verify,state,'mandatory-citation-and-cutoff-check')['verification']
        findings={}; partial=False
        for instrument in self.snapshot['request']['instrument_ids']:
            results=[SentimentResult.model_validate(r) for r in state['sentiments'] if r['instrument_id']==instrument]
            summary=aggregate(results,self.snapshot['manifest']['duplicate_groups'])
            quant=state['quantitative'][instrument]
            signal=research_signal(summary,quant,self.config.policy)
            partial |= summary['status']=='insufficient_evidence' or summary['excluded_or_uncertain']>0 or quant['status']!='supported'
            findings[instrument]={'sentiment':summary,'quantitative':quant,'research_signal':signal,
                'counterevidence':[r.document_id for r in results if r.label=='negative' or r.status in {'conflicting','uncertain'}],
                'hypothesis':'Sentiment may relate to subsequent returns; this run does not validate that relationship.',
                'alternative_interpretation':'Public information may already be reflected in market prices.'}
        report={'run_id':self.run['id'],'question':self.run['request']['question'],
            'snapshot':self.snapshot,'configuration_id':self.run['configuration_id'],
            'execution_mode':state['model']['mode'],'data_provenance':self.snapshot['request']['provenance'],
            'created_at':now(),'status':'partial' if partial else 'completed',
            'findings':findings,'sentiments':state['sentiments'],'model':state['model'],
            'verification':mandatory,'trace_reference':'/api/runs/'+self.run['id']+'/steps',
            'template':'evidence-report-v1','limitations':self.snapshot['manifest']['limitations']+[
                'Sentiment scores are not calibrated probabilities or forecasts.',
                'Synthetic data validates software behavior only; no historical return claim.',
                'Cached model training data provenance and historical outcome contamination are unresolved.',
                'Semantic claim support has not yet been validated against human-reviewed cases.'],
            'external_execution':False}
        return {'report':report}

    def single_pass(self,state):
        # One researcher executes the same bounded tool contracts, without separate role handoffs.
        combined=self.call_tool('evidence',self.collect,state,'eligible-snapshot-read')
        combined.update(self.call_tool('sentiment',self.sentiment,combined,'entity-sentiment'))
        combined.update(self.call_tool('quantitative',self.quantify,combined,'eligible-close-summary'))
        return self.call_tool('report',self.report,combined,'evidence-report-template')

    def execute(self):
        graph=StateGraph(WorkflowState)
        nodes=[('evidence',self.collect,'eligible-snapshot-read'),('sentiment',self.sentiment,'entity-sentiment'),
               ('quantitative',self.quantify,'eligible-close-summary')]
        if self.config.workflow=='verified': nodes.append(('verification',self.verify,'citation-and-cutoff-check'))
        nodes.append(('report',self.report,'evidence-report-template'))
        if self.config.workflow=='single_pass':
            nodes=[('research',self.single_pass,'eligible-evidence/entity-sentiment/quantitative/report')]
        previous=START
        for i,(name,function,tool) in enumerate(nodes):
            graph.add_node(name,self.step(i,name,function,tool));graph.add_edge(previous,name);previous=name
        graph.add_edge(previous,END)
        # V2 uses the durable local trace store; inherited .env tracing must not export evidence.
        with tracing_context(enabled=False):
            return graph.compile().invoke({},config={'recursion_limit':8})['report']
