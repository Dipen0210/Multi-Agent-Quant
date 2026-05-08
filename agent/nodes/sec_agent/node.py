from datetime import datetime, timedelta, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import SECFilingOutput
from agent.tools.sec_edgar_tool import fetch_recent_filings
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label

_RECENT_DAYS = 30  # only consider filings from the last 30 days

_BULLISH = {"growth","beat","exceeded","raised","record","strong","positive","increased","acceleration"}
_BEARISH = {"decline","loss","impairment","risk","litigation","investigation","miss","reduced","headwind","uncertain"}


def _score_filing_text(text: str) -> float:
    words = set(text.lower().split())
    bulls = len(words & _BULLISH)
    bears = len(words & _BEARISH)
    total = bulls + bears
    if total == 0:
        return 0.5
    return round(0.5 + 0.5 * (bulls - bears) / total, 3)


def sec_node(state: AgentState) -> dict:
    ticker = state["ticker"]

    try:
        filings = fetch_recent_filings(ticker, form_types=["10-Q", "10-K", "8-K"], count=5)
    except Exception:
        filings = []

    # Filter to only recent filings (last 30 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_DAYS)
    recent = [
        f for f in filings
        if f.get("date") and datetime.fromisoformat(f["date"].replace("Z","")).replace(tzinfo=timezone.utc) >= cutoff
    ] if filings else []
    filings = recent if recent else filings[:1]  # fallback to most recent if none in window

    if not filings:
        output = SECFilingOutput(
            decision        = "neutral",
            sentiment_label = "neutral",
            sentiment_score = 0.5,
            filing_type     = "none",
            key_findings    = ["No recent SEC filings found"],
            keywords        = [],
            reasoning       = "No SEC filings available for analysis.",
        )
        return {
            "sec_filing": output,
            "messages":   [AIMessage(content="[SEC Agent] No filings found → neutral")],
        }

    filing      = filings[0]
    text        = filing.get("text", "")[:2000]
    filing_type = filing.get("form", "unknown")
    score       = _score_filing_text(text)
    keywords    = extract_keywords([text], n=8)
    decision    = score_to_decision(score)
    label       = score_to_label(score)

    key_terms = {"revenue","earnings","guidance","margin","growth","loss","cash","debt"}
    findings  = [
        line.strip()
        for line in text.split(".")
        if any(t in line.lower() for t in key_terms)
    ][:4]

    reasoning = (
        f"Most recent {filing_type} filing analysed. "
        f"Bullish/bearish term ratio gives score {score:.2f}. "
        f"Key themes: {', '.join(keywords[:4]) if keywords else 'none'}."
    )

    output = SECFilingOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        filing_type     = filing_type,
        key_findings    = findings if findings else [text[:100]],
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "sec_filing": output,
        "messages": [AIMessage(
            content=f"[SEC Agent] {filing_type} → {decision} ({score:.2f}) | keywords: {', '.join(keywords[:3])}"
        )],
    }
