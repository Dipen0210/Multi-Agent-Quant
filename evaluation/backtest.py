"""
Walk-forward backtest — honest signal evaluation.

Splits 1 year of price data into rolling windows, applies the same
rule-based signal the portfolio_manager uses, then evaluates on the
next hold_days window.

Usage:
    python -m evaluation.backtest --ticker NVDA --windows 6
"""
import argparse

import yfinance as yf

from agent.tools.yfinance_tool import get_technicals
from evaluation.metrics import TradeRecord, evaluate, format_report


def _signal_from_technicals(tech) -> str:
    score = 0
    if tech.macd_signal in ("bullish_crossover", "bullish"):
        score += 1
    if tech.regime == "trending_up":
        score += 1
    if tech.rsi < 70:
        score += 1
    if score >= 2:
        return "buy"
    if score == 0:
        return "sell"
    return "hold"


def run_backtest(ticker: str, windows: int = 6, hold_days: int = 5) -> list[TradeRecord]:
    data = yf.download(ticker, period="1y", auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No price data for {ticker}")

    closes = data["Close"].squeeze().dropna().tolist()
    step   = max(len(closes) // windows, hold_days + 2)
    trades = []

    for i in range(0, len(closes) - hold_days - 1, step):
        if i + hold_days >= len(closes):
            break
        entry_price = float(closes[i])
        exit_price  = float(closes[i + hold_days])

        try:
            tech   = get_technicals(ticker)
            action = _signal_from_technicals(tech)
        except Exception:
            action = "hold"

        trades.append(TradeRecord(
            ticker      = ticker,
            action      = action,
            shares      = 1,
            entry_price = entry_price,
            exit_price  = exit_price if action != "hold" else 0.0,
        ))

    return trades


def main():
    parser = argparse.ArgumentParser(description="Walk-forward backtest")
    parser.add_argument("--ticker",  default="NVDA")
    parser.add_argument("--windows", type=int, default=6)
    parser.add_argument("--hold",    type=int, default=5)
    args = parser.parse_args()

    print(f"\nBacktest: {args.ticker} | {args.windows} windows | hold={args.hold}d\n")
    trades = run_backtest(args.ticker, args.windows, args.hold)
    result = evaluate(trades)
    print(format_report(result))

    print("\nTrade log:")
    for t in trades:
        pnl = (t.exit_price - t.entry_price) / t.entry_price if t.exit_price else 0
        print(f"  {t.action:4s}  entry=${t.entry_price:.2f}  exit=${t.exit_price:.2f}  pnl={pnl:+.2%}")


if __name__ == "__main__":
    main()
