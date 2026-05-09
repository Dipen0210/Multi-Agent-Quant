from datetime import datetime, timedelta, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import SECFilingOutput
from agent.tools.sec_edgar_tool import fetch_recent_filings
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label

_RECENT_DAYS = 30

_EXTRACT_PROMPT = """You are a financial analyst. The text below is raw SEC filing content (may contain XBRL tags, numbers, legal boilerplate).
Extract 8-10 clear, concise English sentences that summarize the key financial highlights:
revenue, earnings, guidance, risks, growth, margins, cash flow, debt.
Return ONLY the sentences, one per line. No bullet points. No preamble.

Filing text:
{text}"""


def _extract_filing_sentences(raw_text: str) -> list[str]:
    """Use Groq to extract clean financial sentences from raw EDGAR text."""
    if not raw_text or len(raw_text) < 50:
        return []
    try:
        from agent.tools.llm_client import get_llm
        prompt = _EXTRACT_PROMPT.format(text=raw_text[:4000])
        resp = get_llm().invoke(prompt)
        lines = [l.strip() for l in resp.content.strip().split("\n") if len(l.strip()) > 20]
        return lines[:10]
    except Exception:
        return []


def _score_sentences(sentences: list[str]) -> tuple[float, str]:
    """Score extracted sentences with FinBERT. Returns (score, label)."""
    if not sentences:
        return 0.5, "neutral"
    result = score_headlines(sentences)
    agg = result["aggregate"]
    return agg["score"], agg["label"]


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
    filing_type = filing.get("form", "unknown")
    raw_text    = filing.get("text", "")

    # Groq extracts clean financial sentences from raw XBRL/HTML → FinBERT scores them
    sentences   = _extract_filing_sentences(raw_text)
    score, label = _score_sentences(sentences)
    text_for_kw = " ".join(sentences)
    keywords    = extract_keywords([text_for_kw], n=8)
    decision    = score_to_decision(score)

    # Key findings = the extracted sentences (already clean English)
    findings = sentences[:4] if sentences else [raw_text[:100]]

    reasoning = (
        f"Most recent {filing_type} filing — Groq extracted {len(sentences)} financial sentences, "
        f"scored via FinBERT. Score {score:.2f} ({label}). "
        f"Key themes: {', '.join(keywords[:4]) if keywords else 'none'}."
    )

    output = SECFilingOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        filing_type     = filing_type,
        filing_url      = filing.get("url", ""),
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
