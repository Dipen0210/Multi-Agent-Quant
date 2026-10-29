# Evaluation report — implementation in progress

Environment snapshot: `docs/ENVIRONMENT.json`. All figures below are observed local results, not production or financial performance claims.

## Latest checks — data response checkpoint, 2026-10-29

- `RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -v`: 68 passed in 38.493 s, no skips; includes actual local inference, exact replay and historical model integration. Log: `runtime/verification/data-response-tests.log`.
- `venv/bin/python -m scripts.acceptance --real-model --output runtime/acceptance-real.json`: all 16 checks passed. Backend hash: `ec21a1bd5073b2d74405150f7e63dad64f15adf1a8b36962200a892f304daec8`.
- Focused data API suite: 6 passed in 0.762 s. Frontend lint and `NEXT_DIST_DIR=.next-verify npm run build` exited 0 after the source-health display change.
- Read-only HTTP checks of the local preview returned 200 for the frontend, API health, source-health and OpenAPI; external execution false. Visual interaction remains unverified. Remote push/CI remains blocked by publication approval.

See `audits/API_CONTRACT_AUDIT.md` for response validation scope and remaining routes. The prior results below are historical, not the latest backend identity.

## Latest checks — 2026-10-28

- `RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -v`: all 64 passed in 43.558 s, none skipped. Includes actual local inference, exact replay and model-backed historical research, plus eight new report/trace boundary cases. Retained log: `runtime/verification/report-trace-tests.log`.
- Subsequently added a SQLite trace-write failure regression; `venv/bin/python -m unittest discover -s tests -p test_report_contracts.py -v` passed all 9 focused cases in 1.840 s. The application code did not change after the full run. This verifies that failed trace persistence prevents an accepted report. OpenAPI generation also passed with typed run/report/trace schemas present.
- `venv/bin/python -m scripts.acceptance --real-model --output runtime/acceptance-real.json`: exit 0, all 16 checks passed. Individual tool records are now required by trace completeness. Actual model mode is `real_local_inference`; synthetic inputs and mocked failure/cancellation scenarios are labeled. Code hash `a6c0d55d6fcb33b03b3bbd4a395a27d443430b6e6d57d09f1099e156d3cc5eb0` matches the current backend.
- `cd frontend && npm run lint`: exit 0. `cd frontend && NEXT_DIST_DIR=.next-verify npm run build`: exit 0, including TypeScript and static generation. These commands do not exercise browser interactions.
- Both notebooks were inspected without execution. `venv/bin/python -m scripts.audit_training_data` produced the archived data-quality profile. Its duplicate/conflicting-label findings qualify the notebook's saved 0.88 accuracy; that metric was not reproduced or accepted as V2 evidence. See `audits/NOTEBOOK_AUDIT.md`.

Older observations below are retained as historical evidence. Latest combined counts and acceptance above supersede earlier counts. Full release remains incomplete.

Command receipt: `runtime/verification/report-trace-checks.json`. The report/trace tests verify nested corruption rejection, a plausible but wrong market price, refusal to serve a corrupt persisted report, exact snapshot identity through serialization, individual tool visibility, retry deadlines and interrupted-call recovery. This does not replace human claim-support review. See `WORKFLOW_CONTRACTS.md` for scope and remaining API coverage.

## Commands already executed

| Command | Observed result | Artifact / scope |
|---|---|---|
| `venv/bin/python -m unittest discover -s tests -v` (before simulator additions) | 32 tests, 31 passed, real-model test explicitly skipped | Deterministic baseline/API/contract/recovery tests |
| `RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -p test_real_inference.py -v` | 1 actual local inference + recorded replay check passed | Real cached FinBERT, not a mock |
| `venv/bin/python -m evaluation.run --scope engineering --output runtime/evaluation/baseline-heldout.json` | Passed; 12/12 provisional fixture outcomes matched | 12 synthetic heldout cases; no model quality claim |
| `venv/bin/python -m evaluation.run --engine finbert --scope engineering --output runtime/evaluation/finbert-heldout.json` | Passed provisional engineering threshold; 11/12 fixture outcomes matched | Actual inference; 8.007 s observed runtime |
| `venv/bin/python -m evaluation.run --scope engineering --inject-fault invalid-citation --output runtime/evaluation/injected-fault.json` | Expected exit 1; invalid-citation check failed | Mutated verifier was rejected; no gate threshold lowered |
| `venv/bin/python -m unittest discover -s tests -p test_evaluations.py -v` | 4 passed | Includes restoration and same-bar look-ahead mutation rejection |
| `venv/bin/python -m unittest discover -s tests -p test_simulation.py -v` | 6 passed | Timing, cash, fees, liquidity, gaps, adjustments, partition/embargo |
| `venv/bin/python -m unittest discover -s tests -p test_experiments.py -v` | 3 passed | Frozen reproducibility, linked research runs, revisions, studies API |
| `cd frontend && npm run lint` | Passed after studies UI addition | No browser interaction claim |

Raw artifacts live in ignored `runtime/evaluation/` and are reproducible with the above commands. Runtime varies by machine. New changes require checks appropriate to their scope; older counts do not establish verification of later edits.

## What the measurements mean

The corpus contains 8 development cases and 12 heldout diagnostic cases. It was frozen before the first heldout evaluation; no thresholds or preprocessing were tuned after seeing those results. Expected labels were authored for testing and are **not human-reviewed ground truth**. The 100% baseline result is unsurprising on simple authored lexical cases and is not evidence of real-world superiority. FinBERT's one mismatch is retained, not relabeled or hidden. Class balance, confusion matrices, per-class precision/recall/F1, abstention, schema checks, safety checks and latency are saved in the result artifacts. Unknown cost remains null.

Full release stays incomplete. Human semantic review, broader representative data, final historical validity review, visual acceptance and the requirement-by-requirement audit remain outstanding. The automated historical acceptance walkthrough has passed on synthetic fixtures.

## Workflow comparison

The synthetic experiment compares direct non-agent sentiment, single-pass orchestration, staged verification, no-deduplication ablation, cash and passive exposure under common timing/cost assumptions. Repeated runs yielded identical numerical outputs in the tested fixture. Single-pass and staged variants had identical signals/returns; the extra stage did not establish added research value. New configurations therefore default to the simpler single-pass path. The staged path remains explicitly selectable for inspection and comparisons. Existing persisted user-selected defaults are not overwritten.

This is an orchestration ablation of shared deterministic logic, **not** a benchmark of independent generative agents. More meaningful reviewed comparisons remain required. No profitability, significance, or leakage-free historical LLM claim is made.

## CI status

`.github/workflows/ci.yml` now defines backend regression checks, engineering gates, invalid-citation and look-ahead mutation checks, restoration, and frontend lint/build. Its commands have been run locally as described; remote GitHub Actions execution is unverified because no push or deployment was performed. Legacy AWS deployment is manual and disabled by default.
