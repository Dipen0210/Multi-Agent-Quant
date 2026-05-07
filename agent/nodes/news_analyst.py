import os
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.tools.tavily_tool import fetch_news, extract_headlines
from agent.tools.finbert_tool import score_headlines, build_news_output
from agent.tools.pinecone_tool import query_news, query_sec
from agent.schemas import SimilarEvent


def news_analyst_node(state: AgentState) -> dict:
    ticker = state["ticker"]
    days   = state.get("days", 2)
    sources: list[str] = []

    # 1. Fetch live headlines (graceful fallback if no API key)
    try:
        articles = fetch_news(ticker, days)
    except Exception:
        articles = []
    headlines, urls = extract_headlines(articles)
    sources.extend(urls)

    # 2. FinBERT sentiment scoring
    raw_sentiment = score_headlines(headlines) if headlines else {
        "results": [], "aggregate": {"label": "neutral", "score": 0.5,
                                     "headline_count": 0, "breakdown": {}}
    }

    # 3. RAG — similar historical news from Pinecone
    similar_events: list[SimilarEvent] = []
    pinecone_available = bool(os.getenv("PINECONE_API_KEY"))
    if pinecone_available and headlines:
        query     = f"{ticker} {headlines[0]}" if headlines else ticker
        rag_hits  = query_news(query, top_k=3)
        for hit in rag_hits:
            meta = hit.get("metadata", {})
            if meta.get("date") and meta.get("outcome"):
                similar_events.append(SimilarEvent(
                    date=meta.get("date", ""),
                    event=hit["text"][:80],
                    outcome=meta.get("outcome", ""),
                ))

    # 4. RAG — SEC filings context
    sec_context = ""
    if pinecone_available:
        sec_hits    = query_sec(f"{ticker} revenue earnings guidance", top_k=2)
        sec_context = " | ".join(h["text"][:120] for h in sec_hits if h["text"])

    output = build_news_output(headlines, raw_sentiment, similar_events, sec_context)

    return {
        "news_analyst": output,
        "sources":      state.get("sources", []) + sources,
        "messages": [AIMessage(
            content=f"[News Analyst] {output.headline_count} headlines → "
                    f"{output.sentiment_label} ({output.sentiment_score:.2f})"
        )],
    }
