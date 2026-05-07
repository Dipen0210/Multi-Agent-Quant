import torch
from transformers import BertTokenizer, BertForSequenceClassification
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "my-finbert-finetuned"
LABELS = {0: "negative", 1: "neutral", 2: "positive"}

_model = None
_tokenizer = None


def _load():
    global _model, _tokenizer
    if _model is None:
        _tokenizer = BertTokenizer.from_pretrained(str(MODEL_DIR))
        _model = BertForSequenceClassification.from_pretrained(str(MODEL_DIR))
        _model.eval()


def predict(headlines: list[str]) -> list[dict]:
    """Score a list of headlines. Returns per-headline label + probabilities."""
    _load()
    results = []
    for text in headlines:
        inputs = _tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        with torch.no_grad():
            logits = _model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).squeeze().tolist()
        pred_id = int(torch.argmax(logits, dim=-1).item())
        results.append({
            "text": text,
            "label": LABELS[pred_id],
            "score": round(probs[pred_id], 4),
            "probabilities": {
                "negative": round(probs[0], 4),
                "neutral":  round(probs[1], 4),
                "positive": round(probs[2], 4),
            },
        })
    return results


def aggregate(results: list[dict]) -> dict:
    """Aggregate per-headline results into a single ticker-level sentiment."""
    if not results:
        return {"label": "neutral", "score": 0.5, "headline_count": 0, "breakdown": {}}

    avg_pos = sum(r["probabilities"]["positive"] for r in results) / len(results)
    avg_neg = sum(r["probabilities"]["negative"] for r in results) / len(results)
    avg_neu = sum(r["probabilities"]["neutral"]  for r in results) / len(results)

    scores = {"positive": avg_pos, "neutral": avg_neu, "negative": avg_neg}
    dominant = max(scores, key=scores.__getitem__)

    return {
        "label": dominant,
        "score": round(scores[dominant], 4),
        "headline_count": len(results),
        "breakdown": {k: round(v, 4) for k, v in scores.items()},
    }
