from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import FinancialNewsOutput
from agent.tools.tavily_tool import fetch_news, extract_headlines
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label


def financial_news_node(state: AgentState) -> dict:
    ticker = state["ticker"]

    try:
        articles = fetch_news(ticker, days=1)
    except Exception:
        articles = []

    headlines, urls = extract_headlines(articles)

    # Use full article body when available, fall back to title only
    texts_to_score = []
    for a in articles:
        body = a.get("content", "").strip()
        texts_to_score.append(body if body else a.get("title", ""))
    texts_to_score = [t for t in texts_to_score if t]

    raw = score_headlines(texts_to_score) if texts_to_score else {
        "aggregate": {"label": "neutral", "score": 0.5, "headline_count": 0}
    }
    agg   = raw["aggregate"]
    score = agg["score"]
    label = agg["label"]
    count = len(texts_to_score)

    keywords = extract_keywords(texts_to_score)
    decision = score_to_decision(score)
    reasoning = (
        f"{count} articles (full body) scored via FinBERT. "
        f"Top keywords: {', '.join(keywords) if keywords else 'none'}. "
        f"Majority tone is {label}."
    )

    output = FinancialNewsOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        headline_count  = count,
        headlines       = headlines[:10],
        article_urls    = urls[:10],
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "financial_news": output,
        "sources":        state.get("sources", []) + urls,
        "messages": [AIMessage(
            content=f"[Financial News] {count} articles → {decision} ({score:.2f}) | keywords: {', '.join(keywords[:3])}"
        )],
    }
