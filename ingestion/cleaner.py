import re


def clean_text(text: str) -> str:
    """Remove URLs, special chars, and excess whitespace from raw text."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[^\w\s\.\,\!\?\-\%\$]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-based chunks for embedding."""
    words  = text.split()
    chunks = []
    start  = 0
    while start < len(words):
        chunk = " ".join(words[start : start + chunk_size])
        if len(chunk.split()) >= 20:       # skip tiny trailing chunks
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def prepare_news_docs(articles: list[dict], ticker: str, date: str) -> list[dict]:
    """
    Convert raw Tavily articles into Pinecone-ready documents.
    Each doc has 'text' + metadata for retrieval context.
    """
    docs = []
    for a in articles:
        raw  = f"{a.get('title', '')} {a.get('content', '')}"
        text = clean_text(raw)
        if len(text.split()) < 10:
            continue
        docs.append({
            "text":    text[:600],
            "ticker":  ticker,
            "date":    date,
            "url":     a.get("url", ""),
            "title":   a.get("title", ""),
            "source":  "tavily",
        })
    return docs


def prepare_sec_docs(filing: dict, ticker: str, chunks: list[str]) -> list[dict]:
    """Convert SEC filing chunks into Pinecone-ready documents."""
    docs = []
    for i, chunk in enumerate(chunks):
        docs.append({
            "text":    clean_text(chunk),
            "ticker":  ticker,
            "form":    filing.get("form", ""),
            "date":    filing.get("date", ""),
            "url":     filing.get("url", ""),
            "chunk_id": i,
            "source":  "sec_edgar",
        })
    return docs
