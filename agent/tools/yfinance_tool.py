import yfinance as yf
import pandas as pd
from agent.schemas import MacroContextOutput


def get_current_price(ticker: str) -> float:
    """Return latest closing price for a ticker."""
    hist = yf.Ticker(ticker).history(period="2d")
    return round(float(hist["Close"].dropna().iloc[-1]), 2)


def get_market_indices() -> dict:
    """
    Fetch VIX, 10-year yield, SPY 5-day return, and DXY.
    Returns a plain dict of floats so Risk Manager and Macro Agent can both use it.
    """
    try:
        vix_hist = yf.Ticker("^VIX").history(period="2d")
        vix = round(float(vix_hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        vix = 20.0

    try:
        tnx_hist = yf.Ticker("^TNX").history(period="2d")
        yield_10yr = round(float(tnx_hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        yield_10yr = 4.3

    try:
        spy_hist = yf.Ticker("SPY").history(period="10d")
        spy_close = spy_hist["Close"].dropna()
        # 5-day return: compare latest to 5 trading days ago
        spy_5d_return = round(
            (float(spy_close.iloc[-1]) - float(spy_close.iloc[-6])) / float(spy_close.iloc[-6]), 4
        ) if len(spy_close) >= 6 else 0.0
    except Exception:
        spy_5d_return = 0.0

    try:
        dxy_hist = yf.Ticker("DX-Y.NYB").history(period="2d")
        dxy = round(float(dxy_hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        dxy = 104.0

    return {
        "vix": vix,
        "yield_10yr": yield_10yr,
        "spy_5d_return": spy_5d_return,
        "dxy": dxy,
    }
