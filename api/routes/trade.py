from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str
    side: str        # buy | sell
    shares: int
    stop_loss: float


@router.post("/trade", summary="Manually place a trade on Alpaca paper trading")
def place_trade(req: TradeRequest):
    """
    Place a market order on Alpaca paper trading.
    Called by the frontend when user clicks 'Confirm Trade'.
    """
    if req.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    if req.shares <= 0:
        raise HTTPException(status_code=400, detail="shares must be > 0")

    try:
        if req.side == "sell":
            from agent.tools.alpaca_tool import get_positions, place_order
            positions = get_positions()
            holding = next((p for p in positions if p["ticker"].upper() == req.ticker.upper()), None)
            if not holding or holding["qty"] <= 0:
                raise HTTPException(status_code=400, detail=f"No position held in {req.ticker}")
            qty = min(req.shares, holding["qty"])
            trade = place_order(req.ticker, "sell", qty, req.stop_loss)
        else:
            from agent.tools.alpaca_tool import place_order
            trade = place_order(req.ticker, "buy", req.shares, req.stop_loss)

        return {
            "status":    "executed",
            "ticker":    req.ticker,
            "action":    trade.action,
            "shares":    trade.shares,
            "price":     trade.price,
            "stop_loss": trade.stop_loss,
            "order_id":  trade.order_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Alpaca error: {e}")
