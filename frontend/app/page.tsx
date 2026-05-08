'use client';

import { useState, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ── Types ─────────────────────────────────────────────────────────────────────

type NodeStatus = 'idle' | 'running' | 'complete';

interface NodeState {
  id: string;
  label: string;
  icon: string;
  status: NodeStatus;
  message: string;
}

interface AgentResult {
  ticker: string;
  signal: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  analysis_time_ms: number;
  technical_analyst: { rsi: number; macd_signal: string; regime: string; chart_pattern: string };
  macro_context: { vix: number; risk_environment: string; fed_stance: string };
  risk_manager: { decision: string; adjusted_size: number; stop_loss_price: number };
  portfolio_manager: { bull_case: string; bear_case: string; resolution: string };
  critic: { decision: string; flags: string[]; agent_agreement: string };
  trade_executed: { shares: number; stop_loss: number; order_id: string; broker: string } | null;
  news_analyst: {
    sentiment_label: string;
    sentiment_score: number;
    headline_count: number;
    breakdown: Record<string, number>;
    financial_news:   { decision: string; sentiment_score: number; keywords: string[]; reasoning: string; headline_count: number } | null;
    reddit:           { decision: string; sentiment_score: number; keywords: string[]; reasoning: string; post_count: number } | null;
    sec_filing:       { decision: string; sentiment_score: number; keywords: string[]; reasoning: string; filing_type: string } | null;
    analyst_ratings:  { decision: string; sentiment_score: number; keywords: string[]; reasoning: string; recommendation: string; upside_pct: number; analyst_count: number } | null;
    source_agreement: string;
  };
}

// ── Config ───────────────────────────────────────────────────────────────────

const POPULAR_TICKERS = ['NVDA', 'AAPL', 'TSLA', 'MSFT', 'AMZN', 'GOOGL', 'META', 'AMD', 'NFLX', 'SPY'];

const NODES_CONFIG = [
  { id: 'router',               label: 'Planner',              icon: '🎯' },
  { id: 'financial_news',       label: 'Financial News',       icon: '📰' },
  { id: 'reddit',               label: 'Reddit Sentiment',     icon: '💬' },
  { id: 'sec',                  label: 'SEC Filings',          icon: '📋' },
  { id: 'analyst_ratings',      label: 'Analyst Ratings',      icon: '⭐' },
  { id: 'sentiment_aggregator', label: 'Sentiment Aggregator', icon: '🧠' },
  { id: 'technical_analyst',    label: 'Technical Analyst',    icon: '📈' },
  { id: 'macro_agent',          label: 'Macro Context',        icon: '🌐' },
  { id: 'risk_manager',         label: 'Risk Manager',         icon: '🛡️' },
  { id: 'portfolio_manager',    label: 'Portfolio Manager',    icon: '💼' },
  { id: 'critic',               label: 'Critic Agent',         icon: '🔍' },
  { id: 'execution',            label: 'Execution',            icon: '⚡' },
];

// Which nodes start running after each node completes
const NEXT_NODES: Record<string, string[]> = {
  router:               ['financial_news', 'reddit', 'sec', 'analyst_ratings', 'technical_analyst', 'macro_agent'],
  financial_news:       [],
  reddit:               [],
  sec:                  [],
  analyst_ratings:      [],
  sentiment_aggregator: [],
  technical_analyst:    [],
  macro_agent:          [],
  risk_manager:         ['portfolio_manager'],
  portfolio_manager:    ['critic'],
  critic:               ['execution'],
  execution:            [],
};

// After all 4 complete, start sentiment_aggregator; after aggregator + tech + macro, start risk_manager
const NEWS_PARALLEL   = new Set(['financial_news', 'reddit', 'sec', 'analyst_ratings']);
const RISK_PREREQS    = new Set(['sentiment_aggregator', 'technical_analyst', 'macro_agent']);

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

function makeNodes(): NodeState[] {
  return NODES_CONFIG.map(n => ({ ...n, status: 'idle', message: '' }));
}

// ── Node Card ─────────────────────────────────────────────────────────────────

function NodeCard({ node }: { node: NodeState }) {
  const isRunning  = node.status === 'running';
  const isComplete = node.status === 'complete';
  const isIdle     = node.status === 'idle';

  return (
    <motion.div
      animate={{ opacity: isIdle ? 0.4 : 1, scale: isRunning ? 1.03 : 1 }}
      transition={{ duration: 0.25 }}
      className={[
        'rounded-xl border px-4 py-3 w-full',
        isIdle     && 'bg-slate-900 border-slate-800',
        isRunning  && 'bg-blue-950 border-blue-500 node-running',
        isComplete && 'bg-slate-900 border-green-700',
      ].filter(Boolean).join(' ')}
    >
      <div className="flex items-center gap-2">
        <span className="text-base leading-none">{node.icon}</span>
        <span className="text-sm font-semibold text-slate-200">{node.label}</span>
        <div className="ml-auto">
          {isRunning  && <span className="spinner" />}
          {isComplete && <span className="text-green-400 text-sm font-bold">✓</span>}
        </div>
      </div>
      <AnimatePresence>
        {isComplete && node.message && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-1.5 text-xs text-slate-400 leading-relaxed line-clamp-2 overflow-hidden"
          >
            {node.message.replace(/\[.*?\]\s*/g, '')}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

function VLine({ active }: { active: boolean }) {
  return (
    <div className="flex justify-center my-1">
      <motion.div
        animate={{ backgroundColor: active ? '#22c55e' : '#1e293b' }}
        transition={{ duration: 0.4 }}
        className="w-px h-5"
      />
    </div>
  );
}

// ── Workflow Graph ─────────────────────────────────────────────────────────────

function AgentWorkflow({ nodes }: { nodes: NodeState[] }) {
  const get  = (id: string) => nodes.find(n => n.id === id)!;
  const done = (id: string) => get(id).status === 'complete';

  const newsDone = done('financial_news') && done('reddit') && done('sec') && done('analyst_ratings');
  const riskReady = done('sentiment_aggregator') && done('technical_analyst') && done('macro_agent');

  return (
    <div className="w-full space-y-0">

      {/* Planner */}
      <NodeCard node={get('router')} />
      <VLine active={done('router')} />

      {/* 4 parallel news agents */}
      <div className="grid grid-cols-2 gap-2">
        <NodeCard node={get('financial_news')} />
        <NodeCard node={get('reddit')} />
        <NodeCard node={get('sec')} />
        <NodeCard node={get('analyst_ratings')} />
      </div>
      <VLine active={newsDone} />

      {/* Sentiment Aggregator */}
      <NodeCard node={get('sentiment_aggregator')} />

      {/* Fan-in with Technical + Macro */}
      <div className="grid grid-cols-2 gap-2 mt-2">
        <NodeCard node={get('technical_analyst')} />
        <NodeCard node={get('macro_agent')} />
      </div>
      <VLine active={riskReady} />

      {/* Sequential decision tier */}
      {(['risk_manager', 'portfolio_manager', 'critic', 'execution'] as const).map((id, i) => (
        <div key={id}>
          <NodeCard node={get(id)} />
          {i < 3 && <VLine active={done(id)} />}
        </div>
      ))}
    </div>
  );
}

// ── Source Cards ───────────────────────────────────────────────────────────────

function SourceCard({ label, score, decision, keywords, reasoning }: {
  label: string; score: number; decision: string; keywords: string[]; reasoning: string;
}) {
  const color = decision === 'bullish' ? 'border-green-700 bg-green-950/30'
    : decision === 'bearish' ? 'border-red-700 bg-red-950/30'
    : 'border-slate-700 bg-slate-900';
  const textColor = decision === 'bullish' ? 'text-green-400'
    : decision === 'bearish' ? 'text-red-400'
    : 'text-slate-400';

  return (
    <div className={`rounded-xl border p-3 ${color}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-semibold text-slate-300">{label}</span>
        <span className={`text-xs font-bold ${textColor}`}>{decision.toUpperCase()} · {score.toFixed(2)}</span>
      </div>
      {keywords.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-1">
          {keywords.slice(0, 4).map(k => (
            <span key={k} className="text-xs bg-slate-800 text-slate-400 rounded px-1.5 py-0.5">{k}</span>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{reasoning}</p>
    </div>
  );
}

// ── Result Card ───────────────────────────────────────────────────────────────

function ResultCard({ result }: { result: AgentResult }) {
  const color = {
    BUY:  { border: 'border-green-500',  bg: 'bg-green-950',  text: 'text-green-400'  },
    SELL: { border: 'border-red-500',    bg: 'bg-red-950',    text: 'text-red-400'    },
    HOLD: { border: 'border-yellow-500', bg: 'bg-yellow-950', text: 'text-yellow-400' },
  }[result.signal];

  const news = result.news_analyst;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="mt-8 space-y-3"
    >
      {/* Signal Banner */}
      <div className={`rounded-2xl border-2 p-6 text-center ${color.border} ${color.bg}`}>
        <div className={`text-6xl font-black ${color.text}`}>{result.signal}</div>
        <div className="text-slate-300 mt-1 text-lg">{result.ticker} · {(result.confidence * 100).toFixed(0)}% confidence</div>
        <div className="text-slate-500 text-xs mt-1">{(result.analysis_time_ms / 1000).toFixed(1)}s · {result.trade_executed?.broker ?? 'paper'}</div>
      </div>

      {/* News Sources Breakdown */}
      <div>
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Today&apos;s Sentiment by Source</div>
        <div className="grid grid-cols-2 gap-2">
          {news.financial_news && (
            <SourceCard label="Financial News" score={news.financial_news.sentiment_score}
              decision={news.financial_news.decision} keywords={news.financial_news.keywords}
              reasoning={news.financial_news.reasoning} />
          )}
          {news.reddit && (
            <SourceCard label="Reddit" score={news.reddit.sentiment_score}
              decision={news.reddit.decision} keywords={news.reddit.keywords}
              reasoning={news.reddit.reasoning} />
          )}
          {news.sec_filing && (
            <SourceCard label={`SEC · ${news.sec_filing.filing_type}`} score={news.sec_filing.sentiment_score}
              decision={news.sec_filing.decision} keywords={news.sec_filing.keywords}
              reasoning={news.sec_filing.reasoning} />
          )}
          {news.analyst_ratings && (
            <SourceCard label="Analyst Ratings" score={news.analyst_ratings.sentiment_score}
              decision={news.analyst_ratings.decision} keywords={news.analyst_ratings.keywords}
              reasoning={news.analyst_ratings.reasoning} />
          )}
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
          <span>Aggregated: <span className="text-white font-semibold">{news.sentiment_label} ({news.sentiment_score.toFixed(2)})</span></span>
          <span>·</span>
          <span>Agreement: <span className="text-slate-300">{news.source_agreement.replace('_', ' ')}</span></span>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatBox title="Technical">
          <Row k="RSI"     v={result.technical_analyst.rsi.toFixed(1)} />
          <Row k="MACD"    v={result.technical_analyst.macd_signal} />
          <Row k="Regime"  v={result.technical_analyst.regime} />
          <Row k="Pattern" v={result.technical_analyst.chart_pattern} truncate />
        </StatBox>
        <StatBox title="Macro">
          <Row k="VIX"         v={result.macro_context.vix.toFixed(2)} />
          <Row k="Environment" v={result.macro_context.risk_environment} />
          <Row k="Fed"         v={result.macro_context.fed_stance} />
        </StatBox>
        <StatBox title="Risk">
          <Row k="Decision" v={result.risk_manager.decision}
               color={result.risk_manager.decision === 'APPROVED' ? 'text-green-400' : 'text-red-400'} />
          <Row k="Shares"   v={String(result.risk_manager.adjusted_size)} />
          <Row k="Stop"     v={`$${result.risk_manager.stop_loss_price.toFixed(2)}`} />
        </StatBox>
        <StatBox title="Critic">
          <Row k="Decision"  v={result.critic.decision}
               color={result.critic.decision === 'PROCEED' ? 'text-green-400' : 'text-red-400'} />
          <Row k="Agreement" v={result.critic.agent_agreement} />
          {result.critic.flags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {result.critic.flags.slice(0, 2).map(f => (
                <span key={f} className="text-xs bg-yellow-900/40 text-yellow-400 border border-yellow-800 rounded px-1.5 py-0.5 leading-tight">{f}</span>
              ))}
            </div>
          )}
        </StatBox>
      </div>

      {/* Portfolio Manager Reasoning */}
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 space-y-2">
        <div className="text-xs text-slate-500 uppercase tracking-wider">Portfolio Manager Reasoning</div>
        <p className="text-sm text-slate-300 leading-relaxed">
          <span className="text-green-400 font-semibold">Bull · </span>{result.portfolio_manager.bull_case}
        </p>
        <p className="text-sm text-slate-300 leading-relaxed">
          <span className="text-red-400 font-semibold">Bear · </span>{result.portfolio_manager.bear_case}
        </p>
        <p className="text-sm text-slate-500 italic">{result.portfolio_manager.resolution}</p>
      </div>

      {/* Execution */}
      {result.trade_executed && (
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">Execution</div>
          <div className="flex gap-6 text-sm">
            <div><span className="text-slate-400">Shares </span><span className="font-mono">{result.trade_executed.shares}</span></div>
            <div><span className="text-slate-400">Stop </span><span className="font-mono">${result.trade_executed.stop_loss.toFixed(2)}</span></div>
            <div className="text-xs text-slate-600 truncate">ID: {result.trade_executed.order_id}</div>
          </div>
        </div>
      )}
    </motion.div>
  );
}

function StatBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{title}</div>
      <div className="space-y-1 text-sm">{children}</div>
    </div>
  );
}

function Row({ k, v, color, truncate }: { k: string; v: string; color?: string; truncate?: boolean }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-slate-400 shrink-0">{k}</span>
      <span className={`${color ?? ''} ${truncate ? 'truncate text-right max-w-32' : ''} font-mono text-xs`}>{v}</span>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [ticker, setTicker]       = useState('');
  const [nodes, setNodes]         = useState<NodeState[]>(makeNodes());
  const [result, setResult]       = useState<AgentResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [started, setStarted]     = useState(false);

  const completedNews = useRef(new Set<string>());
  const completedRisk = useRef(new Set<string>());

  const analyze = useCallback((tickerOverride?: string) => {
    const t = (tickerOverride ?? ticker).trim().toUpperCase();
    if (!t || isRunning) return;

    setTicker(t);
    setNodes(makeNodes());
    setResult(null);
    setError(null);
    setIsRunning(true);
    setStarted(true);
    completedNews.current = new Set();
    completedRisk.current = new Set();

    setNodes(prev => prev.map(n => n.id === 'router' ? { ...n, status: 'running' } : n));

    const es = new EventSource(`${API_URL}/stream?ticker=${t}&days=1`);

    es.addEventListener('step', (e: MessageEvent) => {
      const { node: nodeId, message } = JSON.parse(e.data) as { node: string; message: string };

      setNodes(prev => {
        let next = prev.map(n =>
          n.id === nodeId ? { ...n, status: 'complete' as NodeStatus, message } : n
        );

        if (NEWS_PARALLEL.has(nodeId)) {
          completedNews.current.add(nodeId);
          if (completedNews.current.size === NEWS_PARALLEL.size) {
            next = next.map(n => n.id === 'sentiment_aggregator' ? { ...n, status: 'running' } : n);
          }
        } else if (RISK_PREREQS.has(nodeId)) {
          completedRisk.current.add(nodeId);
          if (completedRisk.current.size === RISK_PREREQS.size) {
            next = next.map(n => n.id === 'risk_manager' ? { ...n, status: 'running' } : n);
          }
        } else {
          const nextIds = NEXT_NODES[nodeId] ?? [];
          next = next.map(n => nextIds.includes(n.id) ? { ...n, status: 'running' } : n);
        }
        return next;
      });
    });

    es.addEventListener('result', (e: MessageEvent) => {
      setResult(JSON.parse(e.data));
      setIsRunning(false);
      es.close();
    });

    es.addEventListener('error', (e: MessageEvent) => {
      try { setError(JSON.parse(e.data).message); } catch { setError('Analysis failed.'); }
      setIsRunning(false);
      es.close();
    });

    es.onerror = () => {
      setError(`Cannot reach API at ${API_URL} — is the FastAPI server running?`);
      setIsRunning(false);
      es.close();
    };
  }, [ticker, isRunning]);

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <div className="max-w-2xl mx-auto px-4 py-10 pb-24">

        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black text-white tracking-tight">QuantSentiment</h1>
          <p className="text-slate-500 text-sm mt-1">Multi-agent AI · Today&apos;s news only · Paper trading</p>
        </div>

        {/* Popular tickers */}
        <div className="flex flex-wrap gap-2 justify-center mb-4">
          {POPULAR_TICKERS.map(t => (
            <button
              key={t}
              onClick={() => setTicker(t)}
              className={[
                'px-3 py-1.5 rounded-lg text-sm font-semibold border transition-colors',
                ticker === t
                  ? 'bg-blue-600 border-blue-500 text-white'
                  : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-slate-500',
              ].join(' ')}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Input + Analyze */}
        <div className="flex gap-2 mb-8">
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && analyze()}
            placeholder="Or type any ticker…"
            maxLength={10}
            className="flex-1 bg-slate-900 border border-slate-700 focus:border-blue-500 outline-none rounded-xl px-4 py-3 text-white placeholder-slate-600 text-sm transition-colors"
          />
          <button
            onClick={() => analyze()}
            disabled={isRunning || !ticker.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed px-6 py-3 rounded-xl font-semibold text-sm transition-colors"
          >
            {isRunning
              ? <span className="flex items-center gap-2"><span className="spinner" />Analyzing</span>
              : 'Analyze →'}
          </button>
        </div>

        {/* Error */}
        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="mb-6 p-3 bg-red-950 border border-red-700 rounded-xl text-red-400 text-sm"
            >{error}</motion.div>
          )}
        </AnimatePresence>

        {/* Workflow */}
        <AnimatePresence>
          {started && (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
              <AgentWorkflow nodes={nodes} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Result */}
        {result && <ResultCard result={result} />}

      </div>
    </main>
  );
}
