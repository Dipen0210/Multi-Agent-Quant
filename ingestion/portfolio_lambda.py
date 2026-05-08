"""
Lambda handler — portfolio tracker.
Triggered by EventBridge cron: cron(0/15 13-20 ? * MON-FRI *)  (every 15min, market hours UTC)

Flow:
  Alpaca Paper API → fetch positions + P&L → log to S3
"""

import json
import os
import boto3
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET", "quantsentiment-data")


def _save_to_s3(data: dict) -> None:
    try:
        now = datetime.now(timezone.utc)
        key = f"paper-trading-logs/{now.strftime('%Y-%m-%d')}/{now.strftime('%H-%M')}.json"
        boto3.client("s3").put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
        print(f"[S3] saved portfolio snapshot → {key}")
    except Exception as e:
        print(f"[S3 save skipped] {e}")


def run() -> dict:
    """Fetch Alpaca paper portfolio state and log it."""
    from agent.tools.alpaca_tool import get_account, get_positions

    account   = get_account()
    positions = get_positions()
    timestamp = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "timestamp": timestamp,
        "account":   account,
        "positions": positions,
        "position_count": len(positions),
    }

    _save_to_s3(snapshot)

    print(f"Portfolio value: ${account['portfolio_value']:,.2f} | "
          f"Cash: ${account['cash']:,.2f} | "
          f"Positions: {len(positions)}")
    return snapshot


def handler(event, context):
    """AWS Lambda entrypoint."""
    try:
        snapshot = run()
        return {"statusCode": 200, "body": json.dumps(snapshot)}
    except Exception as e:
        print(f"ERROR: {e}")
        return {"statusCode": 500, "body": str(e)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
