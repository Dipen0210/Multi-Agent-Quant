import os
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from agent.state import AgentState
from agent.schemas import PortfolioSignal

SYSTEM_PROMPT = """You are a senior portfolio manager at a quant hedge fund.
You receive analysis from three specialist agents and must synthesize a trading decision.
Be concise, rigorous, and honest about uncertainty. Never recommend when confidence is low."""

ANALYSIS_TEMPLATE = """
Ticker: {ticker}

NEWS ANALYST:
- Sentiment: {sentiment_label} (score: {sentiment_score})
- Headlines analyzed: {headline_count}
- SEC context: {sec_context}

TECHNICAL ANALYST:
- RSI: {rsi} (>70 overbought, <30 oversold)
- MACD: {macd_signal}
- Bollinger: {bollinger_position}
- Regime: {regime}
- Chart pattern: {chart_pattern}

MACRO CONTEXT:
- VIX: {vix} | 10yr yield: {yield_10yr}%
- Fed stance: {fed_stance}
- Risk environment: {risk_environment}

RISK MANAGER:
- Decision: {risk_decision}
- Adjusted position size: {adjusted_size} shares
- Stop loss: ${stop_loss_price}

Based on this data, provide:
1. A 2-sentence BULL CASE (reasons to buy)
2. A 2-sentence BEAR CASE (reasons not to buy)
3. Final SIGNAL: exactly one of BUY / SELL / HOLD
4. CONFIDENCE: a float between 0.0 and 1.0
5. RESOLUTION: one sentence explaining why bull or bear case won

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
    """Fallback when LLM key is not available."""
    news  = state.get("news_analyst")
    tech  = state.get("technical_analyst")
    macro = state.get("macro_context")
    risk  = state.get("risk_decision")

    if risk and risk.decision == "VETOED":
        return PortfolioSignal(
            signal="HOLD", confidence=0.0,
            bull_case="N/A — trade vetoed by Risk Manager.",
            bear_case=risk.reason,
            resolution="Risk Manager veto overrides all signals.",
        )

    score = 0.0
    if news  and news.sentiment_label  == "positive": score += 1
    if tech  and tech.macd_signal      in ("bullish", "bullish_crossover"): score += 1
    if macro and macro.risk_environment == "risk_on": score += 1

    if score >= 2:
        signal, conf = "BUY",  round(0.5 + score * 0.1, 2)
    elif score == 0:
        signal, conf = "SELL", 0.55
    else:
        signal, conf = "HOLD", 0.40

    return PortfolioSignal(
        signal=signal,
        confidence=conf,
        bull_case=f"Sentiment={news.sentiment_label if news else 'N/A'}, MACD={tech.macd_signal if tech else 'N/A'}",
        bear_case="Rule-based fallback — no LLM key set.",
        resolution=f"Score {score}/3 → {signal}",
    )


def portfolio_manager_node(state: AgentState) -> dict:
    risk = state.get("risk_decision")

    # Hard veto short-circuit
    if risk and risk.decision == "VETOED":
        signal = PortfolioSignal(
            signal="HOLD", confidence=0.0,
            bull_case="Trade vetoed by Risk Manager before synthesis.",
            bear_case=risk.reason,
            resolution="Risk Manager veto is final.",
        )
        return _result(signal)

    # Try LLM synthesis
    if os.getenv("GROQ_API_KEY") or os.getenv("AWS_ACCESS_KEY_ID"):
        try:
            signal = _llm_synthesis(state)
        except Exception as e:
            print(f"[Portfolio Manager] LLM failed, falling back to rules: {e}")
            signal = _rule_based_signal(state)
    else:
        signal = _rule_based_signal(state)

    return _result(signal)


def _llm_synthesis(state: AgentState) -> PortfolioSignal:
    import json
    from agent.tools.llm_client import get_llm

    news  = state.get("news_analyst")
    tech  = state.get("technical_analyst")
    macro = state.get("macro_context")
    risk  = state.get("risk_decision")

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human",  ANALYSIS_TEMPLATE),
    ])

    chain = prompt | get_llm()
    resp  = chain.invoke({
        "ticker":           state["ticker"],
        "sentiment_label":  news.sentiment_label  if news  else "N/A",
        "sentiment_score":  news.sentiment_score  if news  else 0.5,
        "headline_count":   news.headline_count   if news  else 0,
        "sec_context":      (news.sec_context[:200] if news and news.sec_context else "N/A"),
        "rsi":              tech.rsi               if tech  else "N/A",
        "macd_signal":      tech.macd_signal       if tech  else "N/A",
        "bollinger_position": tech.bollinger_position if tech else "N/A",
        "regime":           tech.regime            if tech  else "N/A",
        "chart_pattern":    tech.chart_pattern     if tech  else "N/A",
        "vix":              macro.vix              if macro else "N/A",
        "yield_10yr":       macro.yield_10yr       if macro else "N/A",
        "fed_stance":       macro.fed_stance       if macro else "N/A",
        "risk_environment": macro.risk_environment if macro else "N/A",
        "risk_decision":    risk.decision          if risk  else "N/A",
        "adjusted_size":    risk.adjusted_size     if risk  else 0,
        "stop_loss_price":  risk.stop_loss_price   if risk  else 0.0,
    })

    raw  = resp.content.strip()
    # Extract JSON block if LLM wraps it in markdown
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


def _result(signal: PortfolioSignal) -> dict:
    return {
        "portfolio_signal": signal,
        "messages": [AIMessage(
            content=f"[Portfolio Manager] {signal.signal} | "
                    f"confidence={signal.confidence:.2f} | "
                    f"{signal.resolution[:80]}"
        )],
    }
