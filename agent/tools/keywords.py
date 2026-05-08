import re
from collections import Counter

_STOP = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with','is',
    'are','was','were','will','be','has','have','had','it','its','this','that',
    'from','by','as','into','after','over','about','just','also','more','than',
    'stock','shares','market','says','said','new','year','quarter','company',
    'percent','billion','million','inc','corp','ltd','quarter','fiscal','report',
}


def extract_keywords(texts: list[str], n: int = 6) -> list[str]:
    words = []
    for t in texts:
        words.extend(re.findall(r"\b[a-zA-Z]{4,}\b", t.lower()))
    filtered = [w for w in words if w not in _STOP]
    return [w for w, _ in Counter(filtered).most_common(n)]


def score_to_decision(score: float) -> str:
    if score >= 0.62:
        return "bullish"
    if score <= 0.38:
        return "bearish"
    return "neutral"


def score_to_label(score: float) -> str:
    if score >= 0.62:
        return "positive"
    if score <= 0.38:
        return "negative"
    return "neutral"
