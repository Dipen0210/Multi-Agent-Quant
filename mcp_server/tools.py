"""
MCP tool implementations — each function is exposed as an MCP tool.
The server calls these; they hit the local FastAPI endpoints.
"""
import os
import json
import httpx

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
_client = httpx.Client(timeout=120)


def analyze_ticker(ticker: str, days: int = 2) -> str:
    """
    Run the full 6-agent analysis on a stock ticker.
    Returns a JSON string with signal, confidence, and full agent reasoning.

    Args:
        ticker: Stock symbol, e.g. NVDA, AAPL, TSLA
        days:   Lookback window in days for news (1-7, default 2)
    """
    resp = _client.post(f"{BASE_URL}/ask", json={"ticker": ticker, "days": days})
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


def get_portfolio() -> str:
    """
    Return current Alpaca paper trading positions and P&L.
    Shows live account balance, open positions, and unrealised gains.
    """
    resp = _client.get(f"{BASE_URL}/portfolio")
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


def get_analytics(period: str = "1M") -> str:
    """
    Return portfolio analytics — equity history, open positions, trade history,
    win rate, total return, and Sharpe metrics from Alpaca paper trading.

    Args:
        period: Time period for equity chart — '1W', '1M', or '3M' (default '1M')
    """
    resp = _client.get(f"{BASE_URL}/analytics", params={"period": period})
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)


def health_check() -> str:
    """Check whether the QuantSentiment API server is running."""
    resp = _client.get(f"{BASE_URL}/health")
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2)
