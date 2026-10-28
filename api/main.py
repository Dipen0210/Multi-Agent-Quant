"""Local research API. Legacy integrations are explicitly opt-in and never execute orders."""
import os
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from research.store import Store
from research.jobs import Jobs
from research.studies import Studies
from api.boundaries import RequestBoundary, ALLOWED_ORIGINS
from api.research_routes import router as research_router
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv

load_dotenv()
# V2 audit records are local; never inherit automatic remote trace export.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
from api.routes.trade import router as trade_router

@asynccontextmanager
async def lifespan(app):
    app.state.store = Store(os.getenv("RESEARCH_DB", "runtime/research.sqlite3"))
    app.state.jobs = Jobs(app.state.store)
    app.state.studies = Studies(app.state.store,app.state.jobs)
    try:
        yield
    finally:
        app.state.studies.close()
        app.state.jobs.close()


app = FastAPI(lifespan=lifespan, title="QuantSentiment Research", version="2.0.0-dev",
              description="Evidence-grounded research and internal simulation. External trading disabled.")
app.add_middleware(RequestBoundary)
app.include_router(research_router, tags=["Research"])


@app.exception_handler(RequestValidationError)
async def invalid_contract(request, exc):
    return JSONResponse({"error":{"code":"invalid_contract","message":"Request failed schema validation",
        "fields":[{"location":list(e["loc"]),"type":e["type"]} for e in exc.errors()]}},status_code=422)


@app.exception_handler(KeyError)
async def missing_resource(request, exc):
    return JSONResponse({"error":{"code":"not_found","message":"Resource not found"}},status_code=404)


@app.exception_handler(ResponseValidationError)
async def invalid_response(request, exc):
    # Validation details may contain stored evidence; never expose them in errors.
    return JSONResponse({'error':{'code':'invalid_response','message':'Stored research output failed validation; no report was accepted'}},status_code=500)


@app.exception_handler(ValueError)
async def invalid_request(request, exc):
    return JSONResponse({"error":{"code":"invalid_request","message":str(exc)}},status_code=422)


app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"])
app.include_router(trade_router, tags=["Execution boundary"])


@app.get("/health")
def health():
    return {"status":"ok", "version":"2.0.0-dev", "deployment":"single-user-local",
            "external_execution":False, "timestamp":datetime.now(timezone.utc).isoformat()}


if os.getenv("ENABLE_LEGACY_ANALYSIS", "false").lower() == "true":
    from api.routes.ask import router as ask_router
    from api.routes.stream import router as stream_router
    app.include_router(ask_router, tags=["Legacy — unvalidated for V2"])
    app.include_router(stream_router, tags=["Legacy — unvalidated for V2"])
else:
    @app.post("/ask")
    @app.get("/stream")
    def legacy_disabled():
        raise HTTPException(410, detail={"code":"legacy_disabled", "message":"Use V2 research runs. Legacy provider analysis is opt-in."})


@app.get("/analytics")
@app.get("/portfolio")
def legacy_portfolio_disabled():
    raise HTTPException(410, detail={"code":"legacy_metrics_unvalidated",
        "message":"Legacy brokerage analytics excluded from V2. Use internal research experiments."})
