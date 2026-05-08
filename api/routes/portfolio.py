import os
import boto3
import json
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

router = APIRouter()

S3_BUCKET = os.getenv("S3_BUCKET", "quantsentiment-data")


@router.get("/portfolio", summary="Current Alpaca paper trading positions")
def get_portfolio():
    """
    Returns live paper trading positions and P&L from Alpaca.
    Falls back to latest S3 snapshot if Alpaca key not set.
    """
    if os.getenv("ALPACA_API_KEY"):
        try:
            from agent.tools.alpaca_tool import get_account, get_positions
            return {
                "source":    "alpaca_live",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "account":   get_account(),
                "positions": get_positions(),
            }
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Alpaca error: {e}")

    # Fallback: latest snapshot from S3
    try:
        s3     = boto3.client("s3")
        today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        prefix = f"paper-trading-logs/{today}/"
        objs   = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
        items  = sorted(objs.get("Contents", []), key=lambda x: x["Key"], reverse=True)
        if items:
            obj  = s3.get_object(Bucket=S3_BUCKET, Key=items[0]["Key"])
            data = json.loads(obj["Body"].read())
            data["source"] = "s3_snapshot"
            return data
    except Exception:
        pass

    return {
        "source":    "unavailable",
        "message":   "Set ALPACA_API_KEY in .env to see live portfolio",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health", summary="Health check")
def health():
    return {
        "status":    "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stack":     os.getenv("STACK", "free"),
    }
