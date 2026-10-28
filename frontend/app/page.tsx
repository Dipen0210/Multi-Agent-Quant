'use client';

import { useCallback, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import Link from 'next/link';
import ResearchStudies from './research-studies';
import TraceStep from './trace-step';
import type { Step } from './trace-step';

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
type Json = Record<string, unknown>;
type DocumentRecord = { id: string; available_at: string; ingested_at: string; data: { title: string; content: string; provider: string; revision: number; published_at: string; first_observed_at: string | null; language: string; instrument_ids: string[]; provenance: string; usage_restrictions: string; source_url?: string } };
type Configuration = { id: string; data: { name: string; sentiment_engine: string; workflow: string } };
type Sentiment = { document_id: string; instrument_id: string; status: string; label: string | null; score: number | null; reason: string; evidence: { quote: string; start: number; end: number }[] };
type Finding = { sentiment: { status: string; score: number | null; independent_sources: number; raw_documents: number; excluded_or_uncertain: number }; quantitative: { status: string; last_close?: number; currency?: string; available_at?: string }; research_signal: { signal: string; reason: string }; hypothesis: string; alternative_interpretation: string };
type Report = { status: string; question: string; findings: Record<string, Finding>; sentiments: Sentiment[]; limitations: string[]; execution_mode: string; data_provenance: string; model: { model_id: string; revision: string; recording_id?: string }; verification: { status: string }; created_at: string };
type Run = { id: string; status: string; created_at: string; report?: Report | null; error?: string | null; configuration_id?: string; snapshot_id?: string };
type Source = { provider: string; latest_available_at: string; latest_import_at: string; records: number };
type Tab = 'Research' | 'Evidence' | 'Runs & traces' | 'Configurations' | 'System' | 'Experiments' | 'Evaluations';

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = data.error?.message ?? data.detail?.message ?? data.detail ?? 'Request failed';
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return data as T;
}
function post<T>(path: string, body: unknown = {}) { return api<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); }
function message(error: unknown) { return error instanceof Error ? error.message : 'Unexpected request failure'; }
function date(value?: string | null) { return value ? new Date(value).toLocaleString('en-US', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC' : 'Unavailable'; }
function Badge({ children }: { children: ReactNode }) { return <span className="rounded-full border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300">{children}</span>; }
function Panel({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) { return <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5 md:p-6"><div className="mb-5 flex flex-wrap items-center justify-between gap-3"><h2 className="font-semibold text-slate-100">{title}</h2>{aside}</div>{children}</section>; }
function Empty({ children }: { children: ReactNode }) { return <p className="rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">{children}</p>; }
const input = 'w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-200 focus:border-emerald-500 focus:outline-none';
const button = 'rounded-lg bg-emerald-400 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40';
const secondary = 'rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-40';

export default function ResearchWorkspace() {
  const [tab, setTab] = useState<Tab>('Research');
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [configs, setConfigs] = useState<Configuration[]>([]);
  const [activeConfig, setActiveConfig] = useState('');
  const [sources, setSources] = useState<Source[]>([]);
  const [health, setHealth] = useState<Json | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentRecord | null>(null);
  const [instruments, setInstruments] = useState(['US:AAPL']);
  const [question, setQuestion] = useState('What does the eligible evidence say about company sentiment?');
  const [cutoff, setCutoff] = useState('2025-01-03T22:00:00Z');
  const [engine, setEngine] = useState('baseline');
  const [provenance, setProvenance] = useState('synthetic');
  const [recording, setRecording] = useState('');
  const [workflow, setWorkflow] = useState('single_pass');
  const [configurationId, setConfigurationId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [csvKind, setCsvKind] = useState('documents');

  const loadWorkspace = useCallback((signal?: AbortSignal) => Promise.all([
    api<{ documents: DocumentRecord[] }>('/api/evidence', { signal }), api<{ items: Run[] }>('/api/runs', { signal }),
    api<{ items: Configuration[]; active_configuration_id: string }>('/api/configurations', { signal }),
    api<Json>('/health', { signal }), api<{ sources: Source[] }>('/api/source-health', { signal }),
  ]), []);
  const applyWorkspace = useCallback(([evidence, history, configurations, status, sourceHealth]: Awaited<ReturnType<typeof loadWorkspace>>) => {
    setDocuments(evidence.documents); setRuns(history.items); setConfigs(configurations.items);
    setActiveConfig(configurations.active_configuration_id); setHealth(status); setSources(sourceHealth.sources); setLoaded(true);
  }, []);
  const refresh = useCallback(async () => { applyWorkspace(await loadWorkspace()); }, [applyWorkspace, loadWorkspace]);
  useEffect(() => {
    const controller = new AbortController();
    loadWorkspace(controller.signal).then(applyWorkspace).catch(e => { if (!controller.signal.aborted) { setError(message(e)); setLoaded(true); } });
    return () => controller.abort();
  }, [loadWorkspace, applyWorkspace]);
  const runId = run?.id;
  const running = run?.status === 'queued' || run?.status === 'running';
  useEffect(() => {
    if (!runId) return;
    const controller = new AbortController(); let inFlight = false;
    const poll = async () => {
      if (inFlight) return; inFlight = true;
      try {
        const [latest, trace] = await Promise.all([api<Run>(`/api/runs/${runId}`, { signal: controller.signal }), api<{ items: Step[] }>(`/api/runs/${runId}/steps`, { signal: controller.signal })]);
        setRun(latest); setSteps(trace.items);
      } catch (e) { if (!controller.signal.aborted) setError(message(e)); }
      finally { inFlight = false; }
    };
    void poll(); const interval = running ? setInterval(poll, 750) : undefined;
    return () => { controller.abort(); if (interval) clearInterval(interval); };
  }, [runId, running]);

  async function action(work: () => Promise<void>) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function importDemo() { await action(async () => {
    const result = await post<{ inserted: number; duplicates: number; rejected: unknown[] }>('/api/demo/import');
    setNotice(`Synthetic fixture: ${result.inserted} records imported, ${result.duplicates} already present, ${result.rejected.length} rejected.`); await refresh();
  }); }
  async function submit(event: FormEvent) { event.preventDefault(); await action(async () => {
    const config = configurationId ? { id: configurationId } : await post<{ id: string }>('/api/configurations', { name: `${engine} · ${workflow}`, sentiment_engine: engine, workflow, recording_id: engine === 'recorded' ? recording : null });
    const snapshot = await post<{ id: string }>('/api/snapshots', { instrument_ids: instruments, cutoff, provenance });
    const next = await api<Run>('/api/runs', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify({ snapshot_id: snapshot.id, question, configuration_id: config.id }) });
    setRun(next); setSteps([]); await refresh();
  }); }
  async function inspect(id: string) { await action(async () => { setSelectedDoc(await api<DocumentRecord>(`/api/evidence/${id}`)); }); }
  async function upload(file?: File) { if (!file) return; await action(async () => {
    if (file.size > 2_000_000) throw new Error('Import limit is 2 MB.');
    const text = await file.text();
    const result = file.name.endsWith('.csv') ? await api<Json>(`/api/imports/csv/${csvKind}`, { method: 'POST', headers: { 'Content-Type': 'text/csv' }, body: text }) : await post<Json>('/api/imports', JSON.parse(text));
    setNotice(JSON.stringify(result)); await refresh();
  }); }

  return <main className="min-h-screen bg-[#080e19] text-slate-200">
    <header className="border-b border-slate-800 px-5 py-5 md:px-10"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-400 text-xl font-black text-slate-950">Q</div><div><h1 className="text-lg font-semibold tracking-tight">QuantSentiment <span className="font-normal text-slate-500">Research</span></h1><p className="text-xs text-slate-500">Evidence first. Every conclusion inspectable.</p></div></div>
      <div className="flex items-center gap-3"><Badge>{health ? 'Local workspace' : loaded ? 'API unavailable' : 'Connecting'}</Badge><span className="text-xs text-slate-500">External trading disabled</span></div>
    </div></header>
    <div className="mx-auto max-w-7xl px-5 py-7 md:px-10">
      <nav className="mb-8 flex gap-2 overflow-x-auto border-b border-slate-800" aria-label="Workspace">
        {(['Research', 'Evidence', 'Runs & traces', 'Experiments', 'Evaluations', 'Configurations', 'System'] as Tab[]).map(item => <button key={item} onClick={() => setTab(item)} className={`whitespace-nowrap border-b-2 px-4 pb-3 text-sm ${tab === item ? 'border-emerald-400 text-emerald-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>{item}</button>)}
      </nav>
      {error && <div role="alert" className="mb-5 rounded-xl border border-red-800 bg-red-950/30 p-4 text-sm text-red-300">{error}</div>}
      {notice && <div role="status" className="mb-5 max-h-40 overflow-auto rounded-xl border border-emerald-900 bg-emerald-950/20 p-4 text-sm text-emerald-200">{notice}</div>}
      {tab === 'Research' && <>
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-2 text-xs font-medium uppercase tracking-widest text-emerald-400">Research workspace</p><h2 className="text-3xl font-semibold tracking-tight">From sources to a defensible view.</h2><p className="mt-2 text-sm text-slate-400">Choose an information cutoff. Inspect evidence, uncertainty, and every research step.</p></div><button className={secondary} disabled={busy} onClick={importDemo}>Load synthetic demo</button></div>
        <div className="grid items-start gap-6 lg:grid-cols-[340px_1fr]">
          <Panel title="New research run"><form onSubmit={submit} className="space-y-5">
            <fieldset><legend className="mb-2 text-xs text-slate-400">Instruments · daily US equities</legend><div className="flex gap-3">{['AAPL', 'MSFT', 'SPY'].map(symbol => <label key={symbol} className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={instruments.includes(`US:${symbol}`)} onChange={e => setInstruments(current => e.target.checked ? [...current, `US:${symbol}`] : current.filter(x => x !== `US:${symbol}`))} />{symbol}</label>)}</div></fieldset>
            <label className="block text-xs text-slate-400">Research question · sentiment scope<textarea className={`${input} mt-2`} rows={3} value={question} maxLength={2000} required onChange={e => setQuestion(e.target.value)} /></label>
            <label className="block text-xs text-slate-400">Information cutoff · ISO timestamp with timezone<input className={`${input} mt-2`} value={cutoff} required onChange={e => setCutoff(e.target.value)} /></label>
            <label className="block text-xs text-slate-400">Evidence provenance<select className={`${input} mt-2`} value={provenance} onChange={e => setProvenance(e.target.value)}>{['synthetic', 'recorded', 'historical_approximate', 'live'].map(x => <option key={x}>{x}</option>)}</select></label>
            <label className="block text-xs text-slate-400">Configuration<select className={`${input} mt-2`} value={configurationId} onChange={e => setConfigurationId(e.target.value)}><option value="">Create from options below</option>{configs.map(c => <option key={c.id} value={c.id}>{c.data.name} {c.id === activeConfig ? '(active)' : ''}</option>)}</select></label>
            {!configurationId && <><label className="block text-xs text-slate-400">Sentiment method<select className={`${input} mt-2`} value={engine} onChange={e => setEngine(e.target.value)}><option value="baseline">Deterministic lexicon baseline</option><option value="finbert">Real local FinBERT inference</option><option value="recorded">Replay recorded inference</option></select></label>
              {engine === 'recorded' && <label className="block text-xs text-slate-400">Recording ID<input className={`${input} mt-2`} required value={recording} onChange={e => setRecording(e.target.value)} /></label>}
              <label className="block text-xs text-slate-400">Workflow<select className={`${input} mt-2`} value={workflow} onChange={e => setWorkflow(e.target.value)}><option value="verified">Research with evidence verification</option><option value="single_pass">Single pass comparison</option></select></label></>}
            <p className="text-xs leading-relaxed text-slate-500">Synthetic fixtures test the software. Real inference uses cached model weights. Neither establishes predictive value.</p>
            <button className={`${button} w-full`} disabled={busy || running || !instruments.length}>{busy ? 'Preparing…' : running ? 'Research running…' : 'Start research'}</button>
          </form></Panel>
          <div className="space-y-6">
            <Panel title={run ? 'Research progress' : 'Ready when your evidence is'} aside={run && <Badge>{run.status}</Badge>}>
              {!run ? <Empty>Load the synthetic demo or import your own evidence, then start a research run.</Empty> : <>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-slate-500">Run {run.id.slice(0, 8)} · {date(run.created_at)}</span>{running && <button className={secondary} onClick={() => action(async () => { setRun(await post<Run>(`/api/runs/${run.id}/cancel`)); })}>Cancel run</button>}</div>
                <ol className="grid gap-2 sm:grid-cols-5">{(steps[0]?.role === 'research' ? ['research'] : ['evidence', 'sentiment', 'quantitative', 'verification', 'report']).map(role => { const step = steps.filter(s => s.role === role).at(-1); return <li key={role} className="rounded-xl border border-slate-800 p-3"><p className="text-xs capitalize text-slate-300">{role}</p><p className={`mt-2 text-xs ${step?.status === 'completed' ? 'text-emerald-400' : 'text-slate-500'}`}>{step?.status ?? 'pending'}</p></li>; })}</ol>
                {run.error && <p className="mt-4 text-sm text-red-300">{run.error}</p>}
                {run.status === 'cancelled' && <p className="mt-4 text-sm text-amber-300">Cancelled. No report is presented as complete.</p>}
              </>}
            </Panel>
            {run?.report && <Panel title="Research report" aside={<Badge>{run.report.execution_mode}</Badge>}>
              <p className="mb-4 text-sm text-slate-400">{run.report.question}</p>
              <div className="mb-5 flex flex-wrap gap-2"><Badge>{run.report.data_provenance} evidence</Badge><Badge>Citations {run.report.verification.status}</Badge><Badge>{run.report.status}</Badge></div>
              {Object.entries(run.report.findings).map(([instrument, finding]) => <article key={instrument} className="mb-5 rounded-xl border border-slate-800 p-4"><div className="flex items-center justify-between"><h3 className="font-semibold">{instrument.replace('US:', '')}</h3><Badge>{finding.research_signal.signal.replace('_', ' ')}</Badge></div>
                <div className="my-5 grid grid-cols-3 gap-3"><div><p className="text-xs text-slate-500">Sentiment</p><p className="mt-1 capitalize">{finding.sentiment.status.replace('_', ' ')}</p></div><div><p className="text-xs text-slate-500">Independent evidence</p><p className="mt-1">{finding.sentiment.independent_sources} <span className="text-xs text-slate-500">/ {finding.sentiment.raw_documents} documents</span></p></div><div><p className="text-xs text-slate-500">Eligible close</p><p className="mt-1">{finding.quantitative.last_close ? `$${finding.quantitative.last_close.toFixed(2)}` : 'Unavailable'}</p></div></div>
                <p className="text-sm text-slate-400">{finding.research_signal.reason}</p><p className="mt-2 text-xs leading-relaxed text-slate-500">{finding.alternative_interpretation}</p>
              </article>)}
              <h3 className="mb-3 text-sm font-semibold">Evidence and counterevidence</h3>
              <div className="space-y-3">{run.report.sentiments.map((sentiment, i) => <div key={`${sentiment.document_id}-${i}`} className="border-l-2 border-slate-700 pl-4"><div className="mb-2 flex items-center gap-2"><span className="text-xs text-slate-400">{sentiment.instrument_id}</span><Badge>{sentiment.label ?? sentiment.status.replaceAll('_', ' ')}</Badge><button onClick={() => inspect(sentiment.document_id)} className="text-xs text-emerald-400 underline underline-offset-4">Inspect source</button></div>{sentiment.evidence.map((span, j) => <blockquote key={j} className="my-2 text-sm leading-relaxed text-slate-300">“{span.quote}”</blockquote>)}<p className="text-xs leading-relaxed text-slate-500">{sentiment.reason}</p></div>)}</div>
              <details className="mt-6 border-t border-slate-800 pt-4"><summary className="cursor-pointer text-sm text-slate-400">Model, limitations, and reproducibility</summary><p className="mt-3 break-all text-xs text-slate-500">{run.report.model.model_id} · {run.report.model.revision}</p>{run.report.model.recording_id && <p className="mt-2 break-all text-xs text-slate-500">Recording: {run.report.model.recording_id}</p>}<ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-slate-400">{run.report.limitations.map(item => <li key={item}>{item}</li>)}</ul></details>
            </Panel>}
          </div>
        </div>
      </>}
      {tab === 'Evidence' && <div className="space-y-6"><Panel title="Evidence library" aside={<button className={secondary} onClick={importDemo} disabled={busy}>Load synthetic demo</button>}>
        <p className="mb-4 text-sm text-slate-400">Immutable source versions. Availability and publication are separate timestamps.</p>
        <div className="mb-6 flex flex-wrap items-center gap-3"><label className="text-xs text-slate-400">CSV collection <select className={input} value={csvKind} onChange={e => setCsvKind(e.target.value)}><option>documents</option><option>market</option></select></label><label className="text-sm text-slate-300">Import JSON or CSV<input className="mt-2 block text-xs text-slate-500" type="file" accept=".json,.csv" onChange={e => upload(e.target.files?.[0])} disabled={busy} /></label></div>
        {!documents.length ? <Empty>No evidence imported.</Empty> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs text-slate-500"><tr><th className="pb-3">Source document</th><th>Revision</th><th>Available at</th><th>Provenance</th></tr></thead><tbody>{documents.map(doc => <tr key={doc.id} className="border-t border-slate-800"><td className="py-3 pr-4"><button className="text-left text-emerald-300 hover:underline" onClick={() => setSelectedDoc(doc)}>{doc.data.title}</button><p className="mt-1 text-xs text-slate-500">{doc.data.provider}</p></td><td>{doc.data.revision}</td><td className="whitespace-nowrap pr-4 text-xs text-slate-400">{date(doc.available_at)}</td><td><Badge>{doc.data.provenance}</Badge></td></tr>)}</tbody></table></div>}
      </Panel></div>}
      {tab === 'Runs & traces' && <div className="grid gap-6 lg:grid-cols-[320px_1fr]"><Panel title="Research history" aside={<button className={secondary} onClick={() => action(refresh)}>Refresh</button>}>{!runs.length ? <Empty>No research runs yet.</Empty> : <div className="space-y-2">{runs.map(item => <button className={`w-full rounded-lg border p-3 text-left ${run?.id === item.id ? 'border-emerald-800 bg-emerald-950/20' : 'border-slate-800'}`} key={item.id} onClick={() => { setRun(item); setSteps([]); }}><div className="flex justify-between text-xs"><span>{item.id.slice(0, 8)}</span><span>{item.status}</span></div><p className="mt-2 text-xs text-slate-500">{date(item.created_at)}</p></button>)}</div>}</Panel><Panel title="Agent steps and validation">{!run ? <Empty>Select a research run.</Empty> : <><div className="mb-4 flex items-center justify-between"><Badge>{run.status}</Badge><button className={secondary} onClick={() => setTab('Research')}>View report</button></div>{steps.map(step => <TraceStep key={step.id} step={step} />)}</>}</Panel></div>}
      {tab === 'Experiments' && <ResearchStudies key="experiment" kind="experiment" />}
      {tab === 'Evaluations' && <ResearchStudies key="evaluation" kind="evaluation" />}
      {tab === 'Configurations' && <Panel title="Versioned configurations"><p className="mb-5 text-sm text-slate-400">Configurations are immutable. Activate an earlier version to roll back the default for API runs. Existing runs retain their original configuration.</p><div className="space-y-3">{configs.map(config => <div key={config.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 p-4"><div><h3 className="text-sm">{config.data.name}</h3><p className="mt-1 text-xs text-slate-500">{config.data.sentiment_engine} · {config.data.workflow} · {config.id.slice(0, 12)}</p></div>{config.id === activeConfig ? <Badge>Active default</Badge> : <button className={secondary} disabled={busy} onClick={() => action(async () => { await post(`/api/configurations/${config.id}/activate`); await refresh(); })}>Activate</button>}</div>)}</div></Panel>}
      {tab === 'System' && <div className="space-y-6"><Panel title="Workspace health"><dl className="grid gap-5 text-sm sm:grid-cols-3"><div><dt className="text-slate-500">API</dt><dd className="mt-2">{health ? 'Available' : 'Unavailable'}</dd></div><div><dt className="text-slate-500">Deployment</dt><dd className="mt-2">Single-user local</dd></div><div><dt className="text-slate-500">External execution</dt><dd className="mt-2 text-emerald-400">Disabled</dd></div></dl><p className="mt-5 text-xs text-slate-500">Historical experiments and evaluations report their actual validity tier. Full release remains incomplete pending acceptance and semantic review.</p></Panel><Panel title="Source availability">{!sources.length ? <Empty>No imported sources.</Empty> : sources.map(source => <div key={source.provider} className="border-b border-slate-800 py-3 text-sm"><p>{source.provider} · {source.records} records</p><p className="mt-1 text-xs text-slate-500">Latest availability: {date(source.latest_available_at)} · Imported: {date(source.latest_import_at)}</p></div>)}<p className="mt-4 text-xs text-slate-500">Imported timestamps do not certify point-in-time capture. Live adapters have not been validated.</p></Panel><Link href="/legacy" className="text-xs text-slate-500 underline">Legacy interface (provider analysis disabled by default)</Link></div>}
      <footer className="mt-10 border-t border-slate-800 pt-5 text-xs text-slate-600">QuantSentiment V2 · Research and internal simulation · No calibrated return probabilities</footer>
    </div>
    {selectedDoc && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-label="Source evidence"><section className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-6"><div className="mb-5 flex items-start justify-between gap-4"><div><Badge>{selectedDoc.data.provenance}</Badge><h2 className="mt-3 text-lg font-semibold">{selectedDoc.data.title}</h2></div><button className={secondary} onClick={() => setSelectedDoc(null)} autoFocus>Close</button></div><dl className="grid gap-3 text-xs text-slate-400 sm:grid-cols-2"><div>Published: {date(selectedDoc.data.published_at)}</div><div>First observed: {date(selectedDoc.data.first_observed_at)}</div><div>Eligible from: {date(selectedDoc.available_at)}</div><div>Imported: {date(selectedDoc.ingested_at)}</div><div>Revision: {selectedDoc.data.revision}</div><div>Provider: {selectedDoc.data.provider}</div></dl><p className="my-6 whitespace-pre-wrap border-y border-slate-800 py-5 text-sm leading-7 text-slate-200">{selectedDoc.data.content}</p><p className="text-xs text-slate-500">{selectedDoc.data.usage_restrictions}</p><p className="mt-3 break-all font-mono text-xs text-slate-600">Content record: {selectedDoc.id}</p>{selectedDoc.data.source_url && <a className="mt-4 inline-block text-sm text-emerald-400" href={selectedDoc.data.source_url} target="_blank" rel="noopener noreferrer">Original source ↗</a>}</section></div>}
  </main>;
}
