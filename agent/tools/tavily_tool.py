import os
from datetime import datetime
from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential

_client = None

# Domains that return price/quote pages instead of actual news articles
_EXCLUDE_DOMAINS = [
    "finance.yahoo.com/quote",
    "marketwatch.com/investing/stock",
    "moomoo.com",
    "youtube.com",
    "wisesheets.io",
    "stockanalysis.com/stocks",
    "macrotrends.net",
    "tradingview.com",
    "barchart.com",
    "finviz.com",
]


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _client


def _is_news_article(result: dict) -> bool:
    """Filter out price/quote pages — keep only actual news articles."""
    url = result.get("url", "").lower()
    title = result.get("title", "").lower()
    # Skip obvious quote/price pages
    if any(d in url for d in _EXCLUDE_DOMAINS):
        return False
    # Skip titles that are just ticker price pages
    skip_phrases = ["stock price", "stock quote", "share price", "quote & history",
                    "quote, news, and history", "financial reports"]
    if any(p in title for p in skip_phrases):
        return False
    # Must have meaningful content
    if len(result.get("content", "")) < 100:
        return False
    return True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def fetch_news(ticker: str, days: int = 1) -> list[dict]:
    """
    Fetch today's actual news articles for a ticker.
    Filters out price/quote pages and unrelated articles.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    results = _get_client().search(
        query=f'"{ticker}" stock news earnings {today}',
        search_depth="advanced",
        max_results=15,
        include_answer=False,
        days=days,
    )
    ticker_upper = ticker.upper()
    articles = []
    for r in results.get("results", []):
        if not _is_news_article(r):
            continue
        # Must mention the ticker in title or content
        combined = (r.get("title", "") + " " + r.get("content", "")).upper()
        if ticker_upper not in combined:
            continue
        articles.append({
            "title":          r.get("title", ""),
            "url":            r.get("url", ""),
            "content":        r.get("content", ""),
            "published_date": r.get("published_date", today),
        })
    return articles[:10]


def extract_headlines(articles: list[dict]) -> tuple[list[str], list[str]]:
    """Split articles into (headlines, sources)."""
    headlines = [a["title"] for a in articles if a["title"]]
    sources   = [a["url"]   for a in articles if a["url"]]
    return headlines, sources
