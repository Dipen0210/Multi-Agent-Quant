import os
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from agent.state import AgentState
from agent.schemas import PortfolioSignal

SYSTEM_PROMPT = """You are a senior portfolio manager at a quant hedge fund.
You receive sentiment analysis from four independent sources about a specific stock.
Your job is ONLY to reason about sentiment — not about price, charts, or market conditions.

Scoring rules:
- 3 or 4 sources bullish → BUY, confidence 0.70–0.90
- 2 sources bullish + 0 bearish → BUY if confidence strong, else HOLD
- 2 sources bullish + 1 bearish → HOLD (conflicting)
- 3 or 4 sources bearish → SELL, confidence 0.70–0.90
- Anything else → HOLD

CRITICAL: Neutral is NOT a bearish signal. A source being neutral means it has no opinion.
Do NOT let neutral sources lower your conviction when other sources are clearly bullish/bearish.
Example: 3 bullish + 1 neutral = BUY with ~0.75 confidence (not HOLD).
Example: 2 bullish + 2 neutral = borderline, lean BUY with ~0.60 confidence.

Only HOLD when there is genuine conflict (bullish vs bearish) or fewer than 2 directional signals."""

SENTIMENT_TEMPLATE = """
Ticker: {ticker}

FINANCIAL NEWS SENTIMENT (today's articles, full body scored):
- Signal: {news_decision} (score: {news_score:.2f})
- Keywords: {news_keywords}
- Reasoning: {news_reasoning}

REDDIT COMMUNITY SENTIMENT (today's posts):
- Signal: {reddit_decision} (score: {reddit_score:.2f})
- Keywords: {reddit_keywords}
- Reasoning: {reddit_reasoning}

SEC FILING SENTIMENT (most recent filing):
- Signal: {sec_decision} (score: {sec_score:.2f})
- Keywords: {sec_keywords}
- Reasoning: {sec_reasoning}

ANALYST RATINGS SENTIMENT (institutional consensus):
- Signal: {analyst_decision} (score: {analyst_score:.2f})
- Keywords: {analyst_keywords}
- Reasoning: {analyst_reasoning}

Based PURELY on these four sentiment signals, provide:
1. A 2-sentence BULL CASE using evidence from the sentiment data above
2. A 2-sentence BEAR CASE using evidence from the sentiment data above
3. Final SIGNAL: exactly one of BUY / SELL / HOLD
4. CONFIDENCE: a float 0.0–1.0 reflecting how strongly the signals agree
5. RESOLUTION: one sentence explaining which signals dominated and why

Respond in this exact JSON format:
{{
  "signal": "BUY",
  "confidence": 0.75,
  "bull_case": "...",
  "bear_case": "...",
  "resolution": "..."
}}
"""


def _rule_based_signal(state: AgentState) -> PortfolioSignal:
    """Fallback when LLM is unavailable — simple vote across 4 sources."""
    fn  = state.get("financial_news")
    rd  = state.get("reddit_sentiment")
    sec = state.get("sec_filing")
    ana = state.get("analyst_ratings")

    bullish = sum(1 for s in [fn, rd, sec, ana] if s and s.decision == "bullish")
    bearish = sum(1 for s in [fn, rd, sec, ana] if s and s.decision == "bearish")
    total   = sum(1 for s in [fn, rd, sec, ana] if s is not None)

    if bullish >= 3:
        signal, conf = "BUY",  round(0.5 + bullish * 0.1, 2)
    elif bearish >= 3:
        signal, conf = "SELL", round(0.5 + bearish * 0.1, 2)
    elif bullish > bearish:
        signal, conf = "BUY",  0.55
    elif bearish > bullish:
        signal, conf = "SELL", 0.55
    else:
        signal, conf = "HOLD", 0.40

    return PortfolioSignal(
        signal=signal,
        confidence=conf,
        bull_case=f"Rule-based: {bullish}/{total} sources bullish.",
        bear_case=f"Rule-based: {bearish}/{total} sources bearish.",
        resolution=f"Majority vote {bullish}B/{bearish}Be/{total-bullish-bearish}N → {signal}",
    )


def portfolio_manager_node(state: AgentState) -> dict:
    if os.getenv("GROQ_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID"):
        try:
            signal = _llm_synthesis(state)
        except Exception as e:
            print(f"[Portfolio Manager] LLM failed, falling back to rules: {e}")
            signal = _rule_based_signal(state)
    else:
        signal = _rule_based_signal(state)

    return {
        "portfolio_signal": signal,
        "messages": [AIMessage(
            content=f"[Portfolio Manager] {signal.signal} | confidence={signal.confidence:.2f} | {signal.resolution[:80]}"
        )],
    }


def _llm_synthesis(state: AgentState) -> PortfolioSignal:
    import json
    from agent.tools.llm_client import get_llm

    fn  = state.get("financial_news")
    rd  = state.get("reddit_sentiment")
    sec = state.get("sec_filing")
    ana = state.get("analyst_ratings")

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  SENTIMENT_TEMPLATE),
    ])

    chain = prompt | get_llm()
    resp  = chain.invoke({
        "ticker":          state["ticker"],
        "news_decision":   fn.decision        if fn  else "N/A",
        "news_score":      fn.sentiment_score if fn  else 0.5,
        "news_keywords":   ", ".join(fn.keywords[:5]) if fn and fn.keywords else "none",
        "news_reasoning":  fn.reasoning       if fn  else "No data",
        "reddit_decision": rd.decision        if rd  else "N/A",
        "reddit_score":    rd.sentiment_score if rd  else 0.5,
        "reddit_keywords": ", ".join(rd.keywords[:5]) if rd and rd.keywords else "none",
        "reddit_reasoning":rd.reasoning       if rd  else "No data",
        "sec_decision":    sec.decision       if sec else "N/A",
        "sec_score":       sec.sentiment_score if sec else 0.5,
        "sec_keywords":    ", ".join(sec.keywords[:5]) if sec and sec.keywords else "none",
        "sec_reasoning":   sec.reasoning      if sec else "No data",
        "analyst_decision":ana.decision       if ana else "N/A",
        "analyst_score":   ana.sentiment_score if ana else 0.5,
        "analyst_keywords":ana.recommendation if ana else "none",
        "analyst_reasoning":ana.reasoning     if ana else "No data",
    })

    raw = resp.content.strip()
    if "```" in raw:
        raw = raw.split("```")[1].replace("json", "").strip()

    data = json.loads(raw)
    return PortfolioSignal(
        signal=data["signal"].upper(),
        confidence=float(data["confidence"]),
        bull_case=data["bull_case"],
        bear_case=data["bear_case"],
        resolution=data["resolution"],
    )
