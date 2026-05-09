# QuantSentiment — Multi-Agent AI Trading System

A production-grade multi-agent AI system that analyses stock sentiment from 5 independent sources and makes paper trading decisions via Alpaca. Built on **LangGraph**, powered by **Groq (Llama 3.3 70B)** and a **fine-tuned FinBERT** model.

---

## Architecture

```
                        ┌─────────────────────────────────────┐
                        │              ROUTER                  │
                        └──────────────┬──────────────────────┘
                                       │ (parallel fan-out)
          ┌──────────────┬─────────────┼──────────────┬──────────────┐
          ▼              ▼             ▼               ▼              ▼
   📰 Financial     💬 Reddit      📋 SEC         ⭐ Analyst     🌐 Macro
      News           Sentiment     Filings         Ratings        Agent
   (Tavily+FinBERT) (Reddit API)  (EDGAR+Groq    (yfinance)    (Tavily+yfinance
                                  +FinBERT)                     +Pinecone)
          │              │             │               │              │
          └──────────────┴─────────────┴───────────────┘              │
                                       │                               │
                                       ▼                               ▼
                              💼 Portfolio Manager          🛡️ Risk Manager
                              (Groq LLM — sentiment        (VIX, yield, SPY,
                               reasoning only)              DXY safety gates)
                                       │                               │
                                       └──────────────┬────────────────┘
                                                      ▼
                                               ⚖️ Critic
                                          (LLM final debate —
                                           3/4 agreement gate)
                                                      │
                                                      ▼
                                               ⚡ Execution
                                          (Alpaca paper trading)
```

## Agent Roles

| Agent | Role | Data Source |
|---|---|---|
| **Financial News** | Today's news articles scored by FinBERT | Tavily search |
| **Reddit** | Community sentiment from WSB/stocks/investing | Reddit public API |
| **SEC Filings** | Most recent 10-Q/8-K — Groq extracts sentences → FinBERT scores | SEC EDGAR |
| **Analyst Ratings** | Institutional consensus + upside-adjusted score | yfinance |
| **Macro Agent** | Global market health: VIX, yield, SPY, DXY + global news | Tavily + yfinance + Pinecone |
| **Portfolio Manager** | Pure sentiment synthesis → BUY/SELL/HOLD (requires 3/4 agreement) | Groq Llama 3.3 70B |
| **Risk Manager** | Market safety gates (VIX > 35, SPY crash, DXY surge, position limits) | Macro context |
| **Critic** | Final validation — blocks if confidence < 0.62 AND agreement < 3/4 | Groq Llama 3.3 70B |
| **Execution** | Places market orders via Alpaca; SELL checks actual holdings | Alpaca Paper API |

---

## Tech Stack

```
LLM Reasoning     Groq — Llama 3.3 70B (free tier) / AWS Bedrock Claude (upgrade)
Sentiment Model   Fine-tuned FinBERT (local, ProsusAI/finbert base)
Agent Framework   LangGraph + LangChain
Observability     LangSmith (traces every node run)
Vector Store      Pinecone — macro trend history (VIX, risk env, sentiment)
News Fetch        Tavily Search API
Market Data       yfinance — VIX, 10yr yield, SPY, DXY, stock prices
SEC Data          SEC EDGAR API
Paper Trading     Alpaca Paper Trading API
Backend           FastAPI + SSE streaming
Frontend          Next.js 16 + Tailwind CSS + Framer Motion + Recharts
```

---

## Features

- **Real-time SSE streaming** — watch each agent complete live in the browser
- **Fine-tuned FinBERT** — custom financial sentiment model (not the base public model)
- **Pinecone macro memory** — tracks 14-day VIX trend and consecutive risk-off days
- **Groq → FinBERT pipeline for SEC filings** — LLM extracts readable sentences from raw XBRL, then FinBERT scores them
- **Portfolio analytics dashboard** — equity chart, open positions, trade history, win rate (Robinhood-style)
- **Smart SELL** — checks actual Alpaca holdings before selling, uses `min(adjusted_size, held_qty)`
- **Portfolio concentration guard** — max 10% in any single stock
- **LangSmith tracing** — full observability on every agent run

---

## Project Structure

```
agent/
├── graph.py                    # LangGraph StateGraph topology
├── state.py                    # Shared state TypedDict
├── schemas.py                  # Pydantic output schemas
├── nodes/
│   ├── financial_news_agent/   # Tavily + FinBERT
│   ├── reddit_agent/           # Reddit API + FinBERT
│   ├── sec_agent/              # EDGAR + Groq + FinBERT
│   ├── analyst_ratings_agent/  # yfinance consensus
│   ├── macro_agent/            # Global market context
│   ├── portfolio_manager/      # LLM sentiment synthesis
│   ├── risk_manager/           # Market safety gates
│   ├── critic/                 # LLM final debate
│   ├── execution/              # Alpaca order placement
│   └── formatter/              # Response assembly
└── tools/
    ├── finbert_tool.py         # Local fine-tuned FinBERT
    ├── tavily_tool.py          # News search
    ├── yfinance_tool.py        # Market indices + prices
    ├── sec_edgar_tool.py       # EDGAR filing fetch
    ├── pinecone_tool.py        # Macro trend store
    ├── alpaca_tool.py          # Paper trading orders
    ├── keywords.py             # Keyword extraction
    └── llm_client.py           # Groq / Bedrock LLM

api/
├── main.py                     # FastAPI app
└── routes/
    ├── stream.py               # SSE streaming endpoint
    ├── portfolio.py            # Live positions
    └── analytics.py           # Portfolio analytics

frontend/
└── app/
    ├── page.tsx                # Main dashboard
    └── analytics/page.tsx      # Portfolio analytics

huggingface/
└── my-finbert-finetuned/       # Fine-tuned FinBERT weights

evaluation/
├── paper_trade_report.py       # Alpaca trade metrics CLI
└── metrics.py                  # Sharpe, drawdown, win rate
```

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
STACK=free                          # free (Groq) or bedrock (AWS)

# LLM
GROQ_API_KEY=gsk_...

# Sentiment
# Fine-tuned model is loaded locally from huggingface/my-finbert-finetuned/

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX_NAME=default

# News
TAVILY_API_KEY=tvly-...

# Paper Trading
ALPACA_API_KEY=PK...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=quantsentiment-agent

# Risk settings
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

**BUY** fires only when:
- Portfolio Manager: ≥ 3/4 sources bullish → BUY with confidence ≥ 0.62
- Critic: agreement ≥ 3/4 AND confidence passes threshold
- Risk Manager: APPROVED (VIX < 35, SPY not crashed, position < 10% of portfolio)

**SELL** fires only when:
- ≥ 3/4 sources bearish AND you actually hold the stock in Alpaca

**HOLD** — everything else (conflict, low conviction, portfolio limit hit)

---

## Portfolio Analytics

Visit `/analytics` for dashboard:
- Portfolio equity chart (1W / 1M / 3M)
- Open positions with unrealized P&L
- Trade history with BUY/SELL tags
- Win rate, total return, trade count
