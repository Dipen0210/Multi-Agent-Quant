import os
import threading
from functools import lru_cache

STACK = os.getenv("STACK", "free")

_LABEL_MAP = {"positive": "bullish", "negative": "bearish", "neutral": "neutral"}
_lock = threading.Lock()
_pipeline_instance = None


_HF_MODEL = os.getenv("FINBERT_MODEL", "Dipen0210/finbert-finetuned")


def _get_pipeline():
    global _pipeline_instance
    if _pipeline_instance is None:
        with _lock:
            if _pipeline_instance is None:
                from transformers import pipeline
                _pipeline_instance = pipeline(
                    "text-classification",
                    model=_HF_MODEL,
                    top_k=None,
                    device=-1,  # CPU
                )
    return _pipeline_instance


def score_headlines(headlines: list[str]) -> dict:
    """
    Score headlines using local FinBERT (ProsusAI/finbert).
    Returns {results, aggregate} dict.
    aggregate.score: 0.0 (bearish) → 0.5 (neutral) → 1.0 (bullish)
    """
    neutral = {
        "results": [],
        "aggregate": {"label": "neutral", "score": 0.5, "headline_count": 0, "breakdown": {}},
    }
    if not headlines:
        return neutral

    # Truncate to 512 chars per headline (FinBERT context limit)
    texts = [h[:512] for h in headlines]

    try:
        pipe = _get_pipeline()
        raw_results = pipe(texts)
    except Exception:
        return {**neutral, "aggregate": {**neutral["aggregate"], "headline_count": len(headlines)}}

    results = []
    net_scores = []
    label_counts: dict[str, int] = {"bullish": 0, "bearish": 0, "neutral": 0}

    for text, probs in zip(texts, raw_results):
        prob_map = {p["label"]: p["score"] for p in probs}
        pos = prob_map.get("positive", 0.0)
        neg = prob_map.get("negative", 0.0)
        neu = prob_map.get("neutral", 0.0)

        # Net sentiment: +1 = bullish, -1 = bearish
        net = pos - neg
        net_scores.append(net)

        top_label = max(prob_map, key=prob_map.__getitem__)
        mapped_label = _LABEL_MAP.get(top_label, "neutral")
        label_counts[mapped_label] += 1

        results.append({
            "text": text,
            "label": mapped_label,
            "score": round(0.5 + 0.5 * net, 4),
            "probabilities": {
                "bullish": round(pos, 4),
                "bearish": round(neg, 4),
                "neutral": round(neu, 4),
            },
        })

    avg_net = sum(net_scores) / len(net_scores) if net_scores else 0.0
    agg_score = round(0.5 + 0.5 * avg_net, 4)

    total = len(results)
    agg_label = "neutral"
    if label_counts["bullish"] > total / 2:
        agg_label = "bullish"
    elif label_counts["bearish"] > total / 2:
        agg_label = "bearish"

    return {
        "results": results,
        "aggregate": {
            "label": agg_label,
            "score": agg_score,
            "headline_count": total,
            "breakdown": {k: round(v / total, 3) for k, v in label_counts.items()},
        },
    }
