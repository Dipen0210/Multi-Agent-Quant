import os
import math
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import RiskDecision
from agent.tools.yfinance_tool import get_current_price

MAX_SINGLE_STOCK_PCT = float(os.getenv("RISK_MAX_SINGLE_STOCK_PCT", "0.10"))
STOP_LOSS_PCT        = float(os.getenv("RISK_STOP_LOSS_PCT",        "0.05"))
DEFAULT_PORTFOLIO    = 100_000.0

# Hard veto thresholds — "is it safe to trade today?"
VIX_VETO_THRESHOLD   = 35.0    # market in panic
SPY_CRASH_THRESHOLD  = -0.05   # SPY down more than 5% in 5 days
DXY_SURGE_THRESHOLD  = 108.0   # very strong dollar = global headwind


def _get_portfolio_value() -> float:
    try:
        from agent.tools.alpaca_tool import get_account
        acct = get_account()
        return acct["portfolio_value"]
    except Exception:
        return DEFAULT_PORTFOLIO


def _get_exposure(ticker: str) -> float:
    try:
        from agent.tools.alpaca_tool import get_portfolio_exposure
        return get_portfolio_exposure(ticker)
    except Exception:
        return 0.0


def _macro_safety_scale(macro) -> float:
    """
    0.5 – 1.0 scale factor based on how safe the market environment is today.
    This scales DOWN position size when markets are risky.
    """
    if macro is None:
        return 0.75

    scale = 1.0
    if macro.risk_environment == "risk_off":
        scale -= 0.15
    if macro.market_trend == "bearish":
        scale -= 0.10
    if macro.vix_trend == "rising":
        scale -= 0.10
    if macro.vix > 20:
        scale -= 0.05
    if macro.consecutive_risk_off_days >= 3:
        scale -= 0.10

    return round(max(0.5, scale), 2)


def risk_manager_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    macro  = state.get("macro_context")
    flags: list[str] = []

    # ── Hard veto checks: is it safe to trade today? ──────────────────────────
    if macro:
        if macro.vix >= VIX_VETO_THRESHOLD:
            return _veto(ticker, f"VIX={macro.vix} — market in panic mode (threshold {VIX_VETO_THRESHOLD})", flags)

        if macro.spy_5d_return <= SPY_CRASH_THRESHOLD:
            return _veto(
                ticker,
                f"SPY 5-day return={macro.spy_5d_return:.1%} — market crashing (threshold {SPY_CRASH_THRESHOLD:.0%})",
                flags,
            )

        if macro.dxy >= DXY_SURGE_THRESHOLD:
            flags.append(f"DXY={macro.dxy} — strong dollar headwind for equities")

        if macro.vix_trend == "rising" and macro.vix > 22:
            flags.append(f"VIX rising trend at {macro.vix} — uncertainty increasing")

        if macro.risk_environment == "risk_off":
            flags.append(f"Risk-off environment (VIX={macro.vix})")

        if macro.market_trend == "bearish":
            flags.append(f"SPY 5d={macro.spy_5d_return:.1%} — broad market in decline")

        if macro.consecutive_risk_off_days >= 3:
            flags.append(f"{macro.consecutive_risk_off_days} consecutive risk-off days")

    # ── Portfolio exposure check ───────────────────────────────────────────────
    exposure = _get_exposure(ticker)
    if exposure >= MAX_SINGLE_STOCK_PCT:
        return _veto(
            ticker,
            f"Already {exposure*100:.1f}% portfolio in {ticker} (max {MAX_SINGLE_STOCK_PCT*100:.0f}%)",
            flags,
        )

    # ── Position sizing ────────────────────────────────────────────────────────
    portfolio_val   = _get_portfolio_value()
    price           = get_current_price(ticker)
    max_position_val = portfolio_val * MAX_SINGLE_STOCK_PCT
    raw_shares      = math.floor(max_position_val / price) if price > 0 else 0

    # Scale by market safety — not by stock sentiment
    safety_scale    = _macro_safety_scale(macro)
    adjusted_shares = max(1, math.floor(raw_shares * safety_scale))
    stop_loss_price = round(price * (1 - STOP_LOSS_PCT), 2)

    vix_str  = f"VIX={macro.vix}" if macro else "VIX=N/A"
    spy_str  = f"SPY 5d={macro.spy_5d_return:.1%}" if macro else "SPY=N/A"
    env_str  = macro.risk_environment if macro else "unknown"

    reason = (
        f"Market safe to trade. {vix_str} ({env_str}) | {spy_str} | "
        f"Safety scale={safety_scale:.2f} | "
        f"Position: {adjusted_shares} shares @ ${price} | Stop ${stop_loss_price}"
    )

    decision = RiskDecision(
        decision="APPROVED",
        original_size=raw_shares,
        adjusted_size=adjusted_shares,
        stop_loss_pct=STOP_LOSS_PCT,
        stop_loss_price=stop_loss_price,
        reason=reason,
        market_safety_flags=flags,
    )
    return _result(decision)


def _veto(ticker: str, reason: str, flags: list[str]) -> dict:
    decision = RiskDecision(
        decision="VETOED",
        original_size=0,
        adjusted_size=0,
        stop_loss_pct=STOP_LOSS_PCT,
        stop_loss_price=0.0,
        reason=reason,
        market_safety_flags=flags,
    )
    return _result(decision)


def _result(decision: RiskDecision) -> dict:
    icon = "✓ APPROVED" if decision.decision == "APPROVED" else "✗ VETOED"
    return {
        "risk_decision": decision,
        "messages": [AIMessage(
            content=f"[Risk Manager] {icon} | {decision.reason[:100]}"
        )],
    }
