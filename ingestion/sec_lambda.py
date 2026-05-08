"""
Lambda handler — weekly SEC filings ingestion pipeline.
Triggered by EventBridge cron: cron(0 6 ? * SUN *)  (6am UTC Sunday)

Flow:
  SEC EDGAR → fetch 10-K / 10-Q → chunk → embed → upsert Pinecone → archive S3
"""

import json
import os
import boto3
import httpx
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from agent.tools.sec_edgar_tool import fetch_recent_filings, chunk_filing_text
from agent.tools.pinecone_tool  import upsert_documents, NS_SEC
from ingestion.cleaner          import prepare_sec_docs

WATCHED_TICKERS = os.getenv(
    "WATCHED_TICKERS",
    "NVDA,AAPL,MSFT,TSLA,GOOGL,AMZN,META,AMD"
).split(",")

S3_BUCKET = os.getenv("S3_BUCKET", "quantsentiment-data")
EDGAR_HEADERS = {"User-Agent": "QuantSentimentAgent research@quantsentiment.ai"}


def _fetch_filing_text(url: str) -> str:
    """Download and return raw text from a SEC filing URL."""
    try:
        resp = httpx.get(url, headers=EDGAR_HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        # Strip HTML tags for plain text filings
        import re
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text)
        return text[:50000]       # cap at 50K chars per filing
    except Exception as e:
        print(f"[filing fetch error] {url}: {e}")
        return ""


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
    """Core ingestion logic — callable locally for testing."""
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = {}

    for ticker in tickers:
        try:
            filings = fetch_recent_filings(ticker, form_types=["10-K", "10-Q"], count=2)
            if not filings:
                summary[ticker] = 0
                continue

            total_vectors = 0
            for filing in filings:
                raw_text = _fetch_filing_text(filing["url"])
                if not raw_text:
                    continue

                chunks = chunk_filing_text(raw_text, chunk_size=400, overlap=50)
                docs   = prepare_sec_docs(filing, ticker, chunks)

                id_prefix = f"{ticker}-{filing['form']}-{filing['date']}-"
                count     = upsert_documents(docs, namespace=NS_SEC, id_prefix=id_prefix)
                total_vectors += count

                _archive_to_s3(
                    {"ticker": ticker, "filing": filing, "chunk_count": len(chunks)},
                    key=f"sec-filings/{ticker}/{filing['form']}-{filing['date']}.json",
                )
                print(f"[{ticker}] {filing['form']} ({filing['date']}) → {count} vectors")

            summary[ticker] = total_vectors

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
