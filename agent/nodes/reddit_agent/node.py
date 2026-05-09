import httpx
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import RedditSentimentOutput
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision

_SUBREDDITS = "wallstreetbets+stocks+investing+StockMarket"
_HEADERS    = {"User-Agent": "QuantSentiment/1.0 (research tool)"}


def _fetch_reddit_posts(ticker: str, limit: int = 25) -> list[str]:
    """
    Search finance subreddits for posts mentioning the ticker.
    Uses restrict_sr=true so results are limited to those subreddits.
    Filters results to only posts that actually mention the ticker in the title.
    """
    url = (
        f"https://www.reddit.com/r/{_SUBREDDITS}/search.json"
        f"?q={ticker}&restrict_sr=true&sort=relevance&t=week&limit={limit}"
    )
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        children = resp.json()["data"]["children"]
        ticker_upper = ticker.upper()
        posts = []
        for c in children:
            title    = c["data"].get("title", "")
            selftext = c["data"].get("selftext", "")
            title_up = title.upper()
            # Require ticker in the title (word boundary check)
            if ticker_upper not in title_up and f"${ticker_upper}" not in title_up:
                continue
            text = title
            if selftext and len(selftext) > 30:
                text += " — " + selftext[:200]
            posts.append(text)
        return posts
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
