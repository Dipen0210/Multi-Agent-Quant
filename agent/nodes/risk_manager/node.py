import os
import math
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import RiskDecision
from agent.tools.yfinance_tool import get_current_price

MAX_SINGLE_STOCK_PCT = float(os.getenv("RISK_MAX_SINGLE_STOCK_PCT", "0.10"))
STOP_LOSS_PCT        = float(os.getenv("RISK_STOP_LOSS_PCT",        "0.05"))
DEFAULT_PORTFOLIO    = 100_000.0   # fallback when Alpaca key not set
VIX_VETO_THRESHOLD  = 35.0


def _get_portfolio_value() -> tuple[float, float]:
    """
    Returns (portfolio_value, current_exposure_fraction) for the ticker.
    Falls back to defaults if Alpaca not configured.
    """
    try:
        from agent.tools.alpaca_tool import get_account
        acct = get_account()
        return acct["portfolio_value"], 0.0
    except Exception:
        return DEFAULT_PORTFOLIO, 0.0


def _get_exposure(ticker: str) -> float:
    try:
        from agent.tools.alpaca_tool import get_portfolio_exposure
        return get_portfolio_exposure(ticker)
    except Exception:
        return 0.0


def risk_manager_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    macro  = state.get("macro_context")
    news   = state.get("news_analyst")

    # ── Hard veto checks ──────────────────────────────────────────────────────
    if macro and macro.vix >= VIX_VETO_THRESHOLD:
        decision = _veto(
            ticker, f"VIX={macro.vix} exceeds veto threshold of {VIX_VETO_THRESHOLD}"
        )
        return _result(decision)

    exposure = _get_exposure(ticker)
    if exposure >= MAX_SINGLE_STOCK_PCT:
        decision = _veto(
            ticker,
            f"Already {exposure*100:.1f}% exposure in {ticker} "
            f"(max {MAX_SINGLE_STOCK_PCT*100:.0f}%)"
        )
        return _result(decision)

    # ── Position sizing ───────────────────────────────────────────────────────
    portfolio_val, _ = _get_portfolio_value()
    price            = get_current_price(ticker)

    max_position_val = portfolio_val * MAX_SINGLE_STOCK_PCT
    raw_shares       = math.floor(max_position_val / price) if price > 0 else 0

    # Scale down if sentiment is weak
    sentiment_score  = news.sentiment_score if news else 0.5
    scale_factor     = _confidence_scale(sentiment_score)
    adjusted_shares  = max(1, math.floor(raw_shares * scale_factor))

    stop_loss_price  = round(price * (1 - STOP_LOSS_PCT), 2)

    reason = (
        f"Portfolio ${portfolio_val:,.0f} | "
        f"Max position ${max_position_val:,.0f} | "
        f"Price ${price} | "
        f"Scale {scale_factor:.2f} (sentiment {sentiment_score:.2f})"
    )

    decision = RiskDecision(
        decision="APPROVED",
        original_size=raw_shares,
        adjusted_size=adjusted_shares,
        stop_loss_pct=STOP_LOSS_PCT,
        stop_loss_price=stop_loss_price,
        reason=reason,
    )
    return _result(decision)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _confidence_scale(sentiment_score: float) -> float:
    """Map sentiment score to a position scale factor (0.5 – 1.0)."""
    return round(0.5 + 0.5 * min(max(sentiment_score, 0.0), 1.0), 2)


def _veto(ticker: str, reason: str) -> RiskDecision:
    return RiskDecision(
        decision="VETOED",
        original_size=0,
        adjusted_size=0,
        stop_loss_pct=STOP_LOSS_PCT,
        stop_loss_price=0.0,
        reason=reason,
    )


def _result(decision: RiskDecision) -> dict:
    icon = "✓ APPROVED" if decision.decision == "APPROVED" else "✗ VETOED"
    return {
        "risk_decision": decision,
        "messages": [AIMessage(
            content=f"[Risk Manager] {icon} | size={decision.adjusted_size} | {decision.reason[:80]}"
        )],
    }
