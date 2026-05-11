from datetime import datetime, timedelta, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import SECFilingOutput
from agent.tools.sec_edgar_tool import fetch_latest_filing_meta, fetch_recent_filings, chunk_filing_text
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label
from agent.tools.pinecone_tool import (
    upsert_sec_chunks,
    delete_sec_chunks,
    query_sec_for_ticker,
    get_stored_filing_info,
)

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


_RAG_QUERY = "{ticker} revenue earnings guidance risk factors financial performance"


def _fetch_and_store(ticker: str, meta: dict, stored_chunk_count: int) -> list[dict]:
    """Fetch full filing text, delete old Pinecone chunks, embed and store new ones."""
    # Delete old chunks cleanly before upserting new filing
    if stored_chunk_count > 0:
        delete_sec_chunks(ticker, stored_chunk_count)

    try:
        filings = fetch_recent_filings(ticker, form_types=["10-Q", "10-K", "8-K"], count=1)
    except Exception:
        filings = []

    filing   = filings[0] if filings else None
    raw_text = filing.get("text", "") if filing else ""
    chunks   = chunk_filing_text(raw_text, chunk_size=500, overlap=50)

    if chunks:
        upsert_sec_chunks(
            ticker    = ticker,
            form      = meta["form"],
            date      = meta["date"],
            accession = meta["accession"],
            chunks    = chunks,
        )
    return query_sec_for_ticker(ticker, _RAG_QUERY.format(ticker=ticker))


def sec_node(state: AgentState) -> dict:
    ticker = state["ticker"]

    # ── 1. Fast metadata check from EDGAR (no text download) ─────────────────
    try:
        meta = fetch_latest_filing_meta(ticker, form_types=["10-Q", "10-K", "8-K"])
    except Exception:
        meta = None

    if not meta:
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

    filing_type = meta["form"]
    filing_url  = meta["url"]

    # ── 2. Compare EDGAR date with what's stored in Pinecone ─────────────────
    stored = get_stored_filing_info(ticker)

    if stored and stored["date"] == meta["date"]:
        # Same filing already in Pinecone — use cache
        source = "pinecone-cache"
        chunks = query_sec_for_ticker(ticker, _RAG_QUERY.format(ticker=ticker))
    else:
        # New filing detected — fetch full text, overwrite Pinecone
        source = "edgar-live (new filing)"
        chunks = _fetch_and_store(ticker, meta, stored["chunk_count"] if stored else 0)

    if not chunks:
        output = SECFilingOutput(
            decision        = "neutral",
            sentiment_label = "neutral",
            sentiment_score = 0.5,
            filing_type     = filing_type,
            key_findings    = ["Could not extract content from filing"],
            keywords        = [],
            reasoning       = "Filing found but no usable text extracted.",
        )
        return {
            "sec_filing": output,
            "messages":   [AIMessage(content="[SEC Agent] No content extracted → neutral")],
        }

    # ── 3. Feed retrieved chunks to Groq → extract sentences → FinBERT ───────
    combined_text = " ".join(c["text"] for c in chunks)
    sentences     = _extract_filing_sentences(combined_text)
    score, label  = _score_sentences(sentences)
    keywords      = extract_keywords([" ".join(sentences)], n=8)
    decision      = score_to_decision(score)
    findings      = sentences[:4] if sentences else [combined_text[:200]]

    reasoning = (
        f"RAG ({source}): retrieved {len(chunks)} relevant chunks from {filing_type} filing, "
        f"Groq extracted {len(sentences)} financial sentences, scored via FinBERT. "
        f"Score {score:.2f} ({label}). "
        f"Key themes: {', '.join(keywords[:4]) if keywords else 'none'}."
    )

    output = SECFilingOutput(
        decision        = decision,
        sentiment_label = label,
        sentiment_score = score,
        filing_type     = filing_type,
        filing_url      = filing_url,
        key_findings    = findings,
        keywords        = keywords,
        reasoning       = reasoning,
    )

    return {
        "sec_filing": output,
        "messages": [AIMessage(
            content=f"[SEC Agent] {filing_type} ({source}) → {decision} ({score:.2f}) | keywords: {', '.join(keywords[:3])}"
        )],
    }
