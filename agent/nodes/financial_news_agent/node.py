from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import FinancialNewsOutput
from agent.tools.tavily_tool import fetch_news, extract_headlines
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label


def financial_news_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    days   = state.get("days", 2)

    try:
        articles = fetch_news(ticker, days)
    except Exception:
        articles = []

    headlines, urls = extract_headlines(articles)

    raw = score_headlines(headlines) if headlines else {
        "aggregate": {"label": "neutral", "score": 0.5, "headline_count": 0}
    }
    agg   = raw["aggregate"]
    score = agg["score"]
    label = agg["label"]
    count = len(headlines)

    keywords = extract_keywords(headlines)
    decision = score_to_decision(score)
    reasoning = (
        f"{count} headlines scored via FinBERT. "
        f"Top keywords: {', '.join(keywords) if keywords else 'none'}. "
        f"Majority tone is {label}."
    )

    output = FinancialNewsOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        headline_count  = count,
        headlines       = headlines[:10],
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "financial_news": output,
        "sources":        state.get("sources", []) + urls,
        "messages": [AIMessage(
            content=f"[Financial News] {count} headlines → {decision} ({score:.2f}) | keywords: {', '.join(keywords[:3])}"
        )],
    }
