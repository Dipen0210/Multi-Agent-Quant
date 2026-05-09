"""
QuantSentiment MCP Server — FastMCP edition (MCP SDK 1.x)

Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "quantsentiment": {
          "command": "/Users/dipen/Projects/QuantSentiment/venv/bin/python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/Users/dipen/Projects/QuantSentiment",
          "env": { "API_BASE_URL": "http://localhost:8000" }
        }
      }
    }
"""
from mcp.server.fastmcp import FastMCP
import mcp_server.tools as qt

mcp = FastMCP("quantsentiment")


@mcp.tool()
def analyze_ticker(ticker: str, days: int = 2) -> str:
    """
    Run the full 6-agent QuantSentiment analysis on a stock ticker.
    Returns signal (BUY/SELL/HOLD), confidence, and full reasoning from
    News Analyst, Technical Analyst, Macro Context, Risk Manager,
    Portfolio Manager, and Critic agents.

    Args:
        ticker: Stock symbol e.g. NVDA, AAPL, TSLA, NFLX
        days:   Lookback window for news in days (1-7, default 2)
    """
    return qt.analyze_ticker(ticker, days)


@mcp.tool()
def get_portfolio() -> str:
    """
    Return current Alpaca paper trading positions and account P&L.
    Shows live account balance, open positions, and unrealised gains.
    """
    return qt.get_portfolio()


@mcp.tool()
def get_analytics(period: str = "1M") -> str:
    """
    Return portfolio analytics from Alpaca paper trading.
    Shows equity history, open positions, trade history, win rate and total return.

    Args:
        period: '1W', '1M', or '3M' (default 1M)
    """
    return qt.get_analytics(period)


@mcp.tool()
def health_check() -> str:
    """Check whether the QuantSentiment API server is running."""
    return qt.health_check()


if __name__ == "__main__":
    mcp.run(transport="stdio")
