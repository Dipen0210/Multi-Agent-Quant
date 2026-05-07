import yfinance as yf
import pandas as pd
import numpy as np
from agent.schemas import TechnicalAnalystOutput, MacroContextOutput


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def _macd(close: pd.Series) -> dict:
    ema12    = _ema(close, 12)
    ema26    = _ema(close, 26)
    macd_line   = ema12 - ema26
    signal_line = _ema(macd_line, 9)
    hist        = macd_line - signal_line

    last_macd   = float(macd_line.iloc[-1])
    last_signal = float(signal_line.iloc[-1])
    prev_macd   = float(macd_line.iloc[-2])
    prev_signal = float(signal_line.iloc[-2])

    if prev_macd <= prev_signal and last_macd > last_signal:
        label = "bullish_crossover"
    elif prev_macd >= prev_signal and last_macd < last_signal:
        label = "bearish_crossover"
    elif last_macd > last_signal:
        label = "bullish"
    else:
        label = "bearish"

    return {"macd": round(last_macd, 4), "signal": round(last_signal, 4),
            "histogram": round(float(hist.iloc[-1]), 4), "label": label}


def _bollinger(close: pd.Series, period: int = 20) -> dict:
    sma  = close.rolling(period).mean()
    std  = close.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    price = float(close.iloc[-1])

    if price > float(upper.iloc[-1]):
        position = "above_upper"
    elif price < float(lower.iloc[-1]):
        position = "below_lower"
    else:
        position = "mid_band"

    return {"upper": round(float(upper.iloc[-1]), 2),
            "lower": round(float(lower.iloc[-1]), 2),
            "position": position}


def _regime(close: pd.Series) -> str:
    returns    = close.pct_change().dropna()
    volatility = float(returns.std()) * (252 ** 0.5)
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    price = float(close.iloc[-1])

    if volatility > 0.40:
        return "volatile"
    if price > sma20 > sma50:
        return "trending_up"
    if price < sma20 < sma50:
        return "trending_down"
    return "ranging"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_technicals(ticker: str) -> TechnicalAnalystOutput:
    """Compute RSI, MACD, Bollinger Bands and regime for a ticker."""
    hist  = yf.Ticker(ticker).history(period="1y")
    close = hist["Close"].dropna()

    rsi_val  = _rsi(close)
    macd_d   = _macd(close)
    boll_d   = _bollinger(close)
    regime   = _regime(close)

    return TechnicalAnalystOutput(
        rsi=rsi_val,
        macd_signal=macd_d["label"],
        bollinger_position=boll_d["position"],
        regime=regime,
    )


def get_current_price(ticker: str) -> float:
    """Return latest closing price."""
    hist = yf.Ticker(ticker).history(period="1d")
    return round(float(hist["Close"].iloc[-1]), 2)


def get_macro_data() -> MacroContextOutput:
    """Pull VIX and 10-year treasury yield as macro context."""
    vix_data   = yf.Ticker("^VIX").history(period="1d")
    tnx_data   = yf.Ticker("^TNX").history(period="1d")

    vix   = round(float(vix_data["Close"].iloc[-1]), 2)
    yield_ = round(float(tnx_data["Close"].iloc[-1]), 2)

    # Simple heuristics
    risk_env    = "risk_off" if vix > 25 else ("risk_on" if vix < 18 else "neutral")
    fed_stance  = "hawkish" if yield_ > 4.5 else ("dovish" if yield_ < 3.5 else "neutral")
    favorable   = risk_env == "risk_on" and fed_stance != "hawkish"

    return MacroContextOutput(
        vix=vix,
        yield_10yr=yield_,
        fed_stance=fed_stance,
        risk_environment=risk_env,
        favorable_for_sector=favorable,
        summary=f"VIX={vix} ({risk_env}), 10yr yield={yield_}% ({fed_stance})",
    )
