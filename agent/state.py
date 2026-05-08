from __future__ import annotations
from typing import Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from agent.schemas import (
    NewsAggregatorOutput,
    FinancialNewsOutput,
    RedditSentimentOutput,
    SECFilingOutput,
    AnalystRatingsOutput,
    TechnicalAnalystOutput,
    MacroContextOutput,
    RiskDecision,
    PortfolioSignal,
    CriticDecision,
    TradeExecution,
)


class AgentState(TypedDict):
    # Input
    ticker: str
    days: int

    # SSE streaming log
    messages: Annotated[list, add_messages]

    # News sub-agents (parallel)
    financial_news:   Optional[FinancialNewsOutput]
    reddit_sentiment: Optional[RedditSentimentOutput]
    sec_filing:       Optional[SECFilingOutput]
    analyst_ratings:  Optional[AnalystRatingsOutput]

    # Analysis tier outputs
    news_analyst:      Optional[NewsAggregatorOutput]
    technical_analyst: Optional[TechnicalAnalystOutput]
    macro_context:     Optional[MacroContextOutput]

    # Decision tier outputs
    risk_decision: Optional[RiskDecision]
    portfolio_signal: Optional[PortfolioSignal]
    critic_decision: Optional[CriticDecision]

    # Execution
    trade_execution: Optional[TradeExecution]

    # Metadata
    sources: list[str]
    start_time_ms: int
