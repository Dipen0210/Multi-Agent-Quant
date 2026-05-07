import os
import json
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from agent.schemas import NewsAnalystOutput

STACK = os.getenv("STACK", "free")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def score_headlines(headlines: list[str]) -> dict:
    """
    Score headlines using FinBERT.
    Routes to HuggingFace Spaces (free) or SageMaker (upgrade).
    Returns raw {results, aggregate} dict.
    """
    if not headlines:
        return {"results": [], "aggregate": {"label": "neutral", "score": 0.5,
                                              "headline_count": 0, "breakdown": {}}}
    if STACK == "bedrock":
        return _score_sagemaker(headlines)
    return _score_hf_spaces(headlines)


def _score_hf_spaces(headlines: list[str]) -> dict:
    url = os.getenv("HF_SPACES_URL", "").rstrip("/") + "/api/predict"
    payload = {"data": [json.dumps(headlines)]}
    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()
    raw = response.json()["data"][0]
    return json.loads(raw)


def _score_sagemaker(headlines: list[str]) -> dict:
    import boto3
    client = boto3.client("sagemaker-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    payload = json.dumps({"headlines": headlines})
    response = client.invoke_endpoint(
        EndpointName=os.getenv("SAGEMAKER_ENDPOINT"),
        ContentType="application/json",
        Body=payload,
    )
    return json.loads(response["Body"].read())


def build_news_output(headlines: list[str], raw: dict, similar_events: list, sec_context: str) -> NewsAnalystOutput:
    agg = raw["aggregate"]
    return NewsAnalystOutput(
        sentiment_label=agg["label"],
        sentiment_score=agg["score"],
        headline_count=agg["headline_count"],
        breakdown=agg["breakdown"],
        headlines=headlines,
        similar_past_events=similar_events,
        sec_context=sec_context,
    )
