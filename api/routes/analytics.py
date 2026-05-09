from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

router = APIRouter()


def _get_client():
    import os
    from alpaca.trading.client import TradingClient
    return TradingClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
        paper=True,
    )


def _equity_history(client, period: str = "1M") -> list[dict]:
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        req  = GetPortfolioHistoryRequest(period=period, timeframe="1D", pnl_reset="per_day")
        hist = client.get_portfolio_history(req)
        points = []
        for ts, equity, pl in zip(hist.timestamp, hist.equity, hist.profit_loss):
            if equity and equity > 0:
                points.append({
                    "date":   datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %d"),
                    "equity": round(float(equity), 2),
                    "pl":     round(float(pl or 0), 2),
                })
        return points
    except Exception:
        return []


def _get_trades(client) -> list[dict]:
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    req    = GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50)
    orders = client.get_orders(req)
    trades = []
    for o in orders:
        qty   = float(o.filled_qty or 0)
        price = float(o.filled_avg_price) if o.filled_avg_price else 0.0
        if qty == 0 or price == 0:
            continue
        trades.append({
            "ticker":  o.symbol,
            "side":    o.side.value,
            "qty":     int(qty),
            "price":   round(price, 2),
            "total":   round(qty * price, 2),
            "date":    o.filled_at.strftime("%Y-%m-%d %H:%M") if o.filled_at else "",
        })
    return trades


def _compute_metrics(account: dict, trades: list[dict], positions: list[dict]) -> dict:
    total_pl    = sum(p["unrealized_pl"] for p in positions)
    start_val   = 100_000.0  # Alpaca paper default
    current_val = account["portfolio_value"]
    total_pct   = round((current_val - start_val) / start_val * 100, 2)

    buys  = {t["ticker"]: t for t in trades if t["side"] == "buy"}
    sells = [t for t in trades if t["side"] == "sell"]
    wins  = sum(1 for s in sells if s["ticker"] in buys and s["price"] > buys[s["ticker"]]["price"])
    total_closed = len(sells)
    win_rate = round(wins / total_closed * 100, 1) if total_closed > 0 else None

    return {
        "total_pl":       round(total_pl, 2),
        "total_pl_pct":   total_pct,
        "num_trades":     len(trades),
        "open_positions": len(positions),
        "win_rate":       win_rate,
        "wins":           wins,
        "losses":         total_closed - wins,
    }


@router.get("/analytics", summary="Portfolio analytics — equity history, positions, trades, metrics")
def get_analytics(period: str = "1M"):
    try:
        from agent.tools.alpaca_tool import get_account, get_positions
        client    = _get_client()
        account   = get_account()
        positions = get_positions()
        trades    = _get_trades(client)
        history   = _equity_history(client, period)
        metrics   = _compute_metrics(account, trades, positions)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "account":   account,
            "metrics":   metrics,
            "equity_history": history,
            "positions": positions,
            "trades":    trades,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
