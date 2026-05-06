# QuantSentiment Agent — Final Project Map

---

## Project Identity

**Name**: QuantSentiment Agent
**Tagline**: Multi-agent AI system for financial reasoning — built on LangGraph, deployed on AWS
**Type**: Multi-agent LangGraph system, cloud-deployed on AWS, accessible via MCP

### Positioning (Critical)
```
WRONG frame:  "I built a trading system"
RIGHT frame:  "Multi-agent AI engineering applied to financial reasoning"

The agentic architecture is the headline.
Finance is the domain.
Recruiter should think: "AI engineer who ships multi-agent systems in hard domains."
```

---

## Two Stacks — Same Codebase, Config-Only Swap

```
COMPONENT              FREE TIER STACK              UPGRADE STACK (Bedrock+SageMaker)
──────────────────────────────────────────────────────────────────────────────────────
LLM Reasoning          Groq (Llama 3.1 70B)         AWS Bedrock (Claude 3.5 Sonnet)
Chart Vision           Groq (Llama 3.2 Vision)       AWS Bedrock (Claude 3.5 Sonnet)
                       ↑ same Groq client             ↑ same Bedrock client — both in one
FinBERT Hosting        HuggingFace Spaces (CPU)       AWS SageMaker Endpoint
Embeddings             HuggingFace sentence-xfmrs     AWS Bedrock Titan Embeddings
App Server             AWS EC2 t2.micro               AWS ECS Fargate
Vector DB              Pinecone free (100K vecs)       Pinecone (same — stronger keyword)

UNCHANGED IN BOTH:
  LangGraph · LangChain · Pinecone · FastAPI · MCP Server
  AWS Lambda · AWS S3 · AWS EventBridge · AWS ECR · AWS CloudWatch
  GitHub Actions · Alpaca Paper API · Tavily · yfinance · SEC EDGAR
  LangSmith · nginx (replaces API Gateway in both)

REMOVED FROM BOTH:
  API Gateway  → nginx on server handles HTTPS routing
  NewsAPI      → Tavily covers this (purpose-built for agents)
  HF BLIP      → vision handled by Groq / Bedrock (same client, no extra model)
```

---

## Architecture — Free Tier

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          USER / CLIENT                                   │
│        curl · frontend · Claude Desktop (via MCP) · Postman            │
└──────────────────────────────┬───────────────────────────────────────────┘
                               ↓  HTTPS via nginx
┌──────────────────────────────────────────────────────────────────────────┐
│              AWS EC2 t2.micro  [FREE 750hr/mo]                           │
│     FastAPI (SSE) + LangGraph agent runtime + MCP Server + nginx        │
│                         Docker container                                 │
└──┬──────────────┬─────────────┬──────────────┬───────────────────────────┘
   ↓              ↓             ↓              ↓
┌──────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐
│Groq  │  │HuggingFace│  │Pinecone  │  │ Tavily   │  │ Alpaca  │
│API   │  │Spaces     │  │free tier │  │ (news)   │  │ Paper   │
│text +│  │FinBERT    │  │2 namespac│  │          │  │ Trading │
│vision│  │(fine-tuned│  │news + SEC│  │          │  │         │
└──────┘  └───────────┘  └──────────┘  └──────────┘  └─────────┘
                               ↑
┌──────────────────────────────────────────────────────────────────────────┐
│                   AWS S3  [FREE 5GB, 12mo]                               │
│   /news-data/ · /sec-filings/ · /charts/ · /paper-trading-logs/        │
└─────────────────────────────┬────────────────────────────────────────────┘
                              ↑
┌──────────────────────────────────────────────────────────────────────────┐
│              AWS Lambda + EventBridge  [FREE always]                     │
│   1. nightly-news:    Tavily → HF embed → Pinecone (news namespace)     │
│   2. sec-ingestion:   EDGAR → HF embed → Pinecone (sec namespace)       │
│   3. portfolio-track: Alpaca P&L → S3  (every 15min, market hours)     │
└──────────────────────────────────────────────────────────────────────────┘
       GitHub → GitHub Actions → ECR → EC2 rolling deploy
```

---

## Architecture — Upgrade (Bedrock + SageMaker)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          USER / CLIENT                                   │
│        curl · frontend · Claude Desktop (via MCP) · Postman            │
└──────────────────────────────┬───────────────────────────────────────────┘
                               ↓  HTTPS via ALB
┌──────────────────────────────────────────────────────────────────────────┐
│                 AWS ECS Fargate                                          │
│     FastAPI (SSE) + LangGraph agent runtime + MCP Server                │
│                         Docker container                                 │
└──┬──────────────┬─────────────┬──────────────┬───────────────────────────┘
   ↓              ↓             ↓              ↓
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  ┌─────────┐
│ Bedrock  │ │SageMaker │ │Pinecone  │ │ Tavily   │  │ Alpaca  │
│Claude 3.5│ │FinBERT   │ │(same)    │ │ (news)   │  │ Paper   │
│text +    │ │Endpoint  │ │2 namespac│ │          │  │ Trading │
│vision    │ │          │ │news + SEC│ │          │  │         │
└──────────┘ └──────────┘ └──────────┘ └──────────┘  └─────────┘
                               ↑
┌──────────────────────────────────────────────────────────────────────────┐
│                          AWS S3                                          │
│   /news-data/ · /sec-filings/ · /charts/ · /paper-trading-logs/        │
└─────────────────────────────┬────────────────────────────────────────────┘
                              ↑
┌──────────────────────────────────────────────────────────────────────────┐
│              AWS Lambda + EventBridge                                    │
│   1. nightly-news:    Tavily → Bedrock Titan embed → Pinecone           │
│   2. sec-ingestion:   EDGAR → Bedrock Titan embed → Pinecone            │
│   3. portfolio-track: Alpaca P&L → S3                                   │
└──────────────────────────────────────────────────────────────────────────┘
       GitHub → GitHub Actions → ECR → ECS Fargate rolling deploy
```

---

## Multi-Agent Graph (LangGraph — identical in both stacks)

### Agent Roster

```
ANALYSIS TIER (parallel)
  News Analyst Agent       Tavily + FinBERT + dual RAG (news + SEC)
  Technical Analyst Agent  RSI, MACD, Bollinger + chart vision
  Macro Context Agent      VIX, rates, Fed, sector rotation

DECISION TIER (sequential)
  Risk Manager Agent       position sizing, stop-loss, hard veto
  Portfolio Manager Agent  bull/bear synthesis, final signal
  Critic Agent             reflection loop, HOLD override

EXECUTION TIER
  Execution Agent          Alpaca paper trade or log HOLD
```

### Graph Flow

```
                          [START]
                             │
                      user query + ticker
                             │
                   ┌─────────▼──────────┐
                   │    router node      │  ← LLM decides workflow
                   └──┬─────────────────┘
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
┌───────────────┐ ┌─────────────┐ ┌──────────────────┐
│ News Analyst  │ │  Technical  │ │  Macro Context   │
│               │ │  Analyst    │ │                  │
│ • Tavily news │ │             │ │ • VIX level      │
│ • FinBERT     │ │ • RSI, MACD │ │ • Fed stance     │
│ • News RAG    │ │ • Bollinger │ │ • Sector flows   │
│ • SEC RAG     │ │ • Chart gen │ │ • 10yr yield     │
│ • Confidence  │ │ • Vision AI │ │ • CPI context    │
└───────┬───────┘ └──────┬──────┘ └────────┬─────────┘
        └────────────────┼─────────────────┘
                         ▼
               ┌──────────────────┐
               │  Risk Manager    │
               │                  │
               │ • Position size  │
               │ • Stop-loss calc │
               │ • Max exposure   │
               │ → APPROVE / VETO │  ← hard veto, cannot be overridden
               └────────┬─────────┘
                        ▼
               ┌──────────────────┐
               │ Portfolio Mgr    │
               │                  │
               │ • Bull case      │
               │ • Bear case      │
               │ • Resolve signal │
               │ → BUY/SELL/HOLD  │
               └────────┬─────────┘
                        ▼
               ┌──────────────────┐
               │  Critic Agent    │  ← reflection loop
               │                  │
               │ • Confidence>0.65│
               │ • 2+/3 agree?    │
               │ • Red flags?     │
               │ → PROCEED / HOLD │
               └────────┬─────────┘
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
  ┌──────────────────┐    ┌──────────────────┐
  │ Execution Agent  │    │ HOLD — log reason│
  │ Alpaca paper     │    │ to S3, no trade  │
  └────────┬─────────┘    └────────┬─────────┘
           └──────────┬────────────┘
                      ▼
             ┌──────────────────┐
             │    formatter     │  → SSE + JSON
             └────────┬─────────┘
                      ▼
                    [END]
```

---

## Agent Descriptions

### News Analyst Agent
- Fetches last 48h headlines via Tavily
- Runs headlines through fine-tuned FinBERT (HuggingFace Spaces / SageMaker)
- Retrieves similar historical news from Pinecone (news namespace)
- Searches relevant SEC filings from Pinecone (sec namespace)
- Outputs: sentiment score, confidence, headline count, historical analogues

### Technical Analyst Agent
- Fetches OHLCV data via yfinance (1y lookback)
- Computes RSI (14-period), MACD, Bollinger Bands
- Identifies market regime: trending / ranging / volatile
- Generates candlestick chart → sends to LLM vision → extracts pattern
- Outputs: RSI, MACD signal, chart pattern, regime label

### Macro Context Agent
- Pulls VIX, 10-year treasury yield via yfinance
- Checks Fed meeting dates and most recent decision
- Assesses sector rotation and risk-on/risk-off environment
- Outputs: macro score, rate environment, risk signal

### Risk Manager Agent
- Enforces max 10% single-stock exposure, stop-loss at -5%
- Checks correlation with existing paper positions
- Issues APPROVE (with adjusted size) or VETO (with reason)
- **VETO is hard — Portfolio Manager cannot override**

### Portfolio Manager Agent
- Receives all three analysis outputs
- Constructs explicit bull case and bear case
- Resolves conflicts with a scoring mechanism
- Outputs: BUY / SELL / HOLD, confidence 0–1

### Critic Agent
- Checks: confidence > 0.65, at least 2/3 analysis agents agree
- Flags: thin news coverage, extreme VIX, pre-earnings risk
- If flagged → overrides to HOLD, logs reason to S3
- Prevents overconfident trades — what separates an engineered system from a toy

---

## Honest Metrics Framework

```
SHOW THESE                                    DROP THESE
──────────────────────────────────────────────────────────────────────
✓ Sharpe ratio                               ✗ Raw % return
✓ Max drawdown                               ✗ "26% backtested gain"
✓ Walk-forward validation                    ✗ In-sample only
✓ Out-of-sample vs in-sample split           ✗ Unqualified backtest claims
✓ Buy-and-hold baseline comparison
✓ Realistic transaction costs (Alpaca model)
✓ Agent disagreement rate
✓ Critic Agent veto rate
✓ Confidence calibration score
✓ 30–60 day live Alpaca paper trading results
```

Live paper trading with honest modest results is more credible than
any backtest number. Run it, report it honestly.

---

## Streaming Response (SSE)

```
→ [Router]         Planning workflow for NVDA...                ✓
→ [News Analyst]   Fetching headlines (48h)...                  ✓  (9 found)
→ [News Analyst]   Running FinBERT...                           ✓  (avg: 0.79 pos)
→ [News Analyst]   Searching news RAG...                        ✓  (top 3)
→ [News Analyst]   Searching SEC filings...                     ✓  (Q4 2024 10-Q)
→ [Tech Analyst]   RSI: 42.3 · MACD: bullish cross             ✓
→ [Tech Analyst]   Analyzing chart pattern...                   ✓  (ascending tri.)
→ [Macro Agent]    VIX: 18.2 · yield: 4.3% · risk-on           ✓
→ [Risk Manager]   Checking exposure limits...                  ✓  APPROVED (80 sh)
→ [Portfolio Mgr]  Bull / Bear synthesis...                     ✓  BUY @ 0.79
→ [Critic]         Confidence: 0.79 ✓ · Agreement: 3/3 ✓       ✓  PROCEED
→ [Execution]      Placing paper trade via Alpaca...            ✓  80sh @ $127.40

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SIGNAL:     BUY
CONFIDENCE: 0.79
SHARES:     80  (risk-adjusted)
PRICE:      $127.40
STOP-LOSS:  $121.03  (-5%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Agent Output Schema

```json
{
  "ticker": "NVDA",
  "signal": "BUY",
  "confidence": 0.79,
  "news_analyst": {
    "sentiment_score": 0.79,
    "label": "positive",
    "headlines_analyzed": 9,
    "similar_past_events": [
      {"date": "2024-05-22", "event": "earnings beat", "outcome": "+12% in 5d"}
    ],
    "sec_context": "Q4 2024: data center revenue +40% YoY, guidance raised"
  },
  "technical_analyst": {
    "rsi": 42.3,
    "macd": "bullish_crossover",
    "chart_pattern": "ascending_triangle",
    "regime": "trending_up",
    "bollinger": "mid_band"
  },
  "macro_context": {
    "vix": 18.2,
    "fed_stance": "neutral",
    "yield_10yr": 4.3,
    "risk_environment": "risk_on"
  },
  "risk_manager": {
    "decision": "APPROVED",
    "original_size": 100,
    "adjusted_size": 80,
    "stop_loss_price": 121.03,
    "reason": "Adjusted: portfolio already 8% tech exposure"
  },
  "portfolio_manager": {
    "bull_case": "Strong earnings, oversold RSI, bullish chart pattern...",
    "bear_case": "Stretched valuation at 35x forward P/E...",
    "resolution": "Bull case outweighs on technical + sentiment confluence"
  },
  "critic": {
    "decision": "PROCEED",
    "confidence_check": true,
    "agent_agreement": "3/3",
    "flags": [],
    "veto_reason": null
  },
  "trade_executed": {
    "broker": "alpaca_paper",
    "action": "buy",
    "shares": 80,
    "price": 127.40,
    "stop_loss": 121.03,
    "order_id": "abc-123"
  },
  "metrics": {
    "analysis_time_ms": 4230,
    "agents_run": 6,
    "tools_called": 11
  },
  "timestamp": "2026-05-05T10:30:00Z"
}
```

---

## Data Pipelines

### Ingestion (Lambda + EventBridge)

```
PIPELINE 1 — Nightly News  (11pm daily)
  Tavily → raw headlines
  → clean + chunk
  → embed: HF sentence-transformers (free) OR Bedrock Titan (upgrade)
  → upsert Pinecone (namespace: news-YYYY-MM-DD)
  → archive to S3

PIPELINE 2 — SEC Filings  (Sunday weekly)
  SEC EDGAR → 10-K, 10-Q, earnings transcripts
  → parse + chunk by section
  → embed: HF sentence-transformers OR Bedrock Titan
  → upsert Pinecone (namespace: sec-filings)
  → archive to S3

PIPELINE 3 — Portfolio Tracker  (every 15min, market hours)
  Alpaca API → positions, P&L, trade history
  → log to S3
  → expose via GET /portfolio
```

### Inference (Real-time)
```
User query → LangGraph (EC2 or Fargate)
  → Analysis Tier (parallel)
  → Decision Tier (sequential)
  → Execution Tier
  → SSE stream each step → full JSON on completion
```

---

## MCP Server

```
Tools exposed to Claude Desktop:
  get_news_sentiment(ticker, days)    → FinBERT scores + summaries
  get_technicals(ticker)              → RSI, MACD, regime
  get_macro_context()                 → VIX, rates, Fed
  search_sec_filings(ticker, query)   → RAG over 10-K/10-Q
  get_risk_assessment(ticker, size)   → position sizing + stop-loss
  get_portfolio()                     → live Alpaca positions + P&L
  full_analysis(ticker)               → run entire 6-agent graph
```

---

## Project Folder Structure

```
QuantSentiment/
│
├── agent/
│   ├── graph.py                      ← LangGraph stateful graph
│   ├── state.py                      ← AgentState TypedDict
│   ├── nodes/
│   │   ├── router.py
│   │   ├── news_analyst.py           ← Tavily + FinBERT + RAG
│   │   ├── technical_analyst.py      ← RSI, MACD, chart, vision
│   │   ├── macro_agent.py            ← VIX, rates, Fed
│   │   ├── risk_manager.py           ← position sizing, veto
│   │   ├── portfolio_manager.py      ← bull/bear synthesis
│   │   ├── critic.py                 ← reflection loop
│   │   ├── execution.py              ← Alpaca trade
│   │   └── formatter.py              ← output + SSE events
│   ├── tools/
│   │   ├── llm_client.py             ← Groq OR Bedrock (env-var swap)
│   │   ├── finbert_tool.py           ← HF Spaces OR SageMaker (env-var swap)
│   │   ├── embedder.py               ← HF sentence-xfmrs OR Bedrock Titan
│   │   ├── tavily_tool.py
│   │   ├── yfinance_tool.py
│   │   ├── sec_edgar_tool.py
│   │   ├── pinecone_tool.py
│   │   ├── chart_tool.py             ← matplotlib → vision via llm_client
│   │   └── alpaca_tool.py
│   ├── memory.py
│   └── schemas.py                    ← Pydantic I/O models
│
├── api/
│   ├── main.py                       ← FastAPI app
│   ├── routes/
│   │   ├── ask.py                    ← POST /ask
│   │   ├── stream.py                 ← GET /stream (SSE)
│   │   └── portfolio.py              ← GET /portfolio
│   └── sse.py
│
├── mcp/
│   ├── server.py
│   └── tools.py
│
├── ingestion/
│   ├── news_lambda.py
│   ├── sec_lambda.py
│   ├── portfolio_lambda.py
│   └── cleaner.py
│
├── evaluation/
│   ├── backtest.py                   ← walk-forward engine
│   ├── metrics.py                    ← Sharpe, drawdown, baseline
│   └── paper_trade_report.py         ← 30-60 day live results
│
├── infra/
│   ├── Dockerfile
│   ├── nginx.conf                    ← HTTPS routing (replaces API Gateway)
│   ├── ec2-setup.sh                  ← free tier bootstrap
│   ├── sagemaker_deploy.py           ← upgrade: deploy FinBERT to SageMaker
│   └── eventbridge-rules.json
│
├── .github/
│   └── workflows/
│       └── deploy.yml                ← GitHub Actions: test → ECR → deploy
│
├── .env.example
│   ── STACK=free           # or: STACK=bedrock
│   ── GROQ_API_KEY=
│   ── BEDROCK_REGION=
│   ── SAGEMAKER_ENDPOINT=
│   ── HF_SPACES_URL=
│   ── PINECONE_API_KEY=
│   ── TAVILY_API_KEY=
│   ── ALPACA_API_KEY=
│
├── Data/dataset.csv
├── Final/my-finbert-finetuned.zip
├── requirements.txt
└── PROJECT_MAP.md
```

---

## CI/CD Pipeline

### Free Tier (GitHub Actions → EC2)
```
push to main
  → pytest
  → docker build
  → push to ECR
  → SSH to EC2 → docker pull → restart container
  → health check GET /health
  → smoke test POST /ask {"ticker":"AAPL"}
```

### Upgrade (GitHub Actions → ECS Fargate)
```
push to main
  → pytest
  → docker build
  → push to ECR
  → ecs update-service --force-new-deployment
  → health check via ALB
  → smoke test
```

---

## Build Phases

| Phase | What | Free Tier | Upgrade |
|-------|------|-----------|---------|
| **1** | FinBERT model hosting | HuggingFace Spaces | SageMaker Endpoint |
| **2** | Core tools (Tavily, yfinance, SEC, Alpaca) | Same | Same |
| **3** | Analysis Tier (3 agents) | Groq | Bedrock Claude |
| **4** | Pinecone RAG + Lambda ingestion | HF embeddings | Bedrock Titan embed |
| **5** | Decision Tier (Risk + Portfolio agents) | Groq | Bedrock Claude |
| **6** | Critic Agent + reflection loop | Same | Same |
| **7** | Chart vision + SSE streaming | Groq Vision | Bedrock Claude Vision |
| **8** | Serve + Docker + deploy (live URL) | EC2 + nginx | ECS Fargate + ALB |
| **9** | MCP Server + GitHub Actions CI/CD | Same | Same |
| **10** | LangSmith + CloudWatch + metrics | Same | Same |
| **11** | 30-day live paper trading run | Alpaca (free) | Alpaca (free) |

**Total build: ~3 weeks · Paper trading: parallel from Phase 7**

---

## Free Tier Limits

| Service | Limit | Risk |
|---|---|---|
| Groq API | 14,400 req/day · 30 req/min | Low — cache repeated tickers |
| HuggingFace Spaces | CPU free, ~10s cold start | Low |
| Pinecone free | 100K vectors · 1 index | Low — both namespaces fit |
| Tavily | 1,000 req/month | Medium — cache aggressively |
| AWS Lambda | 1M req/mo · 400K GB-sec | Very low |
| AWS S3 | 5GB · 20K GET · 2K PUT (12mo) | Low |
| AWS EC2 t2.micro | 750hr/mo = 1 instance 24/7 (12mo) | Fine |
| LangSmith | 5,000 traces/month | Medium — disable in prod |
| GitHub Actions | 2,000 min/month (private) | Low |
| Alpaca Paper | Unlimited | None |
| SEC EDGAR | Unlimited (10 req/sec) | None |

---

## Resume Lines

### Free Tier Version
```latex
\textbf{Tech Stack: Python, LangGraph, LangChain, Groq API (LLM + Vision),
HuggingFace, Pinecone, FastAPI, AWS (EC2 · Lambda · S3 · EventBridge),
Docker, GitHub Actions, MCP, Alpaca, Tavily, yfinance, SEC EDGAR}
```

### Upgrade Version (Bedrock + SageMaker)
```latex
\textbf{Tech Stack: Python, LangGraph, LangChain, AWS Bedrock (Claude 3.5),
AWS SageMaker, Pinecone, FastAPI, AWS (ECS Fargate · Lambda · S3 · EventBridge),
Docker, GitHub Actions, MCP, Alpaca, Tavily, yfinance, SEC EDGAR}
```

---

## Full Keyword Coverage

```
AI Engineering    LangGraph · Multi-agent · ReAct · Reflection / Critic pattern
                  Dual RAG (news + SEC) · Vector DB · Fine-tuned LLM
                  Multi-modal vision · MCP Server · SSE streaming · Tool calling

AWS Free Tier     EC2 · Lambda · S3 · EventBridge · ECR · CloudWatch
AWS Upgrade       Bedrock · SageMaker · ECS Fargate (swap when credits available)

DevOps            Docker · GitHub Actions · CI/CD · nginx · Rolling deploys

Finance Domain    FinBERT · RSI · MACD · Sharpe ratio · Walk-forward validation
                  Alpaca paper trading · SEC EDGAR · Live P&L tracking
                  Risk management (hard veto, position sizing, stop-loss)
```
