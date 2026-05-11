from datetime import datetime, timedelta, timezone
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.schemas import SECFilingOutput
from agent.tools.sec_edgar_tool import fetch_recent_filings, chunk_filing_text
from agent.tools.finbert_tool import score_headlines
from agent.tools.keywords import extract_keywords, score_to_decision, score_to_label
from agent.tools.pinecone_tool import (
    upsert_sec_chunks,
    query_sec_for_ticker,
    has_recent_sec_filing,
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


def _ingest_and_store(ticker: str, filing: dict) -> list[dict]:
    """Chunk a filing, embed it, store in Pinecone, return retrieved chunks."""
    raw_text = filing.get("text", "")
    chunks   = chunk_filing_text(raw_text, chunk_size=500, overlap=50)
    if chunks:
        upsert_sec_chunks(
            ticker    = ticker,
            form      = filing.get("form", "unknown"),
            date      = filing.get("date", ""),
            accession = filing.get("accession", ""),
            chunks    = chunks,
        )
    return query_sec_for_ticker(ticker, _RAG_QUERY.format(ticker=ticker))


def sec_node(state: AgentState) -> dict:
    ticker = state["ticker"]

    # ── 1. RAG: check Pinecone cache first ────────────────────────────────────
    source = "pinecone-cache"
    if has_recent_sec_filing(ticker):
        chunks = query_sec_for_ticker(ticker, _RAG_QUERY.format(ticker=ticker))
        filing_type = chunks[0]["metadata"].get("form", "unknown") if chunks else "unknown"
        filing_url  = ""
    else:
        # ── 2. Cache miss: fetch from EDGAR, chunk, embed, store ───────────────
        source = "edgar-live"
        try:
            filings = fetch_recent_filings(ticker, form_types=["10-Q", "10-K", "8-K"], count=5)
        except Exception:
            filings = []

        cutoff = datetime.now(timezone.utc) - timedelta(days=_RECENT_DAYS)
        recent = [
            f for f in filings
            if f.get("date") and datetime.fromisoformat(f["date"].replace("Z", "")).replace(tzinfo=timezone.utc) >= cutoff
        ] if filings else []
        filing = (recent or filings[:1] or [None])[0]

        if not filing:
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

        filing_type = filing.get("form", "unknown")
        filing_url  = filing.get("url", "")
        chunks      = _ingest_and_store(ticker, filing)

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
