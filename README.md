# QuantSentiment — Multi-Agent AI Trading System

A production-grade multi-agent AI system that analyses stock sentiment from 5 independent sources and makes paper trading decisions via Alpaca. Built on **LangGraph**, powered by **Groq (Llama 3.3 70B)** and a **fine-tuned FinBERT** model.

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
                                     (awaits user confirmation button)
                                                      │
                                                      ▼
                                            Alpaca Paper Trading
                                          (only fires on user click)
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
| **Execution** | Surfaces recommendation to UI; user clicks Confirm to place order | Alpaca Paper API |

---

## Tech Stack

```
LLM Reasoning     Groq — Llama 3.3 70B (free tier)
Sentiment Model   Fine-tuned FinBERT (Dipen0210/finbert-finetuned on HuggingFace Hub)
Agent Framework   LangGraph + LangChain
Observability     LangSmith (traces every node run)
Vector Store      Pinecone — macro trend history (VIX, risk env, sentiment)
News Fetch        Tavily Search API
Market Data       yfinance — VIX, 10yr yield, SPY, DXY, stock prices
SEC Data          SEC EDGAR API
Paper Trading     Alpaca Paper Trading API
Backend           FastAPI + SSE streaming
Frontend          Next.js 16 + Tailwind CSS + Framer Motion + Recharts
MCP Server        FastMCP — Claude Desktop integration (analyze, get_analytics)
Deployment        Docker + AWS ECR + EC2 + GitHub Actions CI/CD
```

---

## Features

- **Real-time SSE streaming** — watch each agent complete live in the browser
- **Fine-tuned FinBERT** — custom financial sentiment model (`Dipen0210/finbert-finetuned`)
- **Pinecone macro memory** — tracks 14-day VIX trend and consecutive risk-off days
- **Groq → FinBERT pipeline for SEC filings** — LLM extracts readable sentences from raw XBRL, then FinBERT scores them
- **Portfolio analytics dashboard** — equity chart, open positions, trade history, win rate (Robinhood-style)
- **Manual trade confirmation** — agent recommends the trade; user clicks Confirm to actually place it
- **Smart SELL** — checks actual Alpaca holdings before selling, uses `min(adjusted_size, held_qty)`
- **Portfolio concentration guard** — max 10% in any single stock
- **LangSmith tracing** — full observability on every agent run
- **MCP server** — ask Claude Desktop to analyze a stock or pull analytics directly

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
│   ├── execution/              # Surfaces trade for user confirmation
│   └── formatter/              # Response assembly
└── tools/
    ├── finbert_tool.py         # Fine-tuned FinBERT (HuggingFace Hub)
    ├── tavily_tool.py          # News search (excludes price/quote pages)
    ├── yfinance_tool.py        # Market indices + prices
    ├── sec_edgar_tool.py       # EDGAR filing fetch + content download
    ├── pinecone_tool.py        # Macro trend store
    ├── alpaca_tool.py          # Paper trading orders
    ├── keywords.py             # Keyword extraction
    └── llm_client.py           # Groq LLM client

api/
├── main.py                     # FastAPI app
└── routes/
    ├── stream.py               # SSE streaming endpoint
    ├── ask.py                  # Single-shot /ask endpoint
    ├── portfolio.py            # Live positions
    ├── analytics.py            # Portfolio analytics (equity, trades, metrics)
    └── trade.py                # Manual trade placement endpoint

frontend/
└── app/
    ├── page.tsx                # Main dashboard + trade confirmation UI
    └── analytics/page.tsx      # Robinhood-style portfolio analytics

mcp_server/
├── server.py                   # FastMCP server definition
└── tools.py                    # analyze_stock + get_analytics MCP tools

huggingface/
└── my-finbert-finetuned/       # Fine-tuned FinBERT weights (also on HuggingFace Hub)

evaluation/
├── paper_trade_report.py       # Alpaca trade metrics CLI
└── metrics.py                  # Sharpe, drawdown, win rate

.github/
└── workflows/
    └── deploy.yml              # GitHub Actions: test → build → push ECR → deploy EC2
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

# Fine-tuned FinBERT (loaded from HuggingFace Hub)
FINBERT_MODEL=Dipen0210/finbert-finetuned
HF_API_TOKEN=hf_...                 # read-only HuggingFace token

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

### 3. Run locally

```bash
# Backend (terminal 1)
uvicorn api.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## Signal Logic

**BUY** fires only when:
- Portfolio Manager: ≥ 3/4 sources bullish → BUY with confidence ≥ 0.62
- Critic: agreement ≥ 3/4 AND confidence passes threshold
- Risk Manager: APPROVED (VIX < 35, SPY not crashed, position < 10% of portfolio)
- User clicks **Confirm Trade** button in the UI

**SELL** fires only when:
- ≥ 3/4 sources bearish AND you actually hold the stock in Alpaca
- User clicks **Confirm Trade** button in the UI

**HOLD** — everything else (conflict, low conviction, portfolio limit hit)

---

## Portfolio Analytics

Visit `/analytics` for the Robinhood-style dashboard:
- Portfolio equity chart (1W / 1M / 3M timeframe toggle)
- Open positions with unrealized P&L
- Trade history with BUY/SELL tags
- Win rate, total return, Sharpe ratio, trade count

---

## MCP Server (Claude Desktop)

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "quantsentiment": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/QuantSentiment",
      "env": { "API_BASE_URL": "http://localhost:8000" }
    }
  }
}
```

Available tools in Claude Desktop:
- **`analyze_stock`** — run the full 8-agent pipeline on any ticker
- **`get_analytics`** — pull live portfolio metrics, equity curve, positions, trade history

---

## Deployment (AWS EC2 via GitHub Actions)

The pipeline is fully automated: **push to `main` → GitHub Actions → Docker → EC2**.

### Architecture

```
GitHub push → GitHub Actions CI/CD
                    │
                    ├── 1. Test (smoke test imports)
                    ├── 2. Build Docker image
                    ├── 3. Push to AWS ECR
                    └── 4. SSH into EC2 → pull image → restart container
                                │
                           EC2 Instance
                           ├── Docker container (port 8000)
                           ├── Nginx reverse proxy (port 80/443)
                           └── ~/quantsentiment.env (API keys)
```

### One-time EC2 setup

> You only do this once. After this, every `git push` auto-deploys.

**1. SSH into your EC2 instance**

```bash
chmod 400 ~/Downloads/your-key.pem
ssh -i ~/Downloads/your-key.pem ec2-user@<YOUR_EC2_IP>
```

**2. Install Docker and AWS CLI**

```bash
sudo yum update -y
sudo yum install -y docker
sudo service docker start
sudo usermod -aG docker ec2-user
# Log out and back in for the group to take effect

sudo yum install -y aws-cli
```

**3. Verify**

```bash
docker --version
aws --version
```

**4. Create the env file with your API keys**

```bash
cat > ~/quantsentiment.env << 'EOF'
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
EOF
```

**5. Install and configure Nginx**

```bash
sudo yum install -y nginx
sudo systemctl enable nginx

# Create reverse proxy config
sudo tee /etc/nginx/conf.d/quantsentiment.conf << 'EOF'
server {
    listen 80;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off;           # required for SSE streaming
    }
}
EOF

sudo nginx -t && sudo systemctl start nginx
```

### GitHub Actions secrets

Set these in your repo → **Settings → Secrets and variables → Actions**:

| Secret | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user key with ECR + EC2 permissions |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret |
| `AWS_REGION` | e.g. `us-east-2` |
| `ECR_REGISTRY` | e.g. `123456789.dkr.ecr.us-east-2.amazonaws.com` |
| `EC2_HOST` | Your EC2 public IP address |
| `EC2_SSH_KEY` | Contents of your `.pem` file (the full private key text) |

### Deploy

```bash
git add .
git commit -m "your message"
git push origin main
```

GitHub Actions will automatically: test → build → push to ECR → pull on EC2 → restart container.

### Do you need Docker locally?

**No.** Docker only runs on EC2. You don't need it on your Mac for development.

- **Local dev**: `uvicorn` + `npm run dev` directly (no Docker needed)
- **Production**: Docker runs on EC2, managed entirely by GitHub Actions

---

## How a full deploy works (step by step)

```
1. You write code on your Mac
2. git push origin main
3. GitHub Actions starts automatically:
   a. Installs Python, runs: python -c "from api.main import app"
   b. Builds Docker image using your Dockerfile
   c. Pushes the image to AWS ECR (private container registry)
   d. SSHes into EC2, runs:
        docker pull <new-image>
        docker stop quantsentiment
        docker run -d --env-file ~/quantsentiment.env <new-image>
        nginx -s reload
4. Your EC2 is now running the new version
5. Users hit http://<EC2_IP> → Nginx → FastAPI container
```

The frontend (Next.js) is currently run separately on your Mac. If you want to deploy the frontend too, it can be added to a Vercel project or served from the same EC2.
