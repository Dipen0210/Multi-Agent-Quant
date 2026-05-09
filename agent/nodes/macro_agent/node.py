from datetime import datetime
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import MacroContextOutput
from agent.tools.yfinance_tool import get_market_indices
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_label
from agent.tools.pinecone_tool import (
    save_macro_snapshot,
    fetch_macro_trend,
    compute_vix_trend,
    compute_consecutive_risk_off,
)

_GLOBAL_NEWS_QUERIES = [
    "global stock market news today",
    "macroeconomic news today",
    "Federal Reserve interest rates news today",
]


def _fetch_global_headlines() -> tuple[list[str], list[str]]:
    """Fetch global market headlines via Tavily. Returns (headlines, urls)."""
    try:
        from agent.tools.tavily_tool import fetch_news, extract_headlines
        headlines, urls = [], []
        for query_term in _GLOBAL_NEWS_QUERIES:
            articles = fetch_news(query_term, days=1)
            h, u = extract_headlines(articles)
            headlines.extend(h)
            urls.extend(u)
        # Deduplicate headlines while keeping url alignment
        seen: set[str] = set()
        unique_h, unique_u = [], []
        for h, u in zip(headlines, urls):
            if h not in seen:
                seen.add(h)
                unique_h.append(h)
                unique_u.append(u)
        return unique_h[:15], unique_u[:15]
    except Exception:
        return [], []


def _derive_labels(indices: dict) -> tuple[str, str, str]:
    """Return (fed_stance, risk_environment, market_trend) from index values."""
    vix = indices["vix"]
    yield_10yr = indices["yield_10yr"]
    spy_5d = indices["spy_5d_return"]

    risk_env = "risk_off" if vix > 25 else ("risk_on" if vix < 18 else "neutral")
    fed_stance = "hawkish" if yield_10yr > 4.5 else ("dovish" if yield_10yr < 3.5 else "neutral")
    market_trend = "bullish" if spy_5d > 0.01 else ("bearish" if spy_5d < -0.01 else "neutral")

    return fed_stance, risk_env, market_trend


def macro_agent_node(state: AgentState) -> dict:
    # ── 1. Fetch market indices ────────────────────────────────────────────────
    indices = get_market_indices()
    fed_stance, risk_env, market_trend = _derive_labels(indices)

    # ── 2. Fetch and score global news headlines ───────────────────────────────
    headlines, news_urls = _fetch_global_headlines()
    if headlines:
        raw = score_headlines(headlines)
        agg = raw["aggregate"]
        sentiment_score = agg["score"]
        sentiment_label = agg["label"]
        keywords = extract_keywords(headlines, n=8)
    else:
        sentiment_score = 0.5
        sentiment_label = "neutral"
        keywords = []

    # ── 3. Pinecone: fetch trend, then save today's snapshot ──────────────────
    history = fetch_macro_trend(days=14)
    vix_trend = compute_vix_trend(history)
    consec_risk_off = compute_consecutive_risk_off(history)

    snapshot_meta = {
        "vix":             indices["vix"],
        "yield_10yr":      indices["yield_10yr"],
        "spy_5d_return":   indices["spy_5d_return"],
        "dxy":             indices["dxy"],
        "risk_environment": risk_env,
        "sentiment_score": sentiment_score,
    }
    summary_str = (
        f"VIX={indices['vix']} ({risk_env}), "
        f"SPY 5d={indices['spy_5d_return']:.1%} ({market_trend}), "
        f"yield={indices['yield_10yr']}% ({fed_stance}), "
        f"DXY={indices['dxy']}, "
        f"global sentiment={sentiment_label} ({sentiment_score:.2f})"
    )
    save_macro_snapshot(summary_str, snapshot_meta)

    # ── 4. Build reasoning narrative (for Portfolio Manager) ──────────────────
    reasoning = (
        f"{len(headlines)} global market headlines scored via FinBERT. "
        f"Global news sentiment is {sentiment_label}. "
        f"Key macro themes: {', '.join(keywords[:5]) if keywords else 'none'}. "
        f"VIX trend is {vix_trend}"
        + (f" with {consec_risk_off} consecutive risk-off days." if consec_risk_off > 0 else ".")
    )

    output = MacroContextOutput(
        vix=indices["vix"],
        yield_10yr=indices["yield_10yr"],
        spy_5d_return=indices["spy_5d_return"],
        dxy=indices["dxy"],
        fed_stance=fed_stance,
        risk_environment=risk_env,
        market_trend=market_trend,
        sentiment_score=sentiment_score,
        sentiment_label=sentiment_label,
        global_news_keywords=keywords,
        global_news_urls=news_urls,
        headline_count=len(headlines),
        vix_trend=vix_trend,
        consecutive_risk_off_days=consec_risk_off,
        summary=summary_str,
        reasoning=reasoning,
    )

    return {
        "macro_context": output,
        "messages": [AIMessage(
            content=(
                f"[Macro Agent] VIX={indices['vix']} ({vix_trend}) | "
                f"SPY 5d={indices['spy_5d_return']:.1%} ({market_trend}) | "
                f"Global news: {sentiment_label} ({sentiment_score:.2f}) | "
                f"keywords: {', '.join(keywords[:3])}"
            )
        )],
    }
