from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import NewsAggregatorOutput

_WEIGHTS = {
    "financial_news":   0.30,
    "reddit_sentiment": 0.20,
    "sec_filing":       0.30,
    "analyst_ratings":  0.20,
}


def _agreement(decisions: list[str]) -> str:
    n     = len(decisions)
    bulls = decisions.count("bullish")
    bears = decisions.count("bearish")
    if bulls == n:        return "all_bullish"
    if bears == n:        return "all_bearish"
    if bulls >= n * .75:  return "mostly_bullish"
    if bears >= n * .75:  return "mostly_bearish"
    return "mixed"


def sentiment_aggregator_node(state: AgentState) -> dict:
    fin     = state.get("financial_news")
    reddit  = state.get("reddit_sentiment")
    sec     = state.get("sec_filing")
    analyst = state.get("analyst_ratings")

    sources = {
        "financial_news":   fin,
        "reddit_sentiment": reddit,
        "sec_filing":       sec,
        "analyst_ratings":  analyst,
    }

    weighted_sum = sum(
        src.sentiment_score * _WEIGHTS[key]
        for key, src in sources.items() if src is not None
    )
    total_weight = sum(_WEIGHTS[k] for k, v in sources.items() if v is not None)
    agg_score    = round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.5

    if agg_score >= 0.62:   agg_label = "positive"
    elif agg_score <= 0.38: agg_label = "negative"
    else:                   agg_label = "neutral"

    decisions       = [s.decision for s in sources.values() if s is not None]
    source_agreement = _agreement(decisions)

    breakdown = {
        "financial_news":  fin.sentiment_score     if fin     else 0.5,
        "reddit":          reddit.sentiment_score   if reddit  else 0.5,
        "sec_filing":      sec.sentiment_score      if sec     else 0.5,
        "analyst_ratings": analyst.sentiment_score  if analyst else 0.5,
    }

    output = NewsAggregatorOutput(
        sentiment_label  = agg_label,
        sentiment_score  = agg_score,
        headline_count   = fin.headline_count if fin else 0,
        breakdown        = breakdown,
        headlines        = fin.headlines      if fin else [],
        sec_context      = " | ".join(sec.key_findings[:2]) if sec and sec.key_findings else "",
        financial_news   = fin,
        reddit           = reddit,
        sec_filing       = sec,
        analyst_ratings  = analyst,
        source_agreement = source_agreement,
    )

    score_parts = " | ".join(f"{k}: {v:.2f}" for k, v in breakdown.items())

    return {
        "news_analyst": output,
        "messages": [AIMessage(
            content=(
                f"[Sentiment Aggregator] {agg_label} ({agg_score:.2f}) | "
                f"agreement={source_agreement} | {score_parts}"
            )
        )],
    }
