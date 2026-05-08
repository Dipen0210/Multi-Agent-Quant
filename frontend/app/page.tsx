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
  trade_executed: { shares: number; stop_loss: number; order_id: string; broker: string };
  news_analyst: { sentiment_label: string; sentiment_score: number; headline_count: number };
}

// ── Config ───────────────────────────────────────────────────────────────────

const NODES_CONFIG = [
  { id: 'router',            label: 'Planner',           icon: '🎯' },
  { id: 'news_analyst',      label: 'News Analyst',      icon: '📰' },
  { id: 'technical_analyst', label: 'Technical Analyst', icon: '📈' },
  { id: 'macro_agent',       label: 'Macro Context',     icon: '🌐' },
  { id: 'risk_manager',      label: 'Risk Manager',      icon: '🛡️' },
  { id: 'portfolio_manager', label: 'Portfolio Manager', icon: '💼' },
  { id: 'critic',            label: 'Critic Agent',      icon: '🔍' },
  { id: 'execution',         label: 'Execution',         icon: '⚡' },
];

const PARALLEL = new Set(['news_analyst', 'technical_analyst', 'macro_agent']);

const NEXT_NODES: Record<string, string[]> = {
  router:            ['news_analyst', 'technical_analyst', 'macro_agent'],
  news_analyst:      [],
  technical_analyst: [],
  macro_agent:       [],
  risk_manager:      ['portfolio_manager'],
  portfolio_manager: ['critic'],
  critic:            ['execution'],
  execution:         [],
};

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
      animate={{ opacity: isIdle ? 0.45 : 1, scale: isRunning ? 1.02 : 1 }}
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
        className="w-px h-6"
      />
    </div>
  );
}

// ── Workflow ──────────────────────────────────────────────────────────────────

function AgentWorkflow({ nodes }: { nodes: NodeState[] }) {
  const get = (id: string) => nodes.find(n => n.id === id)!;
  const done = (id: string) => get(id).status === 'complete';
  const parallelDone = done('news_analyst') && done('technical_analyst') && done('macro_agent');

  return (
    <div className="w-full">

      {/* Planner */}
      <NodeCard node={get('router')} />
      <VLine active={done('router')} />

      {/* Fan-out lines */}
      {done('router') && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex justify-center gap-0 mb-1"
        >
          <div className="flex-1 h-px bg-slate-700 mt-0 self-end" />
          <div className="flex-1 h-px bg-slate-700 mt-0 self-end" />
        </motion.div>
      )}

      {/* Parallel agents */}
      <div className="grid grid-cols-3 gap-3">
        <NodeCard node={get('news_analyst')} />
        <NodeCard node={get('technical_analyst')} />
        <NodeCard node={get('macro_agent')} />
      </div>

      {/* Fan-in */}
      <VLine active={parallelDone} />

      {/* Sequential */}
      {(['risk_manager', 'portfolio_manager', 'critic', 'execution'] as const).map((id, i) => (
        <div key={id}>
          <NodeCard node={get(id)} />
          {i < 3 && <VLine active={done(id)} />}
        </div>
      ))}
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="mt-8 space-y-3"
    >
      {/* Signal banner */}
      <div className={`rounded-2xl border-2 p-6 text-center ${color.border} ${color.bg}`}>
        <div className={`text-6xl font-black ${color.text}`}>{result.signal}</div>
        <div className="text-slate-300 mt-1">{result.ticker} · {(result.confidence * 100).toFixed(0)}% confidence</div>
        <div className="text-slate-500 text-xs mt-1">{(result.analysis_time_ms / 1000).toFixed(1)}s · {result.trade_executed.broker}</div>
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

        <StatBox title="News">
          <Row k="Sentiment" v={result.news_analyst.sentiment_label} />
          <Row k="Score"     v={result.news_analyst.sentiment_score.toFixed(2)} />
          <Row k="Headlines" v={String(result.news_analyst.headline_count)} />
        </StatBox>
      </div>

      {/* Reasoning */}
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

      {/* Critic + Execution */}
      <div className="grid grid-cols-2 gap-3">
        <StatBox title="Critic">
          <Row k="Decision"  v={result.critic.decision}
               color={result.critic.decision === 'PROCEED' ? 'text-green-400' : 'text-red-400'} />
          <Row k="Agreement" v={result.critic.agent_agreement} />
          {result.critic.flags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {result.critic.flags.map(f => (
                <span key={f} className="text-xs bg-yellow-900/40 text-yellow-400 border border-yellow-800 rounded px-1.5 py-0.5">{f}</span>
              ))}
            </div>
          )}
        </StatBox>

        <StatBox title="Execution">
          <Row k="Shares" v={String(result.trade_executed.shares)} />
          <Row k="Stop"   v={`$${result.trade_executed.stop_loss.toFixed(2)}`} />
          <p className="text-xs text-slate-600 mt-1 truncate">ID: {result.trade_executed.order_id}</p>
        </StatBox>
      </div>
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

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const [ticker, setTicker]       = useState('');
  const [nodes, setNodes]         = useState<NodeState[]>(makeNodes());
  const [result, setResult]       = useState<AgentResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [started, setStarted]     = useState(false);
  const completedParallel         = useRef(new Set<string>());

  const analyze = useCallback(() => {
    if (!ticker.trim() || isRunning) return;

    setNodes(makeNodes());
    setResult(null);
    setError(null);
    setIsRunning(true);
    setStarted(true);
    completedParallel.current = new Set();

    setNodes(prev => prev.map(n => n.id === 'router' ? { ...n, status: 'running' } : n));

    const es = new EventSource(`${API_URL}/stream?ticker=${ticker.toUpperCase()}&days=2`);

    es.addEventListener('step', (e: MessageEvent) => {
      const { node: nodeId, message } = JSON.parse(e.data) as { node: string; message: string };

      setNodes(prev => {
        let next = prev.map(n =>
          n.id === nodeId ? { ...n, status: 'complete' as NodeStatus, message } : n
        );

        if (PARALLEL.has(nodeId)) {
          completedParallel.current.add(nodeId);
          if (completedParallel.current.size === PARALLEL.size) {
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
      <div className="max-w-2xl mx-auto px-4 py-12 pb-24">

        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-3xl font-black text-white tracking-tight">QuantSentiment</h1>
          <p className="text-slate-500 text-sm mt-1">6-agent AI · News · Technical · Macro · Risk · Portfolio · Critic</p>
        </div>

        {/* Input */}
        <div className="flex gap-2 mb-8">
          <input
            type="text"
            value={ticker}
            onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && analyze()}
            placeholder="Ticker — NVDA, AAPL, TSLA, NFLX…"
            maxLength={10}
            className="flex-1 bg-slate-900 border border-slate-700 focus:border-blue-500 outline-none rounded-xl px-4 py-3 text-white placeholder-slate-600 text-sm transition-colors"
          />
          <button
            onClick={analyze}
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
