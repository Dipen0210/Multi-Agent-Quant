"""Legacy read-only market adapter; missing inputs are errors, never invented prices."""
import math
import yfinance as yf


def _closes(ticker: str, period: str, minimum: int = 1):
    values = yf.Ticker(ticker).history(period=period)["Close"].dropna()
    if len(values) < minimum or any(not math.isfinite(float(v)) or v <= 0 for v in values):
        raise ValueError(f"Insufficient or invalid market observations for {ticker}")
    return values


def get_current_price(ticker: str) -> float:
    return round(float(_closes(ticker, "2d").iloc[-1]), 2)


def get_market_indices() -> dict:
    spy = _closes("SPY", "10d", 6)
    return {
        "vix": float(_closes("^VIX", "2d").iloc[-1]),
        "yield_10yr": float(_closes("^TNX", "2d").iloc[-1]),
        "spy_5d_return": float(spy.iloc[-1] / spy.iloc[-6] - 1),
        "dxy": float(_closes("DX-Y.NYB", "2d").iloc[-1]),
    }
