# QuantSentiment V2 — Financial Research Workspace

A local research and simulation application built on the existing **FastAPI, Next.js, LangGraph and FinBERT** project. V2 turns timestamped source evidence into inspectable sentiment reports, traces and frozen research experiments.

**Status: implementation in progress.** API acceptance and engineering checks have passed locally; human semantic review, visual verification and the final requirement audit remain incomplete. This is not a validated trading strategy. External brokerage orders are disabled.

## What is implemented

- Immutable document revisions and market observations, UTC/availability checks, bounded JSON/CSV and recorded-provider imports, duplicate groups and frozen datasets.
- Entity-specific sentiment with exact source spans, conflicting/uncertain/insufficient statuses, a transparent lexical baseline, actual cached FinBERT inference and exact-input replay.
- Single-pass and staged LangGraph workflows with validated tool outputs, persistent runs, cancellation, bounded retries, recovery, local traces and versioned configurations.
- Daily long/flat simulation with chronological partitions, next-open timing, fees/spread/slippage, liquidity/cash constraints and reconciled equity curves.
- Comparisons with cash, passive exposure, direct sentiment and workflow/duplicate-handling ablations; explicit synthetic or limited-metadata validity labels.
- Versioned diagnostic evaluations, per-class metrics, provisional engineering gates and tests that reject injected citation/look-ahead defects.
- Integrated research, evidence, traces, experiments, evaluations, configuration and health views.

The fixed universe is AAPL, MSFT and SPY, at daily frequency. Existing legacy provider code is retained, but unvalidated legacy brokerage analytics are excluded from V2.

## Run locally

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci
```

From the project root:

```sh
venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm run dev -- --hostname 127.0.0.1 --webpack
```

Open http://127.0.0.1:3000 and load the explicitly synthetic demo. The deterministic mode needs no keys. Actual FinBERT inference requires legitimately available cached model/tokenizer files; missing artifacts produce a failure, not fabricated outputs.

## Verify

```sh
venv/bin/python -m unittest discover -s tests -v
venv/bin/python -m scripts.acceptance --real-model
venv/bin/python -m evaluation.run --scope engineering
cd frontend && npm run lint && npm run build
```

See [demo and acceptance](docs/DEMO.md), [evaluation evidence](docs/EVALUATION_REPORT.md), [model provenance](docs/MODEL_PROVENANCE.md), [progress](PROGRESS.md), [implementation plan](IMPLEMENTATION_PLAN.md) and [requirement ledger](docs/REQUIREMENTS.md).

[The original README and legacy screenshots](docs/LEGACY_README.md) and PROJECT_MAP.md are historical context, not current capability evidence. No production deployment, profitable return, calibrated confidence or multi-agent superiority is claimed.
