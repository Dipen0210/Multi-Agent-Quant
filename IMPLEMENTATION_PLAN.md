# QuantSentiment V2 implementation plan

Authoritative requirements: [complete specification](docs/specs/MULTI_AGENT_QUANT_V2_CURSOR_PROMPT.md).
Scope: daily US equity research, bounded disclosed universe; local single-user application; no external orders. Preserve FastAPI, Next.js, existing model and useful adapters. No external deployment or paid calls as part of implementation.

## User additions — 2026-10-28

- Commit and push every major verified checkpoint to the existing GitHub repository. Use `codex/quantsentiment-v2` for implementation checkpoints; preserve upstream changes and avoid force-pushing or merging incomplete work into main. Git publication is now explicitly authorized; deployment and live trading remain excluded.
- At the end, organize the repository and remove demonstrably redundant/dead code. Map imports, entry points and references before removing code; preserve source notebooks/data and user artifacts locally. See `docs/maintenance/CLEANUP_PLAN.md`. This is required delivery work, not an optional follow-up.
- Prepare factual product notes and decision/evidence links for a later PRD. Do not describe provisional capabilities or unreviewed gates as accepted product requirements. See `docs/product/PRODUCT_NOTES.md`.

## Dependency order and gates

| Phase | Requirement family | Architecture / artifacts | Gate |
|---|---|---|---|
| P0 | BASE, SEC | Audit, fail-closed repairs, execution isolation, regression tests | documented startup, regression suite, frontend checks |
| P1 | DATA | SQLite migrations, immutable revisions, import validation, eligible frozen snapshots | idempotency, timestamp/revision/entity/quality tests |
| P2 | SENT, SIGNAL | retain verified FinBERT, explicit baseline, evidence spans, uncertainty, deterministic rules | labeled cases, inference test, no missing-input actions |
| P3 | AGENT, REPORT | persistent bounded jobs, validated steps, cancellation, source verification, reports | integrated report, recovery, failures, citation/cutoff tests |
| P4 | OPS, EVAL | local durable traces, versioned configuration, evaluation corpus and release gates | regression blocking, trace completeness, comparison and rollback |
| P5 | HIST | frozen daily long/flat simulation, baselines and ablations | accounting, timing/cost/corporate-action tests and validity disclosures |
| P6 | APP, DEMO | integrated UI, API boundaries, CI, documentation | actual UI acceptance, full workflow, reproducibility |

Minimal tracing and test infrastructure start in P0/P1. Independent work may proceed while optional remote integrations are blocked, but a phase is not verified until its entire gate passes.

## Decisions

- Reuse SQLite (Python standard library) for a local durable relational store. No additional service needed. Migration scripts will be versioned.
- Keep existing LangGraph implementation available as legacy code; new research responsibilities must be structured and bounded, not imitate brokerage orders.
- Default inference mode must explicitly identify deterministic fixtures, baseline, recorded replay, or real FinBERT/provider inference. Fixtures prove plumbing only.
- Research corpus initially uses direct eligible evidence selection; any keyword/vector retrieval addition requires comparisons. Existing Pinecone SEC code is retained but its historical cache is unsuitable for point-in-time claims.
- Retain FinBERT: actual cached weights and tokenizer loaded and produced finite class probabilities during baseline inspection. This is operational evidence, not accuracy/calibration validation.
- Use unittest with existing Python environment; no new test dependency needed.
- Current untracked screenshot and PEM file belong to user; preserve without reading secret contents. Exclude keys and local configuration from Git and container builds.

## Requirement ledger

`docs/REQUIREMENTS.md` maps each specification paragraph/bullet/table row to a stable ID, owning phase, status, implementation, and evidence. Do not mark groups complete based on narrow tests. Initial thresholds in evaluation configuration are provisional engineering targets, not approved product targets.

## Decisions made after measured checks

- Default new configurations to a single research node with validated narrow tools; retain staged role handoffs as an explicit comparison. The synthetic comparison showed no signal/return improvement from the additional verification handoff. Mandatory citation/cutoff checks remain in both paths.
- Evaluation gates are versioned in `evaluation/gates.json`. The initial diagnostic corpus is provisional authored data, not human-reviewed ground truth. Engineering CI is allowed to pass separately; full release remains blocked by missing mandatory evidence.
- Historical studies freeze all source versions, select only eligible revisions per cutoff, and preserve links to research runs and snapshots. Execution uses disclosed ex-post daily-open prices, prior available volume and explicit friction. Historical bars must be split-adjusted; dividends are excluded. Actual FinBERT is optional with knowledge-contamination limits disclosed.
- Default release scope is local single-user. No remote deployment performed. Legacy deployment workflow now requires explicit manual dispatch and a false-by-default deploy input.
- Visual QA remains unverified because Computer Use permissions were not granted. Do not retry those prompts without user authorization; screenshots supplied by the user can support visual review.

## 2026-10-28 audit decisions

- Add process-local rolling request limits with independent read/write/start/cancel allowances. Preserve cancellation under start/poll saturation. Enforce queue capacity for retries as well as new runs; both boundaries now have regression evidence.
- The supplied training notebook names `yiyanghkust/finbert-tone`; retain the served checkpoint's own label map. Profile and preserve the legacy CSV, whose duplicates/conflicting labels prevent accepting random-row accuracy as independent quality evidence. Do not retrain or substitute checkpoints to bypass missing provenance.
- Preserve both supplied notebooks. The strategy notebook's backward price search, cross-ticker holdings and unsigned-confidence aggregation disqualify its backtest as V2 evidence. Keep the transparent V2 simulator and controls; record findings in `docs/audits/NOTEBOOK_AUDIT.md`.
- Clarify the semantic review sheet's target entity without changing frozen labels. The user's request for explanation is not review approval.
- Report/run/trace contracts and single-pass tool records are now implemented and tested; see `docs/WORKFLOW_CONTRACTS.md`. Remaining audit priorities include other API response domains and integrated source timeline/sentiment-history coverage. Passing builds and API tests do not substitute for those requirements.

## Report and trace boundary decisions

- Validate final nested findings and reconcile reports against frozen source/market/configuration data before persistence and on API reads. Internal consistency alone cannot establish numerical grounding. Return a sanitized server error for corrupt stored reports.
- Keep individual tool records in a new migration rather than pretending a single graph-node record captures every call. Preserve interrupted attempts and record subsequent attempts separately. The simpler graph remains the default; tracing does not require extra autonomous agents.
- Apply nested remaining-time budgets to inference retries. A retry may use leftover parent time; it cannot allocate a fresh step budget. Keep deterministic local calls bounded and disclose cooperative rather than preemptive cancellation for those short operations.
