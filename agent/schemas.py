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


class SimilarEvent(BaseModel):
    date: str
    event: str
    outcome: str


class FinancialNewsOutput(BaseModel):
    decision: str                        # bullish | bearish | neutral
    sentiment_label: str
    sentiment_score: float
    headline_count: int
    headlines: list[str]
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


class NewsAggregatorOutput(BaseModel):
    # Backward-compatible fields (used by Risk Manager etc.)
    sentiment_label: str
    sentiment_score: float
    headline_count: int
    breakdown: dict[str, float]
    headlines: list[str]
    similar_past_events: list[SimilarEvent] = []
    sec_context: str = ""

    # Individual source outputs
    financial_news: Optional[FinancialNewsOutput] = None
    reddit: Optional[RedditSentimentOutput] = None
    sec_filing: Optional[SECFilingOutput] = None
    analyst_ratings: Optional[AnalystRatingsOutput] = None

    # Aggregated
    source_agreement: str = "mixed"      # all_bullish | mostly_bullish | mixed | mostly_bearish | all_bearish


# Legacy alias kept so old imports don't break
NewsAnalystOutput = NewsAggregatorOutput


# ── Technical Analyst ──────────────────────────────────────────────────────────

class TechnicalAnalystOutput(BaseModel):
    rsi: float
    macd_signal: str                      # bullish_crossover / bearish_crossover / neutral
    bollinger_position: str               # above_upper / below_lower / mid_band
    regime: str                           # trending_up / trending_down / ranging / volatile
    chart_pattern: str = ""               # from vision model
    chart_image_path: str = ""


# ── Macro Context ──────────────────────────────────────────────────────────────

class MacroContextOutput(BaseModel):
    vix: float
    yield_10yr: float
    fed_stance: str                       # hawkish / dovish / neutral
    risk_environment: str                 # risk_on / risk_off / neutral
    favorable_for_sector: bool
    summary: str = ""


# ── Risk Manager ───────────────────────────────────────────────────────────────

class RiskDecision(BaseModel):
    decision: str                         # APPROVED / VETOED
    original_size: int
    adjusted_size: int
    stop_loss_pct: float
    stop_loss_price: float
    reason: str


# ── Portfolio Manager ──────────────────────────────────────────────────────────

class PortfolioSignal(BaseModel):
    signal: str                           # BUY / SELL / HOLD
    confidence: float = Field(..., ge=0.0, le=1.0)
    bull_case: str
    bear_case: str
    resolution: str


# ── Critic ─────────────────────────────────────────────────────────────────────

class CriticDecision(BaseModel):
    decision: str                         # PROCEED / HOLD
    confidence_check: bool
    agent_agreement: str                  # e.g. "3/3"
    flags: list[str] = []
    veto_reason: Optional[str] = None


# ── Execution ──────────────────────────────────────────────────────────────────

class TradeExecution(BaseModel):
    broker: str = "alpaca_paper"
    action: str                           # buy / sell / hold
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
    news_analyst: Optional[NewsAggregatorOutput] = None
    technical_analyst: Optional[TechnicalAnalystOutput] = None
    macro_context: Optional[MacroContextOutput] = None
    risk_manager: Optional[RiskDecision] = None
    portfolio_manager: Optional[PortfolioSignal] = None
    critic: Optional[CriticDecision] = None
    trade_executed: Optional[TradeExecution] = None
    sources: list[str] = []
    analysis_time_ms: int = 0
    timestamp: str = ""
