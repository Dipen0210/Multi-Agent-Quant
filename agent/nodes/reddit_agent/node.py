import httpx
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import RedditSentimentOutput
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision

_SUBREDDITS = "wallstreetbets+stocks+investing+StockMarket"
_HEADERS    = {"User-Agent": "QuantSentiment/1.0 (research tool)"}


def _fetch_reddit_posts(ticker: str, limit: int = 20) -> list[str]:
    url = (
        f"https://www.reddit.com/search.json"
        f"?q={ticker}&subreddit={_SUBREDDITS}"
        f"&sort=new&t=week&limit={limit}"
    )
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
        return [c["data"]["title"] for c in children if c["data"].get("title")]
    except Exception:
        return []


def reddit_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    posts  = _fetch_reddit_posts(ticker)

    raw = score_headlines(posts) if posts else {
        "aggregate": {"label": "neutral", "score": 0.5, "headline_count": 0}
    }
    agg      = raw["aggregate"]
    score    = agg["score"]
    label    = agg["label"]
    keywords = extract_keywords(posts)
    decision = score_to_decision(score)
    reasoning = (
        f"{len(posts)} Reddit posts from r/wallstreetbets, r/stocks, r/investing. "
        f"Community sentiment is {label}. "
        f"Hot topics: {', '.join(keywords) if keywords else 'none'}."
    )

    output = RedditSentimentOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        post_count      = len(posts),
        top_posts       = posts[:5],
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "reddit_sentiment": output,
        "messages": [AIMessage(
            content=f"[Reddit] {len(posts)} posts → {decision} ({score:.2f}) | topics: {', '.join(keywords[:3])}"
        )],
    }
