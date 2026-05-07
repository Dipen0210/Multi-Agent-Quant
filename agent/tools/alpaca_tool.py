import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from agent.schemas import TradeExecution

_client = None


def _get_client() -> TradingClient:
    global _client
    if _client is None:
        _client = TradingClient(
            api_key=os.getenv("ALPACA_API_KEY"),
            secret_key=os.getenv("ALPACA_SECRET_KEY"),
            paper=True,
        )
    return _client


def get_account() -> dict:
    """Return account cash and portfolio value."""
    acct = _get_client().get_account()
    return {
        "cash":            round(float(acct.cash), 2),
        "portfolio_value": round(float(acct.portfolio_value), 2),
        "buying_power":    round(float(acct.buying_power), 2),
    }


def get_positions() -> list[dict]:
    """Return all open paper positions."""
    positions = _get_client().get_all_positions()
    return [
        {
            "ticker":      p.symbol,
            "qty":         int(p.qty),
            "avg_entry":   round(float(p.avg_entry_price), 2),
            "current":     round(float(p.current_price), 2),
            "unrealized_pl": round(float(p.unrealized_pl), 2),
            "pct":         round(float(p.unrealized_plpc) * 100, 2),
        }
        for p in positions
    ]


def get_portfolio_exposure(ticker: str) -> float:
    """Return fraction of portfolio currently in a given ticker (0.0–1.0)."""
    acct      = _get_client().get_account()
    total_val = float(acct.portfolio_value)
    if total_val == 0:
        return 0.0
    for p in _get_client().get_all_positions():
        if p.symbol.upper() == ticker.upper():
            return round(float(p.market_value) / total_val, 4)
    return 0.0


def place_order(ticker: str, side: str, qty: int, stop_loss_price: float) -> TradeExecution:
    """
    Place a market order on Alpaca paper trading.
    side: 'buy' or 'sell'
    """
    order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL

    req = MarketOrderRequest(
        symbol=ticker.upper(),
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )
    order = _get_client().submit_order(req)

    filled_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0

    return TradeExecution(
        action=side,
        shares=qty,
        price=round(filled_price, 2),
        stop_loss=round(stop_loss_price, 2),
        order_id=str(order.id),
    )


def skip_trade(reason: str) -> TradeExecution:
    """Return a no-op TradeExecution when Critic says HOLD."""
    return TradeExecution(
        action="hold",
        shares=0,
        price=0.0,
        stop_loss=0.0,
        skipped_reason=reason,
    )
