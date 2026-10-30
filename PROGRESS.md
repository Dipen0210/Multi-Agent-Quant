# V2 progress

Updated 2026-10-29. Overall: **IN PROGRESS**. The full specification remains in scope; passing engineering checks do not establish full acceptance. This continuation made code, verification and provenance-audit progress.

## Added delivery requirements

The user now explicitly requests a commit and push at each major checkpoint to `https://github.com/Dipen0210/Multi-Agent-Quant`, final file organization/removal of redundant or dead code, and preparation for a later PRD. Work will use `codex/quantsentiment-v2`, preserve upstream commits and avoid force pushes or premature merges into main. Checkpoint publication is now authorized and done: CP001-CP005 are pushed to `codex/quantsentiment-v2`, remote head `98c9a2a`, with `main` untouched at `ce58f9e` and no pull request opened. Deployment/live trading remain unauthorized and are unaffected by source publication.

Final cleanup is required and unfinished: `docs/maintenance/CLEANUP_PLAN.md` inventories areas requiring dependency/reference checks before removal. `docs/product/PRODUCT_NOTES.md` collects factual scope, decisions, evidence and open items for the future PRD; it is not the final PRD. `docs/README.md` indexes the documentation.

Checkpoint preparation also found that one baseline API test used the normal runtime database. It now uses an isolated temporary database; all 6 baseline tests passed after that test-only repair. No application code changed relative to the report/trace acceptance hash below. A 96-file checkpoint selection was scanned for common credential patterns without displaying values; none were found. User notebooks, screenshot, keys, runtime data and generated files are excluded from that selection.

## Current implementation

- Critical baseline repairs block external orders, remove invented sentiment/market/account fallbacks, fix critic/sizing gates and reject invalid chunk parameters. Legacy brokerage analytics and destructive SEC cache behavior remain excluded from V2 rather than falsely marked repaired.
- SQLite migrations, immutable revisions, bounded imports, recorded-provider adapters, rejection receipts, duplicate groups and frozen cutoff snapshots are integrated. Universe: AAPL/MSFT/SPY, daily XNYS sessions. Demo news/prices are explicitly synthetic.
- Entity-specific sentiment, exact evidence spans, uncertainty/conflict/abstention, lexicon baseline and actual local FinBERT are integrated. Model scores are not calibrated return probabilities.
- Bounded LangGraph workflows, validated intermediate and final outputs, durable jobs, recovery, retries, cancellation, source verification and individual tool-call traces are integrated. Reports are checked against authoritative source/market/configuration data before acceptance and on API reads. Remote trace export is disabled. New configurations default to single-pass; staged roles remain a comparison option.
- Versioned diagnostic cases, per-class evaluation, provisional gates, injected citation/look-ahead defects, immutable configurations and rollback are implemented. The 20-case corpus still awaits human semantic approval.
- Frozen historical studies compare cash, passive exposure, direct sentiment, single-pass, staged verification and duplicate handling with consistent simulation assumptions. Accounting, timing, adjustment, fees/liquidity and calendar controls are implemented. No validated historical return or multi-agent superiority claim.
- Frontend includes research, evidence, reports, runs/traces, experiments, evaluations, configurations and system views. Legacy UI retained at `/legacy`. Browser interaction coverage remains unverified.

## Latest observed verification

Environment: `docs/ENVIRONMENT.json`. CP005 experiment-result integrity increment:

- `RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -v`: 85 passed in 67.316 s, no skips. Log: `runtime/verification/experiment-contract-tests.log`.
- `venv/bin/python -m scripts.acceptance --real-model --output runtime/verification/experiment-contract-acceptance.json`: all 16 checks passed. Current application hash: `a66ced3dd0e31d98ed393fe1b49faa6f1ea7f4e6f1d05a5dd7cb341eeba6daa3`.
- Focused `test_experiment_contracts.py`: 6 passed in 40.370 s. Log: `runtime/verification/experiment-contract-focused.log`.
- Focused historical replay tests: 3 passed in 12.851 s. Log: `runtime/verification/experiment-replay-focused.log`.
- OpenAPI generated with 29/29 typed V2 routes. Frontend unchanged since CP002's successful lint/build; browser interaction unverified.

Historical experiment results now carry typed contracts for per-partition ledgers, metrics, policies and end positions, with recomputed accounting identities. Validation reconciles equity curves against frozen market bars and signals against eligible frozen evidence, so an internally consistent result that contradicts its sources is rejected. Read-side validation does not rerun inference. Each execution carries its own identity, so repeated runs reproduce accounting while preserving separate run histories. Study lifecycle invariants are now shared between evaluation and experiment studies. Typed response coverage of `/api` routes is complete at 29/29; coverage counts remain a structural measure, not semantic acceptance.

Local commits: CP001 `58f6b1c`, CP002 `efe2cec`, CP003 `90d488e`, CP004 `0d3339a`. CP005 is being committed locally. Full release-evidence accounting, the requirement-level audit, final organization and the broader phase gates below remain incomplete. See `docs/audits/API_CONTRACT_AUDIT.md` and `docs/maintenance/CHECKPOINTS.md`.

## Changes in this continuation

- Added typed historical experiment results and shared study lifecycle contracts. Per-partition ledgers, metrics, policies and end positions are revalidated by recomputed accounting identities, then reconciled against frozen market bars and eligible frozen evidence. A changed close price or a flipped signal with recomputed, internally consistent accounting is refused, and the worker rejects wrong-source results before persistence rather than after. A completed study whose linked research report is missing returns a sanitized `invalid_response` error. Six focused contract tests, three focused replay tests and the full 85-test actual-model suite passed, with 16/16 acceptance checks.
- Gave each experiment execution its own identity so repeat runs over identical frozen inputs reproduce accounting without colliding run records or discarding either history. Study responses are now a discriminated union of evaluation and experiment studies; the study list is bounded and paginated. This completes typed response coverage of the `/api` surface at 29/29, which is a structural boundary result and not semantic or human-reviewed acceptance.
- Added full nested report contracts and cross-field invariants. Reconcile exact source spans, market calculations, run/snapshot identity and configured signal policy before persistence and when serving a report. Malformed or plausible-but-wrong stored reports return a sanitized `invalid_response` server error. Run, report and trace routes now have response schemas; other API domains remain to audit.
- Migration 005 adds durable per-tool records inside both single-pass and staged workflows, including nested model attempts, inputs/hashes, validated outputs, timing, status and remaining budget. UI expands tool records within each step; legacy records with no such data are explicit. Trace endpoints are bounded and support pagination.
- Retries share the remaining parent budget. Startup retains interrupted tool calls as failed and clears stale reports before retry. Nine new report/trace tests cover corrupted outputs, wrong numerical claims, API refusal, frozen snapshot serialization, tool visibility, budget exhaustion, recovery and trace-write failure. The first eight were in the 64-test full run; the final persistence-fault test passed in the subsequent 9-test focused run. Details: `docs/WORKFLOW_CONTRACTS.md`.

- Added configurable shared rolling request limits, HTTP 429 with Retry-After, bounded limiter memory and a separate cancellation allowance. Concurrent admission, expiry, proxy-header non-bypass and invalid configuration are tested. Defaults: 600 reads, 120 writes, 60 starts/retries and 60 cancellations per minute.
- Fixed retry admission bypassing the 20-active-run cap. A full queue rejects retries without changing the failed/cancelled run; cancellation can free a slot. Regression test exercises durable admission.
- Answered the user's review question: all current cases target AAPL, so positive Microsoft news does not support Apple sentiment. Added a target column and paired-target regression test. No frozen corpus labels or human-review statuses changed; the question is not approval.
- Inspected both user-supplied notebooks without execution or modification. `ModelSelection.ipynb` identifies `yiyanghkust/finbert-tone`; `tradingStrategy.ipynb` loads the saved fine-tuned directory. Exact served-revision linkage and data/weight licenses remain unresolved.
- Profiled legacy training data: 10,688 rows; 4,121 redundant exact rows; 516 distinct texts with conflicting labels. Saved notebook accuracy is not accepted as independent validation. Original strategy timing, aggregation and cross-ticker accounting defects are documented in `docs/audits/NOTEBOOK_AUDIT.md`.
- A nonempty API-key literal in the strategy notebook was not printed or used. Original preserved; exact notebook path excluded from Git staging and notebooks excluded from Docker context. The notebook was also excluded from the published branch, which was scanned for credential patterns before the push.

## Phase status and remaining gates

| Phase | Status | Remaining work / evidence |
|---|---|---|
| P0 baseline | in progress | Reconcile complete audit/requirement coverage with supplied notebooks and remaining legacy exclusions. |
| P1 data | in progress | Complete requirement-level coverage audit; current contract/import/cutoff checks pass. |
| P2 sentiment/signals | in progress | Human semantic review, dataset/weights licensing, exact checkpoint linkage and representative quality evidence. |
| P3 workflow/reports | in progress | Report/run/trace contracts, per-tool history and nested budgets now tested; finish requirement-level coverage and semantic grounding review. |
| P4 LLMOps/evaluations | in progress | Human-reviewed grounding; full metric/gate/trace audit and recorded review evidence. |
| P5 historical research | in progress | Final audit of simulator assumptions, comparisons and independent validity evidence. |
| P6 delivery | in progress | Frontend interaction/visual review, full response/API audit and clean-setup coverage. Docker runtime and remote CI unverified. |
| Final organization | not started | Required dependency/reference audit, file moves, dead-code removal, updated links/dependencies and post-cleanup acceptance; preserve user artifacts. |

`docs/REQUIREMENTS.md` retains stable IDs. Generic references cannot mark a whole requirement verified. Remaining technical priorities include response schemas for other API domains, integrated evidence timeline/sentiment history, release-evidence accounting and the full requirement audit. Per-tool visibility is implemented, but browser interaction is not verified. This is not a narrowed definition of done.

## User input and access boundaries

The user asked why two semantic cases differ and supplied both notebooks. Neither response approves labels or release gates. Outstanding provenance is narrowed to data origin/rights, weights licensing, training split/checkpoint linkage and historical cutoff; do not ask again for the identified base model.

Computer Use previously requested Accessibility/Screen Recording access. Do not retry without explicit authorization. User-supplied screenshots may support visual review; no screen permission is needed for code work. Preview services were started on 8001/3001, separate from existing 8000/3000. Backend was refreshed with CP004 code (session 66453); frontend session 98423. Dedicated preview database: `runtime/browser-demo.sqlite3`. Read-only HTTP checks passed. Inspect process identity and active jobs before any later preview restart. Automated acceptance uses isolated TestClient instances.

No deployment, real orders, weight redistribution or remote CI success is claimed. Full goal stays active and incomplete while independent technical audit work continues.
