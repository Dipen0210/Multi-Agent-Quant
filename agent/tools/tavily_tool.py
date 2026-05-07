import os
from datetime import datetime, timedelta
from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential

_client = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_news(ticker: str, days: int = 2) -> list[dict]:
    """
    Fetch recent news headlines for a ticker.
    Returns list of {title, url, content, published_date}.
    """
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    results = _get_client().search(
        query=f"{ticker} stock news earnings",
        search_depth="basic",
        max_results=10,
        include_answer=False,
    )
    articles = []
    for r in results.get("results", []):
        articles.append({
            "title":          r.get("title", ""),
            "url":            r.get("url", ""),
            "content":        r.get("content", ""),
            "published_date": r.get("published_date", since),
        })
    return articles


def extract_headlines(articles: list[dict]) -> tuple[list[str], list[str]]:
    """Split articles into (headlines, sources)."""
    headlines = [a["title"] for a in articles if a["title"]]
    sources   = [a["url"]   for a in articles if a["url"]]
    return headlines, sources
