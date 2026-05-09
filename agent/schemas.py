from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol e.g. NVDA")
    days: int = Field(default=2, description="Days of news to fetch")


# ── News sub-agents ────────────────────────────────────────────────────────────

class HeadlineResult(BaseModel):
    text: str
    label: str
    score: float
    probabilities: dict[str, float]


class FinancialNewsOutput(BaseModel):
    decision: str                        # bullish | bearish | neutral
    sentiment_label: str
    sentiment_score: float
    headline_count: int
    headlines: list[str]
    article_urls: list[str] = []
    keywords: list[str]
    reasoning: str


class RedditSentimentOutput(BaseModel):
    decision: str
    sentiment_label: str
    sentiment_score: float
    post_count: int
    top_posts: list[str]
    keywords: list[str]
    reasoning: str


class SECFilingOutput(BaseModel):
    decision: str
    sentiment_label: str
    sentiment_score: float
    filing_type: str
    filing_url: str = ""
    key_findings: list[str]
    keywords: list[str]
    reasoning: str


class AnalystRatingsOutput(BaseModel):
    decision: str
    recommendation: str
    sentiment_score: float
    target_price: float
    current_price: float
    upside_pct: float
    analyst_count: int
    keywords: list[str]
    reasoning: str


# ── Macro Context ──────────────────────────────────────────────────────────────

class MacroContextOutput(BaseModel):
    # Market indices (numbers → Risk Manager uses these for safety gates)
    vix: float
    yield_10yr: float
    spy_5d_return: float              # e.g. -0.023 = -2.3%
    dxy: float                        # US Dollar Index

    # Derived safety labels
    fed_stance: str                   # hawkish / dovish / neutral
    risk_environment: str             # risk_on / risk_off / neutral
    market_trend: str                 # bullish / bearish / neutral (from SPY)

    # Global news sentiment (narrative → Portfolio Manager)
    sentiment_score: float
    sentiment_label: str
    global_news_keywords: list[str] = []
    global_news_urls: list[str] = []
    headline_count: int = 0

    # Pinecone trend context
    vix_trend: str = "stable"         # rising / falling / stable
    consecutive_risk_off_days: int = 0

    # Human-readable
    summary: str = ""
    reasoning: str = ""


# ── Risk Manager ───────────────────────────────────────────────────────────────

class RiskDecision(BaseModel):
    decision: str                      # APPROVED / VETOED
    original_size: int
    adjusted_size: int
    stop_loss_pct: float
    stop_loss_price: float
    reason: str
    market_safety_flags: list[str] = []


# ── Portfolio Manager ──────────────────────────────────────────────────────────

class PortfolioSignal(BaseModel):
    signal: str                        # BUY / SELL / HOLD
    confidence: float = Field(..., ge=0.0, le=1.0)
    bull_case: str
    bear_case: str
    resolution: str


# ── Critic ─────────────────────────────────────────────────────────────────────

class CriticDecision(BaseModel):
    decision: str                      # PROCEED / HOLD
    confidence_check: bool
    agent_agreement: str               # e.g. "3/4"
    flags: list[str] = []
    veto_reason: Optional[str] = None


# ── Execution ──────────────────────────────────────────────────────────────────

class TradeExecution(BaseModel):
    broker: str = "alpaca_paper"
    action: str                        # buy / sell / hold
    shares: int
    price: float
    stop_loss: float
    order_id: Optional[str] = None
    skipped_reason: Optional[str] = None


# ── Final Response ─────────────────────────────────────────────────────────────

class AgentResponse(BaseModel):
    ticker: str
    signal: str
    confidence: float
    # 4 source sentiment agents
    financial_news: Optional[FinancialNewsOutput] = None
    reddit: Optional[RedditSentimentOutput] = None
    sec_filing: Optional[SECFilingOutput] = None
    analyst_ratings: Optional[AnalystRatingsOutput] = None
    # Macro + decision tier
    macro_context: Optional[MacroContextOutput] = None
    portfolio_manager: Optional[PortfolioSignal] = None
    risk_manager: Optional[RiskDecision] = None
    critic: Optional[CriticDecision] = None
    trade_executed: Optional[TradeExecution] = None
    sources: list[str] = []
    analysis_time_ms: int = 0
    timestamp: str = ""
