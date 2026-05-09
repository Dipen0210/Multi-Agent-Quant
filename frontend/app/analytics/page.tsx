'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Analytics {
  account: { cash: number; portfolio_value: number; buying_power: number };
  metrics: {
    total_pl: number; total_pl_pct: number; num_trades: number;
    open_positions: number; win_rate: number | null; wins: number; losses: number;
  };
  equity_history: { date: string; equity: number; pl: number }[];
  positions: {
    ticker: string; qty: number; avg_entry: number; current: number;
    unrealized_pl: number; pct: number;
  }[];
  trades: { ticker: string; side: string; qty: number; price: number; total: number; date: string }[];
}

function fmt(n: number, prefix = '$') {
  return `${prefix}${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function PL({ value, suffix = '' }: { value: number; suffix?: string }) {
  const pos = value >= 0;
  return (
    <span className={pos ? 'text-green-400' : 'text-red-400'}>
      {pos ? '+' : '-'}{fmt(value)}{suffix}
    </span>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-100">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const equity = payload[0]?.value;
  const pl     = payload[1]?.value;
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3 text-xs">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className="text-slate-100 font-semibold">{fmt(equity)}</p>
      {pl !== undefined && (
        <p className={pl >= 0 ? 'text-green-400' : 'text-red-400'}>
          {pl >= 0 ? '+' : ''}{fmt(pl)} P&L
        </p>
      )}
    </div>
  );
};

export default function AnalyticsPage() {
  const [data, setData]       = useState<Analytics | null>(null);
  const [period, setPeriod]   = useState<'1W' | '1M' | '3M'>('1M');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/analytics?period=${period}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => { setError('Failed to load analytics'); setLoading(false); });
  }, [period]);

  const isUp = (data?.metrics.total_pl ?? 0) >= 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link href="/" className="text-slate-400 hover:text-slate-200 text-sm">← Dashboard</Link>
        <h1 className="text-xl font-bold">Portfolio Analytics</h1>
        <span className="ml-auto text-xs text-slate-500">Alpaca Paper Trading</span>
      </div>

      {loading && <p className="text-slate-500 text-center mt-20">Loading...</p>}
      {error   && <p className="text-red-400 text-center mt-20">{error}</p>}

      {data && (
        <div className="max-w-7xl mx-auto space-y-6">

          {/* ── Metric cards ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="Portfolio Value"
              value={fmt(data.account.portfolio_value)}
              sub={`Cash: ${fmt(data.account.cash)}`}
            />
            <MetricCard
              label="Total Return"
              value={<PL value={data.metrics.total_pl} />}
              sub={`${data.metrics.total_pl_pct >= 0 ? '+' : ''}${data.metrics.total_pl_pct}% since start`}
            />
            <MetricCard
              label="Win Rate"
              value={data.metrics.win_rate !== null ? `${data.metrics.win_rate}%` : '—'}
              sub={`${data.metrics.wins}W / ${data.metrics.losses}L`}
            />
            <MetricCard
              label="Trades"
              value={data.metrics.num_trades}
              sub={`${data.metrics.open_positions} open positions`}
            />
          </div>

          {/* ── Equity chart ── */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-300">Portfolio Value</h2>
              <div className="flex gap-1">
                {(['1W', '1M', '3M'] as const).map(p => (
                  <button key={p} onClick={() => setPeriod(p)}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      period === p ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
                    }`}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            {data.equity_history.length < 2 ? (
              <div className="h-48 flex items-center justify-center text-slate-600 text-sm">
                Not enough history yet — run more analyses to build the chart.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={data.equity_history} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={isUp ? '#22c55e' : '#ef4444'} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={isUp ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `$${(v/1000).toFixed(0)}k`} width={48} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="equity" stroke={isUp ? '#22c55e' : '#ef4444'}
                    strokeWidth={2} fill="url(#equityGrad)" dot={false} />
                  <Area type="monotone" dataKey="pl" stroke="transparent" fill="transparent" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* ── Open positions + Trade history side by side ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Positions */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Open Positions</h2>
              {data.positions.length === 0 ? (
                <p className="text-slate-600 text-sm">No open positions.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b border-slate-800">
                      <th className="text-left pb-2">Ticker</th>
                      <th className="text-right pb-2">Shares</th>
                      <th className="text-right pb-2">Avg Cost</th>
                      <th className="text-right pb-2">Current</th>
                      <th className="text-right pb-2">Return</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map(p => (
                      <tr key={p.ticker} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="py-2.5 font-semibold">{p.ticker}</td>
                        <td className="py-2.5 text-right text-slate-400">{p.qty}</td>
                        <td className="py-2.5 text-right text-slate-400">{fmt(p.avg_entry)}</td>
                        <td className="py-2.5 text-right">{fmt(p.current)}</td>
                        <td className="py-2.5 text-right">
                          <PL value={p.unrealized_pl} />
                          <span className="text-xs text-slate-500 ml-1">({p.pct >= 0 ? '+' : ''}{p.pct}%)</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Trade history */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
              <h2 className="text-sm font-semibold text-slate-300 mb-4">Trade History</h2>
              {data.trades.length === 0 ? (
                <p className="text-slate-600 text-sm">No completed trades yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-slate-500 border-b border-slate-800">
                      <th className="text-left pb-2">Ticker</th>
                      <th className="text-left pb-2">Side</th>
                      <th className="text-right pb-2">Qty</th>
                      <th className="text-right pb-2">Price</th>
                      <th className="text-right pb-2">Total</th>
                      <th className="text-right pb-2">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.trades.map((t, i) => (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                        <td className="py-2.5 font-semibold">{t.ticker}</td>
                        <td className="py-2.5">
                          <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                            t.side === 'buy' ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
                          }`}>{t.side.toUpperCase()}</span>
                        </td>
                        <td className="py-2.5 text-right text-slate-400">{t.qty}</td>
                        <td className="py-2.5 text-right">{fmt(t.price)}</td>
                        <td className="py-2.5 text-right">{fmt(t.total)}</td>
                        <td className="py-2.5 text-right text-slate-500 text-xs">{t.date.slice(0,10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
