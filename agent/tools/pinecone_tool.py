import os
from functools import lru_cache
from pinecone import Pinecone, ServerlessSpec
from agent.tools.embedder import embed_text, embed_texts, get_embedding_dim

INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "quantsentiment")

# Namespaces
NS_NEWS = "news"
NS_SEC  = "sec-filings"


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
