'use client';

import { useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';

type NodeStatus = 'idle' | 'running' | 'complete';
interface NodeState { id: string; label: string; icon: string; status: NodeStatus; message: string; }
interface SourceOutput { decision: string; sentiment_score: number; keywords: string[]; reasoning: string; }
interface AgentResult {
  ticker: string; signal: 'BUY' | 'SELL' | 'HOLD'; confidence: number; analysis_time_ms: number;
  financial_news:  (SourceOutput & { headline_count: number; headlines: string[]; article_urls: string[] }) | null;
  reddit:          (SourceOutput & { post_count: number; top_posts: string[] }) | null;
  sec_filing:      (SourceOutput & { filing_type: string; filing_url: string; key_findings: string[] }) | null;
  analyst_ratings: (SourceOutput & { recommendation: string; upside_pct: number; analyst_count: number; target_price: number }) | null;
  macro_context: {
    vix: number; yield_10yr: number; spy_5d_return: number; dxy: number;
    fed_stance: string; risk_environment: string; market_trend: string;
    sentiment_score: number; sentiment_label: string;
    global_news_keywords: string[]; global_news_urls: string[]; headline_count: number;
    vix_trend: string; consecutive_risk_off_days: number; reasoning: string;
  } | null;
  risk_manager:      { decision: string; adjusted_size: number; stop_loss_price: number; reason: string; market_safety_flags: string[] } | null;
  portfolio_manager: { bull_case: string; bear_case: string; resolution: string } | null;
  critic:            { decision: string; flags: string[]; agent_agreement: string; veto_reason?: string } | null;
  trade_executed:    { action: string; shares: number; price: number; stop_loss: number; order_id: string; broker: string; skipped_reason?: string } | null;
}

const POPULAR_TICKERS = ['NVDA','AAPL','TSLA','MSFT','AMZN','GOOGL','META','AMD','NFLX','SPY'];
const NODES_CONFIG = [
  { id: 'router',            label: 'Planner',           icon: '🎯' },
  { id: 'financial_news',    label: 'Financial News',    icon: '📰' },
  { id: 'reddit',            label: 'Reddit',            icon: '💬' },
  { id: 'sec',               label: 'SEC Filings',       icon: '📋' },
  { id: 'analyst_ratings',   label: 'Analyst Ratings',   icon: '⭐' },
  { id: 'macro_agent',       label: 'Macro News',        icon: '🌐' },
  { id: 'portfolio_manager', label: 'Portfolio Manager', icon: '💼' },
  { id: 'risk_manager',      label: 'Risk Manager',      icon: '🛡️' },
  { id: 'critic',            label: 'Critic',            icon: '⚖️' },
  { id: 'execution',         label: 'Execution',         icon: '⚡' },
];
const NEWS_AGENTS    = new Set(['financial_news','reddit','sec','analyst_ratings']);
const CRITIC_PREREQS = new Set(['portfolio_manager','risk_manager']);
const API_URL        = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const makeNodes      = () => NODES_CONFIG.map(n => ({ ...n, status: 'idle' as NodeStatus, message: '' }));

// ── Helpers ───────────────────────────────────────────────────────────────────

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-4 ${className}`}>{children}</div>;
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">{children}</div>;
}

function KwTags({ words }: { words: string[] }) {
  if (!words?.length) return null;
  return (
    <div className="flex flex-wrap gap-1 mt-2">
      {words.slice(0,7).map(k => (
        <span key={k} className="text-xs bg-slate-800 border border-slate-700 text-slate-400 rounded px-1.5 py-0.5">{k}</span>
      ))}
    </div>
  );
}

function DecisionPill({ v }: { v: string }) {
  const l = v.toLowerCase();
  const cls = (l==='bullish'||l==='buy'||l==='approved'||l==='proceed')
    ? 'border-green-700 bg-green-900/40 text-green-400'
    : (l==='bearish'||l==='sell'||l==='vetoed'||l==='hold')
    ? 'border-red-700 bg-red-900/40 text-red-400'
    : 'border-slate-700 bg-slate-800 text-slate-400';
  return <span className={`text-xs font-bold border rounded-full px-2.5 py-0.5 ${cls}`}>{v.toUpperCase()}</span>;
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1 border-b border-slate-800/60 last:border-0">
      <span className="text-xs text-slate-500 shrink-0">{label}</span>
      <span className={`text-xs font-mono font-medium ${color ?? 'text-slate-300'}`}>{value}</span>
    </div>
  );
}

// ── Pipeline sidebar ──────────────────────────────────────────────────────────

function Pipeline({ nodes }: { nodes: NodeState[] }) {
  const get  = (id: string) => nodes.find(n => n.id === id)!;
  const done = (id: string) => get(id)?.status === 'complete';

  const Node = ({ id }: { id: string }) => {
    const n = get(id);
    const running  = n?.status === 'running';
    const complete = n?.status === 'complete';
    return (
      <motion.div animate={{ opacity: n?.status==='idle' ? 0.35 : 1 }} transition={{ duration: 0.2 }}
        className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg border ${
          running  ? 'border-blue-600 bg-blue-950/50 node-running' :
          complete ? 'border-green-800/70 bg-green-950/20' :
                     'border-slate-800 bg-slate-900/30'}`}>
        <span className="text-sm shrink-0">{n?.icon}</span>
        <span className="text-sm font-medium text-slate-200 flex-1">{n?.label}</span>
        {running  && <span className="spinner shrink-0" />}
        {complete && <span className="text-green-400 text-xs font-bold shrink-0">✓</span>}
      </motion.div>
    );
  };

  const Line = ({ active }: { active: boolean }) => (
    <div className="flex justify-center my-0.5">
      <motion.div animate={{ backgroundColor: active ? '#22c55e' : '#1e293b' }} transition={{ duration: 0.3 }} className="w-px h-3" />
    </div>
  );

  const newsDone     = ['financial_news','reddit','sec','analyst_ratings'].every(done);
  const parallelDone = done('portfolio_manager') && done('risk_manager');

  return (
    <div className="space-y-0">
      <Node id="router" /><Line active={done('router')} />
      <div className="grid grid-cols-2 gap-1.5">
        <Node id="financial_news" /><Node id="reddit" />
        <Node id="sec" /><Node id="analyst_ratings" />
      </div>
      <Line active={newsDone} />
      <Node id="macro_agent" />
      <Line active={newsDone} />
      <div className="grid grid-cols-2 gap-1.5">
        <Node id="portfolio_manager" /><Node id="risk_manager" />
      </div>
      <Line active={parallelDone} />
      <Node id="critic" /><Line active={done('critic')} />
      <Node id="execution" />
    </div>
  );
}

// ── Source card ───────────────────────────────────────────────────────────────

function SourceCard({ icon, title, decision, score, meta, keywords, reasoning, links, findings }: {
  icon: string; title: string; decision: string; score: number; meta: string;
  keywords: string[]; reasoning: string;
  links?: { label: string; url: string }[];
  findings?: string[];
}) {
  const borderColor = decision === 'bullish' ? 'border-green-800/60' : decision === 'bearish' ? 'border-red-800/60' : 'border-slate-800';
  return (
    <div className={`rounded-xl border ${borderColor} bg-slate-900/60 p-4 flex flex-col gap-2`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-200">{icon} {title}</span>
        <DecisionPill v={decision} />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-lg font-black font-mono text-slate-100">{score.toFixed(2)}</span>
        <span className="text-xs text-slate-500">{meta}</span>
      </div>
      <p className="text-xs text-slate-400 leading-relaxed">{reasoning}</p>
      <KwTags words={keywords} />
      {findings?.map((f,i) => <p key={i} className="text-xs text-slate-500">· {f}</p>)}
      {links?.map(({ label, url }) => (
        <a key={url} href={url} target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 truncate">
          <span>↗</span><span className="truncate">{label}</span>
        </a>
      ))}
    </div>
  );
}

// ── Results panel ─────────────────────────────────────────────────────────────

function Results({ result }: { result: AgentResult }) {
  const sc = {
    BUY:  { border: 'border-green-500',  bg: 'bg-green-950/50',  text: 'text-green-400'  },
    SELL: { border: 'border-red-500',    bg: 'bg-red-950/50',    text: 'text-red-400'    },
    HOLD: { border: 'border-yellow-500', bg: 'bg-yellow-950/50', text: 'text-yellow-400' },
  }[result.signal];

  const blocked  = result.critic?.decision === 'HOLD';
  const tradeOk  = !!result.trade_executed && !result.trade_executed.skipped_reason;
  const macro    = result.macro_context;

  return (
    <div className="space-y-4">

      {/* ── Row 1: Signal + Execution (separate cards) ── */}
      <div className="grid grid-cols-3 gap-4">

        {/* Signal */}
        <div className={`rounded-xl border-2 p-5 text-center ${sc.border} ${sc.bg}`}>
          <div className={`text-6xl font-black ${sc.text}`}>{result.signal}</div>
          <div className="text-slate-300 mt-1">{result.ticker} · {(result.confidence*100).toFixed(0)}% confidence</div>
          {blocked && result.critic?.veto_reason && (
            <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/30 border border-yellow-800 rounded-lg px-2 py-1">
              ⚠ {result.critic.veto_reason}
            </div>
          )}
          <div className="text-slate-600 text-xs mt-1">{(result.analysis_time_ms/1000).toFixed(1)}s</div>
        </div>

        {/* Execution — only trade status, nothing else */}
        <Card>
          <CardTitle>⚡ Execution</CardTitle>
          {tradeOk && result.trade_executed ? (
            <div className="space-y-1">
              <Row label="Action" value={result.trade_executed.action.toUpperCase()}
                color={result.trade_executed.action==='buy' ? 'text-green-400' : 'text-red-400'} />
              <Row label="Shares" value={String(result.trade_executed.shares)} />
              <Row label="Stop Loss" value={`$${result.trade_executed.stop_loss.toFixed(2)}`} />
              <Row label="Order ID" value={result.trade_executed.order_id.slice(0,12)+'…'} />
              <a href="https://app.alpaca.markets/paper/dashboard/overview" target="_blank" rel="noopener noreferrer"
                className="mt-3 w-full flex justify-center text-xs text-green-400 border border-green-800 rounded-lg py-1.5 hover:bg-green-900/30 transition-colors">
                View on Alpaca ↗
              </a>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">🚫</span>
                <span className="text-sm font-semibold text-slate-300">No Trade Executed</span>
              </div>
              <p className="text-xs text-slate-500">
                {result.trade_executed?.skipped_reason ?? result.critic?.veto_reason ?? 'Signal is HOLD'}
              </p>
              <a href="https://app.alpaca.markets/paper/dashboard/overview" target="_blank" rel="noopener noreferrer"
                className="text-xs text-slate-500 border border-slate-700 rounded-lg px-3 py-1.5 hover:border-slate-500 transition-colors inline-block">
                Alpaca Dashboard ↗
              </a>
            </div>
          )}
        </Card>

        {/* Risk Manager — its own card */}
        {result.risk_manager && (
          <Card>
            <CardTitle>🛡️ Risk Manager · Safe to trade today?</CardTitle>
            <div className="flex items-center gap-2 mb-3">
              <DecisionPill v={result.risk_manager.decision} />
              <span className="text-xs text-slate-500">
                {result.risk_manager.decision === 'APPROVED' ? 'Market conditions OK' : result.risk_manager.reason}
              </span>
            </div>
            {/* Only show position details when a trade is actually happening */}
            {result.signal !== 'HOLD' && tradeOk && (
              <>
                <Row label="Position Size" value={`${result.risk_manager.adjusted_size} shares`} />
                <Row label="Stop Loss" value={`$${result.risk_manager.stop_loss_price.toFixed(2)}`} />
              </>
            )}
            {result.risk_manager.market_safety_flags.length > 0 && (
              <div className="mt-2 space-y-1">
                {result.risk_manager.market_safety_flags.map(f => (
                  <p key={f} className="text-xs text-yellow-400">⚠ {f}</p>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>

      {/* ── Row 2: Portfolio Manager reasoning ── */}
      {result.portfolio_manager && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <CardTitle>💼 Portfolio Manager · LLM Sentiment Reasoning</CardTitle>
            <DecisionPill v={result.signal} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs font-semibold text-green-400 mb-1">↑ Bull Case</div>
              <p className="text-sm text-slate-300 leading-relaxed">{result.portfolio_manager.bull_case}</p>
            </div>
            <div>
              <div className="text-xs font-semibold text-red-400 mb-1">↓ Bear Case</div>
              <p className="text-sm text-slate-300 leading-relaxed">{result.portfolio_manager.bear_case}</p>
            </div>
          </div>
          <p className="text-xs text-slate-500 italic border-t border-slate-800 mt-3 pt-3">↳ {result.portfolio_manager.resolution}</p>
        </Card>
      )}

      {/* ── Row 3: 4 Sentiment source cards ── */}
      <div className="text-xs text-slate-600 uppercase tracking-wider">Ticker Sentiment Sources</div>
      <div className="grid grid-cols-4 gap-3">
        {result.financial_news && (
          <SourceCard icon="📰" title="Financial News"
            decision={result.financial_news.decision} score={result.financial_news.sentiment_score}
            meta={`${result.financial_news.headline_count} articles · FinBERT`}
            keywords={result.financial_news.keywords} reasoning={result.financial_news.reasoning}
            links={result.financial_news.headlines.map((h,i) => ({
              label: h, url: result.financial_news!.article_urls?.[i] ?? '#'
            })).filter(l => l.url !== '#')}
          />
        )}
        {result.reddit && (
          <SourceCard icon="💬" title="Reddit"
            decision={result.reddit.decision} score={result.reddit.sentiment_score}
            meta={`${result.reddit.post_count} posts · wsb/stocks`}
            keywords={result.reddit.keywords} reasoning={result.reddit.reasoning}
            findings={result.reddit.top_posts?.slice(0,5)}
          />
        )}
        {result.sec_filing && (
          <SourceCard icon="📋" title={`SEC · ${result.sec_filing.filing_type}`}
            decision={result.sec_filing.decision} score={result.sec_filing.sentiment_score}
            meta="EDGAR filing · keyword score"
            keywords={result.sec_filing.keywords} reasoning={result.sec_filing.reasoning}
            findings={result.sec_filing.key_findings?.slice(0,4)}
            links={result.sec_filing.filing_url ? [{ label: 'View SEC Filing', url: result.sec_filing.filing_url }] : []}
          />
        )}
        {result.analyst_ratings && (
          <SourceCard icon="⭐" title="Analyst Ratings"
            decision={result.analyst_ratings.decision} score={result.analyst_ratings.sentiment_score}
            meta={`${result.analyst_ratings.analyst_count} analysts · ${result.analyst_ratings.recommendation}`}
            keywords={result.analyst_ratings.keywords} reasoning={result.analyst_ratings.reasoning}
            findings={[
              `Target: $${result.analyst_ratings.target_price?.toFixed(2)} (${result.analyst_ratings.upside_pct?.toFixed(1)}% upside)`,
            ]}
          />
        )}
      </div>

      {/* ── Row 4: Macro + Critic ── */}
      <div className="grid grid-cols-2 gap-4">

        {macro && (
          <Card>
            <div className="flex items-center justify-between mb-3">
              <CardTitle>🌐 Macro Environment</CardTitle>
              <DecisionPill v={macro.sentiment_label} />
            </div>
            <p className="text-xs text-slate-400 leading-relaxed mb-2">{macro.reasoning}</p>
            <KwTags words={macro.global_news_keywords} />
            <div className="mt-3 space-y-0">
              <Row label="VIX" value={`${macro.vix} · ${macro.vix_trend}`}
                color={macro.vix>25 ? 'text-red-400' : macro.vix<18 ? 'text-green-400' : 'text-slate-300'} />
              <Row label="SPY 5d Return" value={`${(macro.spy_5d_return*100).toFixed(2)}% · ${macro.market_trend}`}
                color={macro.market_trend==='bullish' ? 'text-green-400' : macro.market_trend==='bearish' ? 'text-red-400' : 'text-slate-300'} />
              <Row label="10yr Yield" value={`${macro.yield_10yr}% · ${macro.fed_stance}`} />
              <Row label="DXY (Dollar)" value={String(macro.dxy)} />
              {macro.consecutive_risk_off_days > 0 && (
                <Row label="Risk-off streak" value={`${macro.consecutive_risk_off_days} days`} color="text-red-400" />
              )}
            </div>
            {macro.global_news_urls?.slice(0,2).map((url,i) => (
              <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 truncate mt-1">
                ↗ <span className="truncate">{url.replace(/^https?:\/\/(www\.)?/,'').split('/')[0]}</span>
              </a>
            ))}
          </Card>
        )}

        {result.critic && (
          <Card>
            <div className="flex items-center justify-between mb-3">
              <CardTitle>⚖️ Critic · Final Debate</CardTitle>
              <DecisionPill v={result.critic.decision} />
            </div>
            <Row label="Sentiment Agreement" value={result.critic.agent_agreement} />
            <Row label="Decision" value={result.critic.decision}
              color={result.critic.decision==='PROCEED' ? 'text-green-400' : 'text-red-400'} />
            {result.critic.veto_reason && (
              <p className="text-xs text-red-400 mt-2">↳ {result.critic.veto_reason}</p>
            )}
            {result.critic.decision === 'HOLD' && result.risk_manager?.decision === 'VETOED' && (
              <p className="text-xs text-amber-400 mt-1">
                ℹ Sentiment was {result.critic.agent_agreement} bullish — trade blocked by portfolio risk, not sentiment.
              </p>
            )}
            {result.critic.flags.length > 0 && (
              <div className="mt-3 space-y-1.5">
                <div className="text-xs text-slate-600 uppercase tracking-wider">Flags</div>
                {result.critic.flags.slice(0,5).map(f => (
                  <p key={f} className="text-xs text-yellow-400">⚑ {f}</p>
                ))}
              </div>
            )}
          </Card>
        )}
      </div>

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
  const completedNews   = useRef(new Set<string>());
  const completedCritic = useRef(new Set<string>());

  const analyze = useCallback((t?: string) => {
    const sym = (t ?? ticker).trim().toUpperCase();
    if (!sym || isRunning) return;
    setTicker(sym); setNodes(makeNodes()); setResult(null); setError(null);
    setIsRunning(true); setStarted(true);
    completedNews.current = new Set(); completedCritic.current = new Set();
    setNodes(p => p.map(n => n.id==='router' ? {...n, status:'running'} : n));

    const es = new EventSource(`${API_URL}/stream?ticker=${sym}&days=1`);
    es.addEventListener('step', (e: MessageEvent) => {
      const { node: id, message } = JSON.parse(e.data);
      setNodes(prev => {
        let next = prev.map(n => n.id===id ? {...n, status:'complete' as NodeStatus, message} : n);
        if (id==='router') {
          next = next.map(n => ['financial_news','reddit','sec','analyst_ratings','macro_agent'].includes(n.id) ? {...n,status:'running'} : n);
        } else if (NEWS_AGENTS.has(id)) {
          completedNews.current.add(id);
          if (completedNews.current.size===NEWS_AGENTS.size)
            next = next.map(n => n.id==='portfolio_manager' ? {...n,status:'running'} : n);
        } else if (id==='macro_agent') {
          next = next.map(n => n.id==='risk_manager' ? {...n,status:'running'} : n);
        } else if (CRITIC_PREREQS.has(id)) {
          completedCritic.current.add(id);
          if (completedCritic.current.size===CRITIC_PREREQS.size)
            next = next.map(n => n.id==='critic' ? {...n,status:'running'} : n);
        } else if (id==='critic') {
          next = next.map(n => n.id==='execution' ? {...n,status:'running'} : n);
        }
        return next;
      });
    });
    es.addEventListener('result', (e: MessageEvent) => {
      setResult(JSON.parse(e.data)); setIsRunning(false);
      setNodes(p => p.map(n => n.id==='execution' ? {...n,status:'complete'} : n));
      es.close();
    });
    es.addEventListener('error', (e: MessageEvent) => {
      try { setError(JSON.parse(e.data).message); } catch { setError('Analysis failed.'); }
      setIsRunning(false); es.close();
    });
    es.onerror = () => { setError(`Cannot reach API at ${API_URL}`); setIsRunning(false); es.close(); };
  }, [ticker, isRunning]);

  return (
    <main className="min-h-screen bg-slate-950 text-white flex flex-col">

      {/* ── Header ── */}
      <div className="border-b border-slate-800 bg-slate-900/90 backdrop-blur px-6 py-4 flex items-center gap-5">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight leading-none">QuantSentiment</h1>
          <p className="text-slate-600 text-xs mt-0.5">Multi-agent sentiment AI · Paper trading</p>
        </div>
        <div className="flex flex-wrap gap-1.5 ml-4">
          {POPULAR_TICKERS.map(t => (
            <button key={t} onClick={() => setTicker(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                ticker===t ? 'bg-blue-600 border-blue-500 text-white'
                           : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white hover:border-slate-500'}`}>
              {t}
            </button>
          ))}
        </div>
        <div className="flex gap-2 ml-auto">
          <Link href="/analytics"
            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 px-4 py-2 rounded-lg text-sm text-slate-300 hover:text-white transition-colors whitespace-nowrap">
            📊 Analytics
          </Link>
          <input value={ticker} onChange={e => setTicker(e.target.value.toUpperCase())}
            onKeyDown={e => e.key==='Enter' && analyze()}
            placeholder="Ticker…" maxLength={10}
            className="bg-slate-800 border border-slate-700 focus:border-blue-500 outline-none rounded-lg px-3 py-2 text-white placeholder-slate-600 text-sm w-28 transition-colors" />
          <button onClick={() => analyze()} disabled={isRunning || !ticker.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 disabled:cursor-not-allowed px-5 py-2 rounded-lg font-semibold text-sm transition-colors whitespace-nowrap">
            {isRunning ? <span className="flex items-center gap-2"><span className="spinner"/>Analyzing…</span> : 'Analyze →'}
          </button>
        </div>
      </div>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">

        {/* Pipeline sidebar */}
        <div className="w-96 shrink-0 border-r border-slate-800 bg-slate-900/30 p-4 overflow-y-auto">
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-3">Agent Pipeline</div>
          {started
            ? <Pipeline nodes={nodes} />
            : <p className="text-xs text-slate-700 text-center mt-16">Select a ticker to begin</p>}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-6">
          <AnimatePresence>
            {error && (
              <motion.div initial={{opacity:0}} animate={{opacity:1}} exit={{opacity:0}}
                className="mb-4 p-3 bg-red-950 border border-red-800 rounded-xl text-red-400 text-sm">{error}</motion.div>
            )}
          </AnimatePresence>
          {!started && (
            <div className="flex items-center justify-center h-full">
              <p className="text-slate-700">Select a ticker above and click Analyze</p>
            </div>
          )}
          {started && !result && isRunning && (
            <div className="flex items-center justify-center h-full gap-3 text-slate-500">
              <span className="spinner"/><span className="text-sm">Running analysis…</span>
            </div>
          )}
          {result && (
            <motion.div initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:0.3}}>
              <Results result={result} />
            </motion.div>
          )}
        </div>
      </div>
    </main>
  );
}
