# Local demo and acceptance

Status: implemented API workflow; final semantic and visual acceptance remains incomplete. See PROGRESS.md, EVALUATION_REPORT.md and REQUIREMENTS.md.

## Setup

Python 3.13 and Node 22 are the CI targets. The observed local environment is recorded in ENVIRONMENT.json. Use a project virtual environment and the committed frontend lockfile:

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

No provider keys are needed for the deterministic baseline. `.env.example` contains optional legacy provider placeholders. Do not paste keys into the frontend. V2 trace records remain local regardless of legacy LangSmith environment settings.

Start exactly one backend worker, bound to loopback:

```sh
RESEARCH_DB=runtime/research.sqlite3 venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm run dev -- --hostname 127.0.0.1 --webpack
```

Open http://127.0.0.1:3000. This is a single-user local application, without multi-user isolation. Do not bind it to a public interface or deploy it as a shared service. External brokerage orders are blocked even if old credentials are present.

For isolated alternate ports, set `RESEARCH_ALLOWED_ORIGINS=http://127.0.0.1:3001` on the backend and `NEXT_PUBLIC_API_URL=http://127.0.0.1:8001` on the frontend. `NEXT_DIST_DIR=.next-v2-preview` can keep a preview separate from another Next.js build.

The server enforces shared rolling 60-second request limits: 600 reads, 120 other writes, 60 research/evaluation/experiment starts or research retries, and 60 cancellations. Configure these with `RESEARCH_RATE_READ_PER_MINUTE`, `RESEARCH_RATE_WRITE_PER_MINUTE`, `RESEARCH_RATE_START_PER_MINUTE`, and `RESEARCH_RATE_CANCEL_PER_MINUTE` (integers 1–10000). Rejections return HTTP 429, a structured `rate_limited` error and a `Retry-After` header. Starts and polling cannot consume the separate cancellation allowance. Health checks and the always-denied trade endpoint are exempt. These limits are process-local, reset on restart, and do not establish distributed or multi-user quotas. Queue admission independently caps active research runs at 20 (including retries) and studies at 10.

## Interactive workflow

1. Choose **Load synthetic demo**. The import receipt distinguishes inserts, duplicates and rejects. Repeat to see idempotency.
2. Select AAPL and cutoff `2025-01-03T22:00:00Z`, synthetic provenance, and the deterministic baseline. Start research.
3. Inspect the partial report: positive and negative evidence conflict; unsupported language/instruction-like content is explicit; no trade signal is issued.
4. Open **Inspect source**. Compare publication, observation, eligibility and import times. The late article and later revision are excluded from this cutoff. Source text and exact offsets remain inspectable.
5. Select an empty cutoff such as `2024-12-31T22:00:00Z`. Missing evidence yields a partial result and NO_SIGNAL.
6. Inspect **Runs & traces**. Expand a step to inspect its individual tool calls, inputs, validated outputs, nested model attempts, timings and failures. Even single-pass research retains separate tool records. Unknown usage/cost is unknown, not zero. Older attempts without these records are explicitly labeled. See `WORKFLOW_CONTRACTS.md` for schemas, budgets and paginated trace endpoints.
7. In **Experiments**, choose SPY with the default synthetic date range and split dates. The example intentionally exercises simulated fills. Compare cash, passive exposure, direct sentiment, single-pass, staged verification and the duplicate-handling ablation. These invented prices/news test accounting only.
8. In **Evaluations**, run the deterministic baseline or real local FinBERT. Inspect each case and gate. Full release remains incomplete while semantic review and final acceptance evidence are missing.
9. Configuration activation rolls back the default for subsequent API runs; previous runs keep their immutable configuration. Existing persisted selections are not overwritten by code changes.

Research questions are bounded to company/fund sentiment analysis. The report template displays the question; it does not claim arbitrary open-ended reasoning or autonomous financial planning.

## Real inference and replay

The current environment has the custom FinBERT checkpoint cached. A new machine must legitimately obtain the model/tokenizer before selecting real inference; the application does not silently download replacements. See MODEL_PROVENANCE.md for the unresolved licensing/training provenance and exact observed revision.

```sh
RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -p test_real_inference.py -v
```

This runs actual local inference, exact-input recorded replay, and a small synthetic historical workflow using the actual model. It does not establish real-world accuracy or leakage-free returns. The model worker uses offline loading and a bounded cancellable subprocess. Missing weights fail explicitly.

## Automated acceptance

```sh
venv/bin/python -m unittest discover -s tests -v
venv/bin/python -m scripts.acceptance --real-model --output runtime/acceptance-real.json
venv/bin/python -m evaluation.run --scope engineering
cd frontend
npm run lint
NEXT_DIST_DIR=.next-verify npm run build
```

The acceptance command uses the actual FastAPI application and an isolated temporary SQLite database. Imported prices/news are labeled synthetic; provider failure/cancellation cases are explicitly mocked; the `--real-model` step performs actual inference. Its output checks cutoff exclusion, exact citations, conflict/abstention, bounded retries, cancellation, linked experiments, nonzero simulated fills, cash reconciliation, evaluations, mutation rejection and external order isolation.

Reports are validated again when served. A stored report that violates its schema, frozen inputs, source spans, market calculations or configured signal policy returns `invalid_response` instead of being shown as accepted research. New startups apply migration `005_tool_calls.sql`; restart a previously running backend to use the current code and schema. Run only one worker for a given database.

## Prove regression blocking

Both injected-fault commands must exit 1. They patch only their isolated check scope and restore the real implementation afterward:

```sh
venv/bin/python -m evaluation.run --inject-fault invalid-citation --output runtime/evaluation/invalid-citation.json
venv/bin/python -m evaluation.run --inject-fault lookahead-fill --output runtime/evaluation/lookahead.json
venv/bin/python -m evaluation.run --scope engineering --output runtime/evaluation/restored.json
```

A passing engineering gate is not full release approval. `--scope full-release` intentionally rejects the current incomplete acceptance state.

## Imports and data validity

- JSON imports contain `documents` and/or `market` arrays following `/docs` schemas; CSV imports use JSON-encoded array cells.
- Recorded provider payloads can be normalized through `/api/imports/recorded` for Tavily, Reddit, SEC EDGAR and yfinance. Missing publication/capture metadata is quarantined, not guessed.
- Inputs are bounded to 2 MB per request and limited record counts. No importer accepts arbitrary server file paths or executes source text.
- Historical availability without observation metadata requires an explicit latency assumption and is labeled approximate.
- Historical simulations require split-adjusted price-only bars. Dividends are excluded; total-return bars are rejected to avoid ambiguous/double-counted accounting. Raw prices are accepted only for clearly labeled synthetic tests.
- There are no live-data polling adapters enabled by default. Provider access/licensing/quotas must be verified before adding live acquisition.

## Unverified coverage

No deployment or remote GitHub CI success is claimed. Computer Use permission was not granted; visual browser interaction remains unverified. User-provided screenshots can be reviewed without that permission. Human-reviewed semantic cases and custom-model training/license provenance still require evidence.
