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
| **SEC Filings** | 10-Q/8-K — Groq extracts sentences → FinBERT scores | SEC EDGAR |
| **Analyst Ratings** | Institutional consensus + upside-adjusted score | yfinance |
| **Macro Agent** | VIX, yield, SPY, DXY + global news | Tavily + yfinance + Pinecone |
| **Portfolio Manager** | Sentiment synthesis → BUY/SELL/HOLD (3/4 agreement) | Groq Llama 3.3 70B |
| **Risk Manager** | Safety gates: VIX, SPY crash, position limits | Macro context |
| **Critic** | Final validation — blocks if confidence < 0.62 AND agreement < 3/4 | Groq Llama 3.3 70B |
| **Execution** | Surfaces recommendation; user clicks Confirm to place order | Alpaca Paper API |

---

## Tech Stack

| | |
|---|---|
| LLM | Groq — Llama 3.3 70B |
| Sentiment | Fine-tuned FinBERT (`Dipen0210/finbert-finetuned`) |
| Agent Framework | LangGraph + LangChain |
| Observability | LangSmith |
| Vector Store | Pinecone |
| News | Tavily Search API |
| Market Data | yfinance |
| SEC Data | SEC EDGAR API |
| Paper Trading | Alpaca Paper Trading API |
| Backend | FastAPI + SSE streaming |
| Frontend | Next.js 16 + Tailwind CSS + Recharts |
| MCP Server | FastMCP (Claude Desktop integration) |

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

## Signal Logic

**BUY** — ≥ 3/4 sources bullish, confidence ≥ 0.62, Risk Manager approves, user confirms

**SELL** — ≥ 3/4 sources bearish, position held in Alpaca, user confirms

**HOLD** — everything else (conflict, low conviction, portfolio limit hit)

---

## Portfolio Analytics

Visit `/analytics` for equity chart (1W/1M/3M), open positions, trade history, and win rate.
