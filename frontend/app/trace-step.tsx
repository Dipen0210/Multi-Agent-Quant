type Json = Record<string, unknown>;
type ToolCall = {
  id: string; parent_call_id: string | null; tool_name: string; status: string;
  started_at: string; finished_at: string | null; latency_ms: number | null;
  data: { input: Json; output?: Json | null; validation_failures: string[]; resource_budget_seconds: number; tokens: number | null; cost: number | null; model_identifier?: Json | null };
};
export type Step = {
  id: string; role: string; status: string; attempt: number; latency_ms: number | null;
  data: Json; tool_calls?: ToolCall[];
};

function Payload({ title, value }: { title: string; value: unknown }) {
  return <details className="mt-3"><summary className="cursor-pointer text-xs text-slate-400">{title}</summary><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-950 p-3 text-xs text-slate-400">{JSON.stringify(value, null, 2)}</pre></details>;
}

export default function TraceStep({ step }: { step: Step }) {
  const calls = step.tool_calls ?? [];
  return <details className="mb-3 rounded-xl border border-slate-800 p-4">
    <summary className="cursor-pointer text-sm"><span className="capitalize">{step.role}</span> · {step.status} · attempt {step.attempt} · {step.latency_ms ?? '—'} ms</summary>
    <div className="mt-4 space-y-3">
      <p className="text-xs font-medium text-slate-300">Individual tool calls</p>
      {!calls.length && <p className="text-xs text-slate-500">{step.status === 'running' ? 'No tool calls recorded yet.' : 'No individual tool records were retained for this attempt. Inspect the step record below.'}</p>}
      {calls.map(call => <article key={call.id} className={`rounded-lg border border-slate-800 bg-slate-950/50 p-3 ${call.parent_call_id ? 'ml-4' : ''}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="break-all text-slate-200">{call.tool_name}</span><span className={call.status === 'completed' ? 'text-emerald-400' : call.status === 'failed' ? 'text-rose-400' : 'text-amber-300'}>{call.status} · {call.latency_ms ?? '—'} ms</span></div>
        <p className="mt-2 text-xs text-slate-500">Budget {call.data.resource_budget_seconds.toFixed(2)} s · Model tokens {call.data.tokens ?? 'unknown / not measured'} · Cost {call.data.cost === null ? 'unknown / not measured' : `$${call.data.cost}`}</p>
        <p className="mt-1 break-all text-xs text-slate-500">Started {call.started_at} · Finished {call.finished_at ?? 'pending'}</p>
        {call.parent_call_id && <p className="mt-1 break-all text-xs text-slate-500">Parent call: {call.parent_call_id}</p>}
        {call.data.validation_failures.length > 0 && <p className="mt-2 text-xs text-rose-300">Failure: {call.data.validation_failures.join(', ')}</p>}
        {call.data.model_identifier && <Payload title="Served model" value={call.data.model_identifier} />}
        <Payload title="Tool inputs" value={call.data.input} />
        {call.data.output && <Payload title="Validated output" value={call.data.output} />}
      </article>)}
    </div>
    <Payload title="Full step record" value={step.data} />
  </details>;
}
