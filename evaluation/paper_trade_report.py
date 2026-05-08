"""
Paper trading report — reads closed Alpaca paper orders and computes metrics.

Usage:
    python -m evaluation.paper_trade_report
    python -m evaluation.paper_trade_report --days 30
"""
import argparse
import os
from datetime import datetime, timedelta, timezone

from evaluation.metrics import TradeRecord, evaluate, format_report


def _fetch_alpaca_orders(days: int) -> list:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    client = TradingClient(
        api_key    = os.getenv("ALPACA_API_KEY", ""),
        secret_key = os.getenv("ALPACA_SECRET_KEY", ""),
        paper      = True,
    )
    after = datetime.now(timezone.utc) - timedelta(days=days)
    req   = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after, limit=200)
    return client.get_orders(req)


def _pair_orders(orders: list) -> list[TradeRecord]:
    buys:  dict[str, list] = {}
    sells: dict[str, list] = {}

    for o in orders:
        if o.filled_avg_price is None:
            continue
        price  = float(o.filled_avg_price)
        ticker = o.symbol
        if o.side.value == "buy":
            buys.setdefault(ticker, []).append(price)
        else:
            sells.setdefault(ticker, []).append(price)

    records = []
    for ticker, buy_prices in buys.items():
        sell_prices = sells.get(ticker, [])
        for i, entry in enumerate(buy_prices):
            exit_p = sell_prices[i] if i < len(sell_prices) else 0.0
            records.append(TradeRecord(
                ticker      = ticker,
                action      = "buy",
                shares      = 1,
                entry_price = entry,
                exit_price  = exit_p,
            ))
    return records


def main():
    parser = argparse.ArgumentParser(description="Alpaca paper trade report")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    if not os.getenv("ALPACA_API_KEY"):
        print("ALPACA_API_KEY not set — cannot fetch orders.")
        return

    print(f"\nFetching Alpaca paper orders (last {args.days} days)...\n")
    try:
        orders = _fetch_alpaca_orders(args.days)
        trades = _pair_orders(orders)
        result = evaluate(trades)
        print(format_report(result))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
