import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.alpaca_tool import place_order, skip_trade
from agent.tools.yfinance_tool import get_current_price


def execution_node(state: AgentState) -> dict:
    critic   = state.get("critic_decision")
    risk     = state.get("risk_decision")
    portfolio = state.get("portfolio_signal")

    # Critic must have said PROCEED to reach this node (graph routing enforces it)
    # but we double-check defensively
    if not critic or critic.decision != "PROCEED":
        trade = skip_trade("Critic did not approve")
        return _result(trade)

    signal = portfolio.signal if portfolio else "HOLD"
    if signal not in ("BUY", "SELL"):
        trade = skip_trade(f"Signal is {signal} — no trade needed")
        return _result(trade)

    shares    = risk.adjusted_size    if risk else 0
    stop_loss = risk.stop_loss_price  if risk else 0.0

    if shares <= 0:
        trade = skip_trade("Position size is 0 — nothing to execute")
        return _result(trade)

    # Execute on Alpaca if keys available, otherwise simulate
    if os.getenv("ALPACA_API_KEY"):
        try:
            side  = "buy" if signal == "BUY" else "sell"
            trade = place_order(state["ticker"], side, shares, stop_loss)
        except Exception as e:
            trade = skip_trade(f"Alpaca order failed: {e}")
    else:
        price = get_current_price(state["ticker"])
        from agent.schemas import TradeExecution
        trade = TradeExecution(
            action=signal.lower(),
            shares=shares,
            price=price,
            stop_loss=stop_loss,
            order_id="simulated",
            skipped_reason=None,
        )

    return _result(trade)


def _result(trade) -> dict:
    if trade.skipped_reason:
        msg = f"[Execution] SKIPPED — {trade.skipped_reason}"
    else:
        msg = (f"[Execution] {trade.action.upper()} {trade.shares} shares "
               f"@ ${trade.price} | stop ${trade.stop_loss} | id={trade.order_id}")
    return {
        "trade_execution": trade,
        "messages": [AIMessage(content=msg)],
    }
