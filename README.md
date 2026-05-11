# QuantSentiment — Multi-Agent AI Trading System

A multi-agent AI system that analyses stock sentiment from 5 independent sources and makes paper trading decisions via Alpaca. Built on **LangGraph**, powered by **Groq (Llama 3.3 70B)** and a fine-tuned **FinBERT** model.

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │              ROUTER                 │
                        └──────────────┬──────────────────────┘
                                       │ (parallel fan-out)
          ┌──────────────┬─────────────┼──────────────┬──────────────┐
          ▼              ▼             ▼               ▼              ▼
   📰 Financial     💬 Reddit      📋 SEC         ⭐ Analyst     🌐 Macro
      News           Sentiment     Filings         Ratings        Agent
          │              │             │               │              │
          └──────────────┴─────────────┴───────────────┘              │
                                       │                               │
                                       ▼                               ▼
                              💼 Portfolio Manager          🛡️ Risk Manager
                                       │                               │
                                       └──────────────┬────────────────┘
                                                      ▼
                                               ⚖️ Critic
                                                      │
                                                      ▼
                                          ⚡ Execution (user confirms)
                                                      │
                                                      ▼
                                            Alpaca Paper Trading
```

## Agent Roles

| Agent | Role | Data Source |
|---|---|---|
| **Financial News** | News articles scored by FinBERT | Tavily |
| **Reddit** | Community sentiment from WSB/stocks/investing | Reddit API |
| **SEC Filings** | 10-Q/8-K — RAG pipeline: chunk → embed → Pinecone → retrieve → Groq → FinBERT | SEC EDGAR + Pinecone |
| **Analyst Ratings** | Institutional consensus + upside-adjusted score | yfinance |
| **Macro Agent** | VIX, yield, SPY, DXY + global news | Tavily + yfinance + Pinecone |
| **Portfolio Manager** | Sentiment synthesis → BUY/SELL/HOLD (3/4 agreement) | Groq Llama 3.3 70B |
| **Risk Manager** | Safety gates: VIX, SPY crash, position limits | Macro context |
| **Critic** | Final validation — blocks if confidence < 0.62 AND agreement < 3/4 | Groq Llama 3.3 70B |
| **Execution** | Surfaces recommendation; user clicks Confirm to place order | Alpaca Paper API |

---

## Tech Stack

### AI / ML
| Layer | Technology |
|---|---|
| LLM | Groq — Llama 3.3 70B *(upgradeable to AWS Bedrock — Claude / Llama via managed API)* |
| Sentiment Model | Fine-tuned FinBERT (`Dipen0210/finbert-finetuned`) |
| Model Hosting | Hugging Face Spaces (Gradio API) *(upgradeable to AWS SageMaker — dedicated endpoint, no cold starts)* |
| Agent Framework | LangGraph + LangChain |
| Observability | LangSmith |
| Vector Store | Pinecone |

### Data Sources
| Source | Technology |
|---|---|
| News | Tavily Search API |
| Market Data | yfinance |
| SEC Filings | SEC EDGAR API |
| Paper Trading | Alpaca Paper Trading API |

### Backend & Frontend
| Layer | Technology |
|---|---|
| Backend | FastAPI + SSE streaming |
| Frontend | Next.js 16 + Tailwind CSS + Recharts |
| MCP Server | FastMCP (Claude Desktop integration) |

### Infrastructure & DevOps
| Layer | Technology |
|---|---|
| Containerisation | Docker |
| Container Registry | AWS ECR |
| Compute | AWS EC2 |
| Reverse Proxy | Nginx (SSE-compatible, no buffering) |
| CI / CD | GitHub Actions (build → ECR → EC2 deploy on push to main) |

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/Dipen0210/Multi-Agent-Quant.git
cd Multi-Agent-Quant
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure `.env`

```env
STACK=free

GROQ_API_KEY=gsk_...

FINBERT_MODEL=Dipen0210/finbert-finetuned
HF_API_TOKEN=hf_...

PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=default

TAVILY_API_KEY=tvly-...

ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=quantsentiment-agent

CRITIC_CONFIDENCE_THRESHOLD=0.62
RISK_MAX_SINGLE_STOCK_PCT=0.10
RISK_STOP_LOSS_PCT=0.05
```

### 3. Run

```bash
# Backend
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## SEC Filings — RAG Pipeline

SEC filings (10-Q, 10-K, 8-K) are 50–100 pages — too large to feed directly into an LLM. The SEC agent uses a RAG (Retrieval Augmented Generation) pipeline to handle this:

```
User hits Analyze
       ↓
Fetch latest filing date from SEC EDGAR  (metadata only — fast, no text download)
       ↓
Compare with date stored in Pinecone for this ticker
       ↓
Same date → retrieve top 6 relevant chunks from Pinecone  (instant cache)
       ↓
New date → fetch full filing text → chunk (500 words, 50 overlap)
         → embed each chunk → delete old chunks → store new in Pinecone
       ↓
Similarity search: "revenue earnings guidance risk factors"
       ↓
Top 6 chunks → Groq extracts financial sentences → FinBERT scores sentiment
```

**Why RAG here specifically:**
- SEC filings exceed LLM context windows — RAG picks only financially relevant paragraphs
- Filings are stable for a quarter — caching in Pinecone avoids re-embedding the same document
- Date-based invalidation ensures the cache auto-refreshes when a new filing is published

**Pinecone namespaces used:**

| Namespace | What's stored |
|---|---|
| `sec-filings` | Chunked SEC filing embeddings, keyed by ticker |
| `macro-trend` | Daily macro snapshots (VIX, yield, SPY, DXY) for 14-day trend |

---

## Signal Logic

**BUY** — ≥ 3/4 sources bullish, confidence ≥ 0.62, Risk Manager approves, user confirms

**SELL** — ≥ 3/4 sources bearish, position held in Alpaca, user confirms

**HOLD** — everything else (conflict, low conviction, portfolio limit hit)

---

## Portfolio Analytics

Visit `/analytics` for equity chart (1W/1M/3M), open positions, trade history, and win rate.
