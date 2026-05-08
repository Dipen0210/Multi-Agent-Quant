"""
Lambda handler — nightly news ingestion pipeline.
Triggered by EventBridge cron: cron(0 23 * * ? *)  (11pm UTC daily)

Flow:
  Tavily → clean → embed (HF / Bedrock Titan) → upsert Pinecone → archive to S3
"""

import json
import os
import boto3
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from agent.tools.tavily_tool   import fetch_news, extract_headlines
from agent.tools.pinecone_tool import upsert_documents, NS_NEWS
from ingestion.cleaner         import prepare_news_docs

WATCHED_TICKERS = os.getenv(
    "WATCHED_TICKERS",
    "NVDA,AAPL,MSFT,TSLA,GOOGL,AMZN,META,AMD"
).split(",")

S3_BUCKET = os.getenv("S3_BUCKET", "quantsentiment-data")


def _archive_to_s3(data: dict, key: str) -> None:
    try:
        boto3.client("s3").put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(data),
            ContentType="application/json",
        )
    except Exception as e:
        print(f"[S3 archive skipped] {e}")


def run(tickers: list[str] = WATCHED_TICKERS) -> dict:
    """
    Core ingestion logic — callable locally for testing.
    Returns summary of vectors upserted per ticker.
    """
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = {}

    for ticker in tickers:
        try:
            articles = fetch_news(ticker, days=1)
            if not articles:
                summary[ticker] = 0
                continue

            docs = prepare_news_docs(articles, ticker, today)
            if not docs:
                summary[ticker] = 0
                continue

            count = upsert_documents(
                docs,
                namespace=NS_NEWS,
                id_prefix=f"{ticker}-{today}-",
            )
            summary[ticker] = count

            _archive_to_s3(
                {"ticker": ticker, "date": today, "articles": articles},
                key=f"news-data/{today}/{ticker}.json",
            )
            print(f"[{ticker}] upserted {count} vectors")

        except Exception as e:
            print(f"[{ticker}] ERROR: {e}")
            summary[ticker] = -1

    return summary


def handler(event, context):
    """AWS Lambda entrypoint."""
    summary = run()
    total   = sum(v for v in summary.values() if v > 0)
    print(f"Done — {total} total vectors upserted: {summary}")
    return {"statusCode": 200, "body": json.dumps(summary)}


if __name__ == "__main__":
    print(run())
