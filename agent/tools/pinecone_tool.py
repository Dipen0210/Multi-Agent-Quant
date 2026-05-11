import os
import time
from datetime import datetime, timezone
from functools import lru_cache
from pinecone import Pinecone, ServerlessSpec
from agent.tools.embedder import embed_text, embed_texts, get_embedding_dim

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "quantsentiment")

# Namespaces
NS_NEWS  = "news"
NS_SEC   = "sec-filings"
NS_MACRO = "macro-trend"


@lru_cache(maxsize=1)
def _get_index():
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        pc.create_index(
            name=INDEX_NAME,
            dimension=get_embedding_dim(),
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(INDEX_NAME)


def upsert_documents(
    docs: list[dict],
    namespace: str,
    id_prefix: str = "",
) -> int:
    """
    Embed and upsert a list of documents into Pinecone.
    Each doc must have 'text' key; other keys become metadata.
    Returns number of vectors upserted.
    """
    if not docs:
        return 0

    texts   = [d["text"] for d in docs]
    vectors = embed_texts(texts)

    records = []
    for i, (doc, vec) in enumerate(zip(docs, vectors)):
        meta = {k: v for k, v in doc.items() if k != "text"}
        meta["text"] = doc["text"][:500]          # store snippet for display
        records.append({
            "id":     f"{id_prefix}{i}",
            "values": vec,
            "metadata": meta,
        })

    index = _get_index()
    index.upsert(vectors=records, namespace=namespace)
    return len(records)


def query_similar(
    query: str,
    namespace: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve top-k most similar documents for a query string.
    Returns list of {text, score, metadata}.
    """
    vec   = embed_text(query)
    index = _get_index()
    resp  = index.query(vector=vec, top_k=top_k, namespace=namespace, include_metadata=True)

    results = []
    for match in resp.matches:
        results.append({
            "text":     match.metadata.get("text", ""),
            "score":    round(match.score, 4),
            "metadata": match.metadata,
        })
    return results


def query_news(query: str, top_k: int = 5) -> list[dict]:
    return query_similar(query, NS_NEWS, top_k)


def query_sec(query: str, top_k: int = 5) -> list[dict]:
    return query_similar(query, NS_SEC, top_k)


def upsert_sec_chunks(ticker: str, form: str, date: str, accession: str, chunks: list[str]) -> int:
    """Embed and store SEC filing chunks with ticker metadata for later retrieval.
    IDs are sec-{TICKER}-{i} so upserting a new filing overwrites the same positions.
    """
    ticker_up   = ticker.upper()
    chunk_count = len(chunks)
    vectors     = embed_texts(chunks)
    records     = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        records.append({
            "id":     f"sec-{ticker_up}-{i}",
            "values": vec,
            "metadata": {
                "text":        chunk[:500],
                "ticker":      ticker_up,
                "form":        form,
                "date":        date,
                "accession":   accession,
                "chunk_count": chunk_count,
                "timestamp":   int(time.time()),
            },
        })
    index = _get_index()
    index.upsert(vectors=records, namespace=NS_SEC)
    return len(records)


def delete_sec_chunks(ticker: str, chunk_count: int) -> None:
    """Delete all stored chunk IDs for a ticker (used before upserting a new filing)."""
    ids = [f"sec-{ticker.upper()}-{i}" for i in range(chunk_count)]
    _get_index().delete(ids=ids, namespace=NS_SEC)


def get_stored_filing_info(ticker: str) -> dict | None:
    """Return {date, chunk_count} for the stored SEC filing, or None if not found."""
    try:
        vec   = embed_text(f"{ticker} SEC filing financial results")
        index = _get_index()
        resp  = index.query(
            vector=vec,
            top_k=1,
            filter={"ticker": {"$eq": ticker.upper()}},
            namespace=NS_SEC,
            include_metadata=True,
        )
        if not resp.matches:
            return None
        meta = resp.matches[0].metadata
        return {
            "date":        meta.get("date"),
            "chunk_count": int(meta.get("chunk_count", 0)),
        }
    except Exception:
        return None


def query_sec_for_ticker(ticker: str, query: str, top_k: int = 6) -> list[dict]:
    """Retrieve most relevant SEC chunks for a specific ticker via similarity search."""
    vec   = embed_text(query)
    index = _get_index()
    resp  = index.query(
        vector=vec,
        top_k=top_k,
        filter={"ticker": {"$eq": ticker.upper()}},
        namespace=NS_SEC,
        include_metadata=True,
    )
    return [
        {"text": m.metadata.get("text", ""), "score": round(m.score, 4), "metadata": m.metadata}
        for m in resp.matches
    ]




# ── Macro trend store ──────────────────────────────────────────────────────────

def save_macro_snapshot(summary: str, metadata: dict) -> bool:
    """Upsert today's macro snapshot — one record per day, keyed by date."""
    try:
        index = _get_index()
        vector = embed_text(summary)
        today = datetime.now().strftime("%Y-%m-%d")

        index.upsert(
            vectors=[{
                "id": f"macro-{today}",
                "values": vector,
                "metadata": {**metadata, "date": today, "timestamp": int(time.time())},
            }],
            namespace=NS_MACRO,
        )
        return True
    except Exception:
        return False


def fetch_macro_trend(days: int = 14) -> list[dict]:
    """Return up to `days` recent macro snapshots, sorted oldest → newest."""
    try:
        index = _get_index()
        cutoff_ts = int(time.time()) - (days * 86400)
        query_vec = embed_text("global market macro economic conditions today")

        results = index.query(
            vector=query_vec,
            top_k=days,
            filter={"timestamp": {"$gte": cutoff_ts}},
            include_metadata=True,
            namespace=NS_MACRO,
        )

        snapshots = [m.metadata for m in results.matches if m.metadata]
        return sorted(snapshots, key=lambda x: x.get("timestamp", 0))
    except Exception:
        return []


def compute_vix_trend(snapshots: list[dict]) -> str:
    """Rising / falling / stable based on VIX direction across snapshots."""
    vix_values = [s["vix"] for s in snapshots if s.get("vix") is not None]
    if len(vix_values) < 2:
        return "stable"
    delta = vix_values[-1] - vix_values[0]
    if delta > 3:
        return "rising"
    if delta < -3:
        return "falling"
    return "stable"


def compute_consecutive_risk_off(snapshots: list[dict]) -> int:
    """Count trailing consecutive risk_off days."""
    count = 0
    for s in reversed(snapshots):
        if s.get("risk_environment") == "risk_off":
            count += 1
        else:
            break
    return count
