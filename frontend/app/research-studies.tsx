'use client';

import { useCallback, useEffect, useState } from 'react';
import { LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
type Metric = number | null;
type Variant = { metrics: { total_return: number; max_drawdown: number; sharpe_ratio: Metric; annualized_volatility: Metric; turnover: number; fees: number; spread_and_slippage_cost: number; filled_orders: number; observations: number; average_exposure: number }; equity_curve: { session: string; equity: number; cash: number; shares: number }[]; assumptions: string[] };
type Evaluation = { engineering_pass: boolean; full_release_pass: boolean; dataset_version: string; dataset_hash: string; split: string; engine: string; ground_truth_status: string; metrics: { case_accuracy: number; safety_pass_fraction: number; schema_pass_fraction: number; runtime_seconds: number; abstention_rate: number; cost: Metric }; gate_failures: string[]; release_blockers: string[]; safety_checks: Record<string, boolean>; cases: { case_id: string; expected_label: string | null; expected_status: string; pass: boolean; result: { label: string | null; status: string; evidence: { quote: string }[] } }[]; limitations: string[] };
type Experiment = { validity_tier: string; comparisons: Record<string, Record<string, Variant>>; workflow_disagreement_count: number; research_run_ids: string[]; limitations: string[]; partitions: { train: string[]; validation: string[]; test: string[]; fitting: string } };
type Study = { id: string; kind: string; status: string; error?: string; created_at: string; result?: Evaluation | Experiment };
const field = 'mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200';
const button = 'rounded-lg bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40';
const outline = 'rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 disabled:opacity-40';
const colors = ['#34d399', '#60a5fa', '#fbbf24', '#a78bfa', '#f472b6', '#94a3b8'];
const percent = (value: Metric) => value === null ? 'Unavailable' : `${(value * 100).toFixed(2)}%`;
const decimal = (value: Metric) => value === null ? 'Unavailable' : value.toFixed(3);
async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const result = await fetch(API + path, body === undefined ? { signal } : { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(body), signal });
  const data = await result.json();
  if (!result.ok) throw new Error(data.error?.message ?? data.detail?.message ?? 'Request failed');
  return data as T;
}

export default function ResearchStudies({ kind }: { kind: 'evaluation' | 'experiment' }) {
  const [history, setHistory] = useState<Study[]>([]);
  const [study, setStudy] = useState<Study | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [engine, setEngine] = useState('baseline');
  const [split, setSplit] = useState('heldout');
  const [instrument, setInstrument] = useState('US:AAPL');
  const [start, setStart] = useState('2025-01-02');
  const [end, setEnd] = useState('2025-01-21');
  const [trainEnd, setTrainEnd] = useState('2025-01-07');
  const [validationEnd, setValidationEnd] = useState('2025-01-14');
  const [testStart, setTestStart] = useState('2025-01-15');
  const [provenance, setProvenance] = useState('synthetic');
  const [partition, setPartition] = useState('test');
  const running = study?.status === 'queued' || study?.status === 'running';
  const load = useCallback((signal?: AbortSignal) => request<{ items: Study[] }>('/api/studies', undefined, signal), []);
  useEffect(() => { const controller = new AbortController(); load(controller.signal).then(data => setHistory(data.items)).catch(e => { if (!controller.signal.aborted) setError(String(e)); }); return () => controller.abort(); }, [load]);
  const studyId = study?.id;
  useEffect(() => {
    if (!studyId) return;
    const controller = new AbortController(); let inFlight = false;
    const poll = async () => { if (inFlight) return; inFlight = true; try { const data = await request<Study>(`/api/studies/${studyId}`, undefined, controller.signal); setStudy(data); } catch (e) { if (!controller.signal.aborted) setError(String(e)); } finally { inFlight = false; } };
    void poll(); const timer = running ? setInterval(poll, 800) : undefined;
    return () => { controller.abort(); if (timer) clearInterval(timer); };
  }, [studyId, running]);
  async function begin() {
    setError(''); setBusy(true);
    try {
      let next: Study;
      if (kind === 'evaluation') next = await request<Study>('/api/evaluations', { engine, split });
      else {
        const dataset = await request<{ id: string }>('/api/datasets', { instrument_id: instrument, start, end, provenance });
        next = await request<Study>('/api/experiments', { dataset_id: dataset.id, train_end: trainEnd, validation_end: validationEnd, test_start: testStart, configuration: { sentiment_engine: engine } });
      }
      setStudy(next); const data = await load(); setHistory(data.items);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function cancel() { if (!study) return; try { setStudy(await request<Study>(`/api/studies/${study.id}/cancel`, {})); } catch (e) { setError(String(e)); } }
  const evaluation = kind === 'evaluation' ? study?.result as Evaluation | undefined : undefined;
  const experiment = kind === 'experiment' ? study?.result as Experiment | undefined : undefined;
  const variants = experiment?.comparisons[partition];
  const chart = variants ? Object.values(variants)[0].equity_curve.map((point, index) => Object.fromEntries([['session', point.session], ...Object.entries(variants).map(([name, value]) => [name, value.equity_curve[index]?.equity])])) : [];

  return <div className="space-y-6">
    <div><p className="mb-2 text-xs uppercase tracking-widest text-emerald-400">{kind === 'evaluation' ? 'Quality and failure behavior' : 'Reproducible signal research'}</p><h2 className="text-3xl font-semibold">{kind === 'evaluation' ? 'Measure the workflow.' : 'Test assumptions against a frozen dataset.'}</h2><p className="mt-2 text-sm text-slate-400">{kind === 'evaluation' ? 'Versioned cases, explicit gates, and inspectable failures. Engineering checks are separate from full release acceptance.' : 'Daily long/flat simulation with explicit timing, costs, and cash accounting. Synthetic results are software tests.'}</p></div>
    {error && <div role="alert" className="rounded-xl border border-red-800 p-4 text-sm text-red-300">{error}</div>}
    <div className="grid items-start gap-6 lg:grid-cols-[300px_1fr]">
      <aside className="space-y-5"><section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5"><h3 className="mb-4 font-semibold">{kind === 'evaluation' ? 'Run evaluation' : 'Create experiment'}</h3><div className="space-y-4">
        {kind === 'evaluation' ? <><label className="block text-xs text-slate-400">Method<select className={field} value={engine} onChange={e => setEngine(e.target.value)}><option value="baseline">Deterministic baseline</option><option value="finbert">Actual local FinBERT</option></select></label><label className="block text-xs text-slate-400">Dataset partition<select className={field} value={split} onChange={e => setSplit(e.target.value)}><option value="heldout">Held-out diagnostic cases</option><option value="development">Development cases</option></select></label><p className="text-xs leading-relaxed text-slate-500">Expected labels are provisional authored fixtures. Human semantic review remains pending.</p></> : <>
          <label className="block text-xs text-slate-400">Research model<select className={field} value={engine} onChange={e => setEngine(e.target.value)}><option value="baseline">Deterministic baseline</option><option value="finbert">Actual local FinBERT · historical contamination unresolved</option></select></label>
          <label className="block text-xs text-slate-400">Instrument<select className={field} value={instrument} onChange={e => setInstrument(e.target.value)}>{['US:AAPL', 'US:MSFT', 'US:SPY'].map(x => <option key={x}>{x}</option>)}</select></label>
          <label className="block text-xs text-slate-400">Data provenance<select className={field} value={provenance} onChange={e => setProvenance(e.target.value)}><option>synthetic</option><option>historical_approximate</option><option>recorded</option><option>live</option></select></label>
          {([{ label: 'Dataset start', value: start, setter: setStart }, { label: 'Dataset end', value: end, setter: setEnd }, { label: 'Training ends', value: trainEnd, setter: setTrainEnd }, { label: 'Validation ends', value: validationEnd, setter: setValidationEnd }, { label: 'Test begins', value: testStart, setter: setTestStart }]).map(item => <label className="block text-xs text-slate-400" key={item.label}>{item.label}<input type="date" className={field} value={item.value} onChange={e => item.setter(e.target.value)} /></label>)}
          <p className="text-xs leading-relaxed text-slate-500">Frozen default: 10% position cap, five-session horizon, 1 bp fee, 2 bps spread, 5 bps slippage. No threshold fitting or test-set optimization. Load the synthetic demo first, or import complete split-adjusted historical bars.</p></>}
        <button className={`${button} w-full`} disabled={busy || running} onClick={begin}>{busy ? 'Preparing…' : running ? 'Running…' : `Start ${kind}`}</button>
      </div></section><section className="rounded-2xl border border-slate-800 p-5"><h3 className="mb-4 text-sm font-semibold">History</h3>{history.filter(item => item.kind === kind).length === 0 && <p className="text-xs text-slate-500">No studies yet.</p>}<div className="space-y-2">{history.filter(item => item.kind === kind).map(item => <button key={item.id} className="w-full rounded-lg border border-slate-800 p-3 text-left text-xs text-slate-400" onClick={() => setStudy(item)}>{item.id.slice(0, 8)} · {item.status}</button>)}</div></section></aside>
      <section className="min-w-0 rounded-2xl border border-slate-800 bg-slate-900/40 p-5 md:p-6">
        {!study ? <p className="py-12 text-center text-sm text-slate-500">Create a study to inspect its actual results.</p> : <>
          <div className="mb-6 flex items-center justify-between"><div><h3 className="font-semibold">{kind === 'evaluation' ? 'Evaluation results' : 'Experiment results'}</h3><p className="mt-1 text-xs text-slate-500">{study.id.slice(0, 8)} · {study.status}</p></div>{running && <button className={outline} onClick={cancel}>Cancel</button>}</div>
          {study.error && <p className="mb-5 text-sm text-red-300">{study.error}</p>}
          {running && <p className="text-sm text-slate-400">Working through bounded local jobs. Results will appear when computation finishes.</p>}
          {evaluation && <>
            <div className="mb-5 rounded-xl border border-amber-900 bg-amber-950/20 p-4 text-sm text-amber-200">Engineering gates: {evaluation.engineering_pass ? 'passed' : 'failed'} · Full release: {evaluation.full_release_pass ? 'passed' : 'incomplete'}</div>
            <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">{[{ title: 'Fixture agreement', value: percent(evaluation.metrics.case_accuracy) }, { title: 'Safety checks', value: percent(evaluation.metrics.safety_pass_fraction) }, { title: 'Runtime', value: evaluation.metrics.runtime_seconds.toFixed(2) + ' s' }, { title: 'Cost', value: evaluation.metrics.cost === null ? 'Unknown' : '$' + evaluation.metrics.cost }].map(item => <div key={item.title}><p className="text-xs text-slate-500">{item.title}</p><p className="mt-1 text-lg">{item.value}</p></div>)}</div>
            <p className="mb-5 text-xs text-slate-500">{evaluation.dataset_version} · {evaluation.split} · {evaluation.engine}<br />{evaluation.ground_truth_status}</p>
            <div className="mb-6 grid gap-2 sm:grid-cols-2">{Object.entries(evaluation.safety_checks).map(([name, passed]) => <p key={name} className={`rounded-lg border border-slate-800 p-2 text-xs ${passed ? 'text-emerald-300' : 'text-red-300'}`}>{passed ? '✓' : '✕'} {name.replaceAll('_', ' ')}</p>)}</div>
            <h4 className="mb-3 text-sm font-semibold">Case-level findings</h4><div className="space-y-2">{evaluation.cases.map(item => <details key={item.case_id} className="rounded-lg border border-slate-800 p-3 text-xs"><summary className="cursor-pointer text-slate-300">{item.pass ? '✓' : '✕'} {item.case_id} · expected {item.expected_label ?? item.expected_status} · observed {item.result.label ?? item.result.status}</summary>{item.result.evidence.map((span, i) => <blockquote key={i} className="mt-3 text-sm text-slate-400">“{span.quote}”</blockquote>)}</details>)}</div>
            <h4 className="mb-2 mt-6 text-sm font-semibold">Release blockers</h4><ul className="list-disc space-y-2 pl-5 text-xs text-slate-400">{evaluation.release_blockers.map(item => <li key={item}>{item}</li>)}</ul>
          </>}
          {experiment && variants && <>
            <div className="mb-5 rounded-xl border border-amber-900 bg-amber-950/20 p-4 text-sm text-amber-200">Validity: {experiment.validity_tier.replaceAll('_', ' ')}. These results do not establish a profitable strategy.</div>
            <div className="mb-5 flex flex-wrap gap-2">{['train', 'validation', 'test'].map(item => <button key={item} className={`${outline} ${partition === item ? 'border-emerald-600 text-emerald-300' : ''}`} onClick={() => setPartition(item)}>{item}</button>)}</div>
            <div className="h-72 w-full"><ResponsiveContainer width="100%" height="100%"><LineChart data={chart}><CartesianGrid stroke="#1e293b" /><XAxis dataKey="session" tick={{ fontSize: 10, fill: '#94a3b8' }} /><YAxis domain={['auto', 'auto']} tick={{ fontSize: 10, fill: '#94a3b8' }} /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', fontSize: 11 }} /><Legend wrapperStyle={{ fontSize: 10 }} />{Object.keys(variants).map((name, i) => <Line key={name} dataKey={name} stroke={colors[i % colors.length]} dot={false} strokeWidth={2} isAnimationActive={false} />)}</LineChart></ResponsiveContainer></div>
            <div className="mt-5 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="text-slate-500"><tr>{['Variant', 'Return', 'Drawdown', 'Sharpe', 'Turnover', 'Costs', 'Fills'].map(x => <th className="px-2 py-3" key={x}>{x}</th>)}</tr></thead><tbody>{Object.entries(variants).map(([name, variant]) => <tr className="border-t border-slate-800" key={name}><td className="px-2 py-3">{name.replaceAll('_', ' ')}</td><td className="px-2">{percent(variant.metrics.total_return)}</td><td className="px-2">{percent(variant.metrics.max_drawdown)}</td><td className="px-2">{decimal(variant.metrics.sharpe_ratio)}</td><td className="px-2">{decimal(variant.metrics.turnover)}</td><td className="px-2">${(variant.metrics.fees + variant.metrics.spread_and_slippage_cost).toFixed(2)}</td><td className="px-2">{variant.metrics.filled_orders}</td></tr>)}</tbody></table></div>
            <p className="mt-5 text-xs text-slate-400">{experiment.research_run_ids.length} linked research runs · {experiment.workflow_disagreement_count} single-pass/staged signal disagreements · {variants.cash.metrics.observations} sessions in this partition.</p>
            <details className="mt-5"><summary className="cursor-pointer text-sm text-slate-400">Assumptions, validity, and limitations</summary><ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-slate-500">{[...variants.verified.assumptions, ...experiment.limitations].map(item => <li key={item}>{item}</li>)}</ul></details>
          </>}
        </>}
      </section>
    </div>
  </div>;
}
