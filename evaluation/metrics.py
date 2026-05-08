"""
Honest evaluation metrics — no inflated return claims.
Computes Sharpe ratio, max drawdown, and win rate from a trade log.
"""
import math
from typing import NamedTuple


class TradeRecord(NamedTuple):
    ticker:      str
    action:      str    # "buy" | "sell" | "hold"
    shares:      int
    entry_price: float
    exit_price:  float  # 0.0 if position still open


class EvalResult(NamedTuple):
    total_trades:         int
    win_rate:             float   # fraction of closed trades with positive P&L
    sharpe_ratio:         float   # annualised, assuming daily returns
    max_drawdown:         float   # peak-to-trough as a fraction (negative)
    total_return:         float   # fraction (e.g. 0.05 = 5%)
    avg_return_per_trade: float


def _pnl(t: TradeRecord) -> float:
    if t.exit_price == 0.0 or t.action == "hold":
        return 0.0
    direction = 1 if t.action == "buy" else -1
    return direction * (t.exit_price - t.entry_price) / t.entry_price


def sharpe_ratio(returns: list[float], risk_free: float = 0.0) -> float:
    if len(returns) < 2:
        return 0.0
    n    = len(returns)
    mean = sum(returns) / n
    var  = sum((r - mean) ** 2 for r in returns) / (n - 1)
    std  = math.sqrt(var) if var > 0 else 0.0
    if std == 0:
        return 0.0
    return ((mean - risk_free) / std) * math.sqrt(252 / max(n, 1))


def max_drawdown(returns: list[float]) -> float:
    cumulative = [1.0]
    for r in returns:
        cumulative.append(cumulative[-1] * (1 + r))
    peak = cumulative[0]
    mdd  = 0.0
    for v in cumulative:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < mdd:
            mdd = dd
    return mdd


def evaluate(trades: list[TradeRecord]) -> EvalResult:
    closed = [t for t in trades if t.exit_price > 0 and t.action != "hold"]
    if not closed:
        return EvalResult(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    returns = [_pnl(t) for t in closed]
    wins    = sum(1 for r in returns if r > 0)

    return EvalResult(
        total_trades         = len(closed),
        win_rate             = wins / len(closed),
        sharpe_ratio         = sharpe_ratio(returns),
        max_drawdown         = max_drawdown(returns),
        total_return         = sum(returns),
        avg_return_per_trade = sum(returns) / len(returns),
    )


def format_report(result: EvalResult) -> str:
    lines = [
        "── Evaluation Metrics ──────────────────────",
        f"  Trades evaluated : {result.total_trades}",
        f"  Win rate         : {result.win_rate:.1%}",
        f"  Sharpe ratio     : {result.sharpe_ratio:.2f}",
        f"  Max drawdown     : {result.max_drawdown:.1%}",
        f"  Total return     : {result.total_return:.2%}",
        f"  Avg / trade      : {result.avg_return_per_trade:.2%}",
        "────────────────────────────────────────────",
        "  NOTE: paper trading only — no real capital",
    ]
    return "\n".join(lines)
