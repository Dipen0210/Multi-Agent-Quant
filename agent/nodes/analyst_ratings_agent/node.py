import yfinance as yf
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import AnalystRatingsOutput

_SCORE = {
    "strong_buy":   0.90,
    "buy":          0.72,
    "hold":         0.50,
    "underperform": 0.30,
    "sell":         0.15,
}
_DECISION = {
    "strong_buy":   "bullish",
    "buy":          "bullish",
    "hold":         "neutral",
    "underperform": "bearish",
    "sell":         "bearish",
}


def analyst_ratings_node(state: AgentState) -> dict:
    ticker = state["ticker"]

    try:
        info = yf.Ticker(ticker).info
    except Exception:
        info = {}

    rec           = info.get("recommendationKey", "hold").lower().replace(" ", "_")
    target_price  = float(info.get("targetMeanPrice")  or 0)
    current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
    analyst_count = int(info.get("numberOfAnalystOpinions") or 0)

    upside_pct = round((target_price - current_price) / current_price * 100, 1) if current_price > 0 else 0.0
    score      = _SCORE.get(rec, 0.5)
    decision   = _DECISION.get(rec, "neutral")

    keywords = [rec.replace("_", " ")]
    if upside_pct > 10:
        keywords.append("high upside potential")
    elif upside_pct < -5:
        keywords.append("downside risk")
    if analyst_count >= 20:
        keywords.append("high analyst coverage")

    reasoning = (
        f"{analyst_count} analysts rate {ticker} as '{rec.replace('_',' ')}'. "
        f"Mean price target ${target_price:.2f} vs current ${current_price:.2f} "
        f"({'+'if upside_pct>=0 else ''}{upside_pct:.1f}% upside)."
    )

    output = AnalystRatingsOutput(
        decision        = decision,
        recommendation  = rec,
        sentiment_score = score,
        target_price    = target_price,
        current_price   = current_price,
        upside_pct      = upside_pct,
        analyst_count   = analyst_count,
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "analyst_ratings": output,
        "messages": [AIMessage(
            content=f"[Analyst Ratings] {rec} | {analyst_count} analysts | target ${target_price:.2f} ({upside_pct:+.1f}%) → {decision}"
        )],
    }
