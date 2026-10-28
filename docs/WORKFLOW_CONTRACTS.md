# Workflow contracts, tool traces and budgets

Validated locally on 2026-10-28; semantic quality and browser interaction remain separate acceptance items.

## Responsibilities and allowed operations

The application has fixed logical responsibilities. They are implemented with deterministic functions and an optional local classifier; they are not five independent generative LLMs. Source text cannot choose a function, SQL query, URL or shell command.

| Responsibility | Inputs | Validated output | Allowed operation / failure behavior |
|---|---|---|---|
| Evidence | Frozen snapshot and configuration references | `EvidenceOutput` | Read eligible local documents; reject missing/future evidence or document-budget overflow. |
| Sentiment | Selected documents, instruments, cutoff, model configuration | `SentimentOutput` | Extract entity spans, call baseline/local classifier/exact recorded replay; explicit uncertainty, conflict or abstention. Model failures fail the run. |
| Local inference | At most 100 texts, each at most 10,000 characters | `ModelOutput` | Fixed offline Python worker; 512-token truncation, CPU batches of 8. No source-directed commands or network credentials. |
| Quantitative | Frozen market references | `QuantitativeOutput` | Deterministic eligible close/previous-observation calculation. Missing or competing prices yield insufficient evidence. |
| Verification | Snapshot and structured sentiment results | `VerificationOutput` | Check source membership, entity, availability, content hash and exact spans. Never invent a replacement source. |
| Report | Validated results and initiating request | `ReportOutput` / `ResearchReport` | Reconcile instruments, counts, aggregation, counterevidence, signal policy, mode, partial status and source references. Recheck actual source spans and market numbers before acceptance. |

`research/outputs.py` validates intermediate results. `research/reports.py` validates final nested output and cross-field invariants. `research/report_validation.py` verifies the final report against the actual frozen snapshot, source text, market calculation, originating run and configured signal policy. A correctly shaped but unsupported number is rejected.

Run creation/status/cancellation/retry responses and step/tool queries have response models in `api/responses.py`. Reads revalidate stored reports against authoritative data; a corrupt report yields HTTP 500 with `invalid_response` and no source text or validation payload echoed. Other API domains still require complete response-contract audit; this is not a claim that every API response has a schema.

## Orchestration and time budgets

- `single_pass` has one graph node that calls the narrow tools. `verified` retains separate evidence/sentiment/quantitative/verification/report nodes. Both perform mandatory final citation and source checks.
- Run timeout defaults to 120 seconds, configurable 1–180. Step/tool timeout defaults to 60 seconds, configurable 1–90. Each nested call receives the minimum remaining run, step and parent-tool time. Retries cannot refresh that allowance.
- Local inference permits one retry by default, at most two. Cancellation is never retried. A failed attempt retains its own tool record even if a later attempt succeeds.
- Every graph step permits at most 30 tool calls. Fixed graph transitions and recursion limit 8 prevent open-ended discussion loops. There is no source-controlled tool dispatcher.
- Deterministic local work uses bounded input sizes and checks budgets before/after calls; it is not forcibly interrupted in the middle of an individual SQLite/validation operation. The inference subprocess is actively polled, killed and waited for on timeout/cancellation.
- Job admission separately caps active research runs at 20, including retries, and studies at 10. API rolling rate limits have a separate cancellation allowance; see `DEMO.md`.

## Durable trace behavior

Migration `005_tool_calls.sql` adds tool records linked to run, attempt, step and optional parent call. Each records input/hash, validated output, schema/configuration/snapshot references, start/finish time, latency, remaining budget, status and validation failures. Actual inference additionally records model identity, parameters and measured input-token count. Unknown cost stays null. Parent step model metadata refers to the same inference, not additional billable usage; do not sum repeated metadata across parent and child records.

The running record is committed before invoking the function. A trace-write failure prevents accepted completion. On restart, interrupted tool records become failed with `InterruptedProcess`; a subsequent attempt receives new records. Older attempts and reports are not rewritten to invent missing historical tool traces.

`GET /api/runs/{run_id}/steps` returns up to 100 steps (with their tool calls); `GET /api/runs/{run_id}/tools` returns up to 300 calls. Both support bounded `limit` and `offset` query parameters. The **Runs & traces** view expands each step into individual tools, inputs, validated outputs, failure states and timings. Browser rendering/interaction still needs visual acceptance.

## Verification evidence

`tests/test_report_contracts.py` rejects altered nested summaries, counterevidence, execution flags, modes, snapshot hashes, completion states, future market citations and plausible but incorrect prices. It checks API refusal of corrupt stored reports, exact frozen timestamp serialization, single-pass tool visibility, bounded trace queries, shared retry deadlines and interrupted-call history. Existing workflow tests cover cancellation, failure, idempotency and recovery.

`RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -v`: 64 tests passed in 43.558 seconds, including actual local model/replay and historical inference. `scripts.acceptance --real-model` passed all 16 checks with individual-tool completeness required. These demonstrate engineering behavior, not human semantic correctness, predictive returns or multi-agent superiority.

A subsequent SQLite-trigger fault test deliberately rejects a completed tool-trace write and verifies failed run status, no accepted report and an explicit step persistence error. The focused `test_report_contracts.py` suite then passed 9 tests in 1.840 seconds; application code remained unchanged after the full run.
