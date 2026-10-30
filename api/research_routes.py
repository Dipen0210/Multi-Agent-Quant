"""V2 local research API. Uploaded content is data, never an executable instruction."""
from pathlib import Path
import json
from typing import Annotated, Literal
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.exceptions import ResponseValidationError
from pydantic import Field
from research.contracts import Contract, SnapshotRequest, UNIVERSE
from research.importers import parse_csv
from api.responses import RunResponse, RunList, StepList, ToolList
from api.data_responses import (InstrumentList, ImportReceipt, DemoReceipt, EvidenceList,
    DocumentResponse, SourceHealthResponse, ConfigurationResponse, ConfigurationList, ConfigurationActivation)
from research.reports import ReportSnapshot
from research.report_validation import validate_report_sources

router = APIRouter(prefix='/api')


def checked_run(request, run):
    if run.get('report') is not None:
        try:
            validate_report_sources(request.app.state.store,run['report'],run)
        except (ValueError,KeyError) as exc:
            raise ResponseValidationError([{'loc':('response','report'),'type':'invalid_grounding','msg':'Stored report failed evidence validation'}]) from exc
    return run


class ImportRequest(Contract):
    documents: list[dict] = Field(default_factory=list,max_length=500)
    market: list[dict] = Field(default_factory=list,max_length=500)


@router.get('/instruments',response_model=InstrumentList)
def instruments():
    return {'items':[{'id':key,**value} for key,value in UNIVERSE.items()],
            'universe_policy':'Fixed AAPL/MSFT/SPY universe; current constituents; survivorship bias applies.',
            'frequency':'daily','timezone':'America/New_York'}


@router.post('/imports',response_model=ImportReceipt)
def import_data(payload: ImportRequest, request: Request):
    return request.app.state.store.import_records(payload.documents,payload.market)


@router.post('/imports/csv/{kind}',response_model=ImportReceipt)
async def import_csv(kind: Literal['documents','market'], request: Request):
    try:
        rows = parse_csv((await request.body()).decode('utf-8'),kind)
    except (ValueError,UnicodeError) as exc:
        raise HTTPException(422,detail={'code':'invalid_csv','message':'CSV must be UTF-8, bounded, and contain valid JSON array fields'}) from exc
    return request.app.state.store.import_records(**{kind:rows})


@router.post('/demo/import',response_model=DemoReceipt)
def demo_import(request: Request):
    data=json.loads((Path(__file__).parents[1]/'research/fixtures/demo.json').read_text())
    return request.app.state.store.import_records(data['documents'],data['market']) | {'mode':'synthetic','description':data['description']}


@router.get('/evidence',response_model=EvidenceList)
def evidence(request: Request, limit: int = Query(default=100,ge=1,le=500)):
    return {'documents':request.app.state.store.records('documents',limit),
            'market':request.app.state.store.records('market',limit)}


@router.get('/evidence/{document_id}',response_model=DocumentResponse)
def document(document_id: str, request: Request):
    return request.app.state.store.document(document_id)


@router.post('/snapshots',response_model=ReportSnapshot)
def snapshot(payload: SnapshotRequest, request: Request):
    return request.app.state.store.snapshot(payload)


@router.get('/snapshots/{snapshot_id}',response_model=ReportSnapshot)
def get_snapshot(snapshot_id: str, request: Request):
    return request.app.state.store.get_snapshot(snapshot_id)


@router.get('/source-health',response_model=SourceHealthResponse)
def source_health(request: Request, limit: int = Query(default=100,ge=1,le=100), offset: int = Query(default=0,ge=0,le=1000000)):
    with request.app.state.store.connect() as conn:
        rows=conn.execute("SELECT provider,'documents' kind,max(available_at) latest_available_at,max(ingested_at) latest_import_at,count(*) records FROM documents GROUP BY provider UNION ALL SELECT provider,'market' kind,max(available_at),max(ingested_at),count(*) FROM market GROUP BY provider ORDER BY provider,kind LIMIT ? OFFSET ?",(limit,offset)).fetchall()
        rejects=conn.execute('SELECT count(*) FROM rejections').fetchone()[0]
    return {'sources':[dict(r) for r in rows],'rejected_records':rejects,
            'live_adapters':'not validated','freshness_policy':'Compare source availability with the selected cutoff; no live freshness claim.'}


from research.jobs import RunRequest
from research.configuration import Configuration, register, activate


@router.get('/configurations',response_model=ConfigurationList)
def configurations(request: Request, limit: int = Query(default=100,ge=1,le=100), offset: int = Query(default=0,ge=0,le=1000000)):
    with request.app.state.store.connect() as c:
        rows=c.execute('SELECT * FROM configurations ORDER BY created_at DESC,id LIMIT ? OFFSET ?',(limit,offset)).fetchall()
        active=c.execute('SELECT configuration_id FROM active_configuration WHERE singleton=1').fetchone()[0]
    return {'items':[dict(r)|{'data':json.loads(r['data'])} for r in rows],'active_configuration_id':active}


@router.post('/configurations',response_model=ConfigurationResponse)
def create_configuration(payload: Configuration, request: Request):
    return register(request.app.state.store,payload)


@router.post('/configurations/{configuration_id}/activate',response_model=ConfigurationActivation)
def activate_configuration(configuration_id: str, request: Request):
    return activate(request.app.state.store,configuration_id)


@router.post('/runs',status_code=202,response_model=RunResponse)
def create_run(payload: RunRequest, request: Request):
    return checked_run(request,request.app.state.jobs.create(payload,request.headers.get('Idempotency-Key')))


@router.get('/runs',response_model=RunList)
def runs(request: Request):
    with request.app.state.store.connect() as c:
        rows=c.execute('SELECT id,status,created_at,updated_at,configuration_id,snapshot_id FROM runs ORDER BY created_at DESC LIMIT 100').fetchall()
    return {'items':[dict(r) for r in rows]}


@router.get('/runs/{run_id}',response_model=RunResponse)
def run(run_id: str, request: Request):
    return checked_run(request,request.app.state.jobs.get(run_id))


@router.post('/runs/{run_id}/cancel',response_model=RunResponse)
def cancel_run(run_id: str, request: Request):
    return checked_run(request,request.app.state.jobs.cancel(run_id))


@router.post('/runs/{run_id}/retry',response_model=RunResponse)
def retry_run(run_id: str, request: Request):
    return checked_run(request,request.app.state.jobs.retry(run_id))


@router.get('/runs/{run_id}/steps',response_model=StepList)
def steps(run_id: str, request: Request, limit: int = Query(default=100,ge=1,le=100), offset: int = Query(default=0,ge=0,le=1000000)):
    return {'items':request.app.state.jobs.steps(run_id,limit,offset)}


@router.get('/runs/{run_id}/tools',response_model=ToolList)
def tools(run_id: str, request: Request, limit: int = Query(default=300,ge=1,le=300), offset: int = Query(default=0,ge=0,le=1000000)):
    return {'items':request.app.state.jobs.tool_calls(run_id,limit,offset)}


from research.experiments import ExperimentRequest
from research.datasets import DatasetRequest, DatasetResponse, DatasetList, freeze_dataset, get_dataset
from research.studies import EvaluationRequest
from evaluation.contracts import EvaluationStudy, ReleaseStatus
from evaluation.storage import get_evaluation
from research.experiment_results import ExperimentStudy
from research.study_state import StudyList

StudyResponse=Annotated[EvaluationStudy|ExperimentStudy,Field(discriminator='kind')]


@router.post('/datasets',response_model=DatasetResponse)
def create_dataset(payload: DatasetRequest, request: Request):
    return freeze_dataset(request.app.state.store,payload)


@router.get('/datasets',response_model=DatasetList)
def datasets(request: Request, limit: int = Query(default=100,ge=1,le=100), offset: int = Query(default=0,ge=0,le=1000000)):
    with request.app.state.store.connect() as c:
        rows=c.execute('SELECT id FROM datasets ORDER BY created_at DESC,id LIMIT ? OFFSET ?',(limit,offset)).fetchall()
    return {'items':[get_dataset(request.app.state.store,row['id']) for row in rows]}


@router.get('/datasets/{dataset_id}',response_model=DatasetResponse)
def dataset(dataset_id: str, request: Request):
    return get_dataset(request.app.state.store,dataset_id)


@router.post('/evaluations',status_code=202,response_model=EvaluationStudy)
def evaluate(payload: EvaluationRequest, request: Request):
    return request.app.state.studies.create('evaluation',payload,request.headers.get('Idempotency-Key'))


@router.post('/experiments',status_code=202,response_model=ExperimentStudy)
def experiment(payload: ExperimentRequest, request: Request):
    return request.app.state.studies.create('experiment',payload,request.headers.get('Idempotency-Key'))


@router.get('/studies',response_model=StudyList)
def studies(request: Request, limit: int = Query(default=100,ge=1,le=100), offset: int = Query(default=0,ge=0,le=1000000)):
    with request.app.state.store.connect() as c:
        rows=c.execute('SELECT id,kind,status,created_at,updated_at,error FROM studies ORDER BY created_at DESC,id LIMIT ? OFFSET ?',(limit,offset)).fetchall()
    return {'items':[dict(row) for row in rows]}


@router.get('/studies/{study_id}',response_model=StudyResponse)
def study(study_id: str, request: Request):
    return request.app.state.studies.get(study_id)


@router.post('/studies/{study_id}/cancel',response_model=StudyResponse)
def cancel_study(study_id: str, request: Request):
    return request.app.state.studies.cancel(study_id)


@router.get('/release-status',response_model=ReleaseStatus)
def release_status(request: Request):
    with request.app.state.store.connect() as c:
        latest=c.execute('SELECT id FROM evaluation_runs ORDER BY created_at DESC,id LIMIT 1').fetchone()
    result=get_evaluation(request.app.state.store,latest['id']) if latest else None
    return {'full_release_pass':False,'latest_engineering_evaluation':{'id':result['id'],'status':'passed' if result['engineering_pass'] else 'failed'} if result else None,
        'blockers':['Human-reviewed semantic cases pending','Complete historical and frontend acceptance audit pending','Mandatory requirement evidence mapping incomplete'],
        'approval_status':'provisional engineering targets, not user-approved release requirements'}


from datetime import datetime
from pydantic import ValidationError, field_validator, model_validator
from research.contracts import utc, Document
from research.adapters import normalize_text, normalize_yfinance
from research.store import digest


class RecordedImport(Contract):
    provider: Literal['tavily','sec_edgar','reddit','yfinance']
    instrument_ids: list[str] = Field(min_length=1,max_length=3)
    captured_at: datetime | None = None
    historical_latency_seconds: int | None = Field(default=None,ge=0,le=604800)
    usage_restrictions: str = Field(min_length=1,max_length=800)
    records: list[dict] = Field(max_length=100)

    _entities=field_validator('instrument_ids')(classmethod(lambda cls,value:Document.known_entities(value)))
    _aware=field_validator('captured_at')(classmethod(lambda cls,value:utc(value) if value is not None else None))

    @model_validator(mode='after')
    def metadata(self):
        if self.provider=='yfinance':
            if len(self.instrument_ids)!=1 or self.historical_latency_seconds is None: raise ValueError('Market import needs one instrument and explicit latency')
        elif self.captured_at is None: raise ValueError('Recorded text import needs actual capture timestamp')
        return self


@router.post('/imports/recorded',response_model=ImportReceipt)
def recorded_import(payload: RecordedImport, request: Request):
    values=[];rejected=[]
    for index,raw in enumerate(payload.records):
        try:
            value=normalize_yfinance(raw,payload.instrument_ids[0],payload.historical_latency_seconds,payload.usage_restrictions) if payload.provider=='yfinance' else normalize_text(payload.provider,raw,payload.instrument_ids,payload.captured_at,payload.usage_restrictions)
            values.append(value)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            reason='; '.join('.'.join(str(x) for x in e['loc'])+': '+e['type'] for e in exc.errors()) if isinstance(exc,ValidationError) else type(exc).__name__+': required provider fields or timestamps invalid'
            rejected.append({'kind':'recorded_adapter','row':index,'input_hash':digest(raw),'reason':reason})
    return request.app.state.store.import_records(**{'market' if payload.provider=='yfinance' else 'documents':values},external_rejections=rejected)
