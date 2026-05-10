import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.alpaca_tool import place_order, skip_trade, get_positions
from agent.tools.yfinance_tool import get_current_price


def execution_node(state: AgentState) -> dict:
    critic    = state.get("critic_decision")
    risk      = state.get("risk_decision")
    portfolio = state.get("portfolio_signal")

    if not critic or critic.decision != "PROCEED":
        return _result(skip_trade("Critic did not approve"))

    signal = portfolio.signal if portfolio else "HOLD"
    if signal not in ("BUY", "SELL"):
        return _result(skip_trade(f"Signal is {signal} — no trade needed"))

    # Trade is ready but waits for user confirmation via the frontend button
    ticker    = state["ticker"]
    stop_loss = risk.stop_loss_price if risk else 0.0
    shares    = risk.adjusted_size   if risk else 0

    if shares <= 0:
        return _result(skip_trade("Position size is 0 — nothing to execute"))

    price = get_current_price(ticker)
    from agent.schemas import TradeExecution
    return _result(TradeExecution(
        action=signal.lower(),
        shares=shares,
        price=price,
        stop_loss=stop_loss,
        skipped_reason="awaiting_user_confirmation",
    ))


def _execute_buy(ticker: str, shares: int, stop_loss: float) -> dict:
    if not os.getenv("ALPACA_API_KEY"):
        price = get_current_price(ticker)
        from agent.schemas import TradeExecution
        return _result(TradeExecution(
            action="buy", shares=shares, price=price,
            stop_loss=stop_loss, order_id="simulated",
        ))
    try:
        return _result(place_order(ticker, "buy", shares, stop_loss))
    except Exception as e:
        return _result(skip_trade(f"Alpaca BUY failed: {e}"))


def _execute_sell(ticker: str, adjusted_size: int, stop_loss: float) -> dict:
    """For SELL: sell adjusted_size shares, capped at what we actually hold."""
    if not os.getenv("ALPACA_API_KEY"):
        return _result(skip_trade("SELL signal but Alpaca not configured — simulated skip"))

    try:
        positions = get_positions()
        holding = next((p for p in positions if p["ticker"].upper() == ticker.upper()), None)

        if not holding or holding["qty"] <= 0:
            return _result(skip_trade(
                f"SELL signal for {ticker} but no position held — cannot short"
            ))

        # Sell adjusted_size but never more than what we hold
        qty = min(adjusted_size, holding["qty"])
        trade = place_order(ticker, "sell", qty, stop_loss)
        return _result(trade)

    except Exception as e:
        return _result(skip_trade(f"Alpaca SELL failed: {e}"))


def _result(trade) -> dict:
    if trade.skipped_reason:
        msg = f"[Execution] SKIPPED — {trade.skipped_reason}"
    else:
        msg = (
            f"[Execution] {trade.action.upper()} {trade.shares} shares "
            f"@ ${trade.price} | stop ${trade.stop_loss} | id={trade.order_id}"
        )
    return {
        "trade_execution": trade,
        "messages": [AIMessage(content=msg)],
    }
