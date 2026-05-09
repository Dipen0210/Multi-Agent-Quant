from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.routes.ask       import router as ask_router
from api.routes.stream    import router as stream_router
from api.routes.portfolio import router as portfolio_router
from api.routes.analytics import router as analytics_router

app = FastAPI(
    title="QuantSentiment Agent",
    description=(
        "Multi-agent AI system for financial reasoning. "
        "6 specialized LangGraph agents — News Analyst, Technical Analyst, "
        "Macro Context, Risk Manager, Portfolio Manager, Critic."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ask_router,       tags=["Agent"])
app.include_router(stream_router,    tags=["Agent"])
app.include_router(portfolio_router, tags=["Portfolio"])
app.include_router(analytics_router, tags=["Analytics"])
