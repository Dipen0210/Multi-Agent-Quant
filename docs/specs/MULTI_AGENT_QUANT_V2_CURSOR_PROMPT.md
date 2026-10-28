# Multi-Agent Quant Sentiment V2
## Master specification and execution instructions for Cursor

### Goal

Upgrade my existing Multi-Agent Quant Sentiment repository into a working, testable financial research application with evidence-grounded sentiment analysis, reliable agent orchestration, LLMOps, agent evaluations, and reproducible signal research.

Start by auditing the repository. Preserve functioning code and establish what actually exists. Then implement this specification in dependency order, testing and validating each phase before proceeding.

This document defines proposed requirements, not verified capabilities of the current repository. No repository audit has been performed by the author of this specification. Do not assume particular agents, models, frameworks, RAG pipelines, datasets, backtests, or integrations already exist.

The core objective is to determine whether an agent workflow produces more reliable, useful research than simpler alternatives. Additional agents and impressive-looking architecture are not success criteria. Positive trading returns are not a completion requirement.

## Scope and operating boundaries

Build a research and simulation application. Do not place real orders, connect a funded brokerage account, or enable autonomous live trading. Existing execution integrations must remain disabled by default and outside this release's acceptance workflow.

Preserve the repository's supported market and research purpose if coherent. If the market is undefined, document a bounded default of daily equity research using a fixed, clearly disclosed instrument universe. Do not quietly expand into options, derivatives, intraday trading, or global markets.

Required outcomes:

- Verified existing capabilities and remediated critical defects.
- Normalized, provenance-aware text and market data.
- Entity-specific sentiment with evidence and uncertainty.
- A bounded agent workflow with validated intermediate outputs.
- Evidence-grounded research reports and an integrated user interface.
- Versioned prompts, models, tools, datasets, and experiments.
- Agent-level and workflow-level evaluations with release gates.
- A reproducible historical research harness with explicit validity limits.
- A local demo that distinguishes synthetic fixtures, recorded outputs, and real inference.

Conditional additions:

- Add retrieval when the corpus and research questions justify it; otherwise retain direct evidence selection and document the decision.
- Add routing only after measured differences between task classes justify it.
- Add predictive-model training and model-registry infrastructure only when actual trainable models require them.
- Use live data providers only through supported, authorized access. Offline operation must remain possible.

## Phase 0: Inspect, establish a baseline, and repair

Read repository instructions, inspect Git status, and preserve unrelated user changes. Identify the actual runtime entry points before editing code.

Inspect:

- Backend, frontend, scripts, notebooks, configuration, dependencies, and deployment files.
- Agent definitions, prompts, tools, graph transitions, retry behavior, and termination rules.
- Market-data and text providers, cached data, licenses, quotas, and credential requirements.
- Sentiment models, checkpoints, preprocessing, label mappings, and model loading.
- Retrieval, embeddings, storage, citations, and source filtering if present.
- Signal generation, portfolio logic, backtests, execution integrations, and reported results.
- Existing tests, CI, logs, error handling, authentication, and access boundaries.

Produce `docs/audits/BASELINE_AUDIT.md` containing:

- Capability inventory labeled VERIFIED_WORKING, PRESENT_UNVERIFIED, BROKEN, MISSING, or NOT_APPLICABLE.
- File references for each finding and architecture description.
- Actual startup and test commands, their outcomes, and environmental blockers.
- Severity-ranked issues with reproduction steps, expected behavior, and observed behavior.
- Missing artifacts or credentials and which functionality they block.
- Claims in the README or UI that lack reproducible evidence.
- Dependencies proposed for reuse, replacement, or removal, with justification.

Do not infer functionality from filenames, class names, screenshots, or resume descriptions. A model artifact must load and produce valid outputs with the correct preprocessing before it is considered operational.

Fix defects that corrupt data, invalidate evaluation, break core workflows, expose secrets, or permit unintended execution before extending the affected components. Add focused regression tests for each fix. Lower-priority isolated issues may be explicitly deferred with an owner phase; do not call them resolved.

Acceptance: the supported baseline runs with documented commands, critical defects in the selected workflow are fixed, regression tests pass, and unsupported capabilities are explicit. Missing essential weights or datasets are blockers, not reasons to fabricate replacements.

## Product workflow

The user selects instruments, a research question, an information cutoff, and an analysis configuration. The application validates available data, gathers eligible evidence, performs sentiment and quantitative analysis, validates the result, and produces an auditable research report.

The user can inspect each claim, source, agent output, tool call, validation failure, and resource cost. Historical experiments use frozen inputs and explicit execution assumptions. Results can be compared across prompts, models, and workflow variants.

Primary users are a researcher investigating sentiment, an engineer evaluating agents, and a reviewer checking evidence and experiment validity. Avoid building unrelated portfolio-management or brokerage features.

## Data ingestion, provenance, and time

Implement adapters around sources already supported by the repository. Provide local JSON/CSV or Parquet imports and a small deterministic demo dataset. Add a live adapter only if supported access is available.

Use immutable identifiers, UTC timestamps internally, and explicit market timezone/calendar conversion. Keep source observations immutable; store corrections as revisions.

Text records should include source ID, provider, original identifier or URL, title, content reference, content hash, language, associated instrument IDs, entity-resolution status, publication time, first-observed time, ingestion time, revision identity, provenance type, and usage restrictions.

Market records should include instrument ID, exchange/calendar, interval, interval start/end, availability time, OHLCV where applicable, currency, source, adjustment policy, and quality flags. Preserve instrument identity through ticker changes where the data permits it.

Distinguish:

- When an event happened.
- When a publisher made information public.
- When the system could actually have received it.
- When the current application imported it.

A historical analysis may use only information eligible under its declared availability policy. A publication date alone does not establish historical availability. Imported historical datasets without first-observed metadata must be marked as approximations with a documented latency assumption, not certified point-in-time data.

Validate duplicates, revisions, missing timestamps, malformed prices, non-finite values, stale records, market holidays, unsupported instruments, symbol ambiguity, timezones, and missing source attribution. Never silently replace missing prices or evidence with plausible values. Use idempotent imports and retain rejection reasons.

Deduplicate syndicated and near-duplicate stories without losing provenance. Document how duplicated content affects aggregate sentiment. Treat raw volume of repeated stories separately from independent evidence.

For filings or other documents, preserve the exact version, publication/acceptance time when available, source location, and content hash. Later revisions must not leak into earlier research runs.

Acceptance: re-imports do not duplicate logical records, invalid data is rejected or quarantined, and cutoff tests exclude ineligible records and revisions.

## Sentiment engine

Audit existing sentiment methods before choosing replacements. Preserve working models and introduce a simple baseline appropriate to the available labeled data. Do not mandate a particular pretrained model or framework without checking compatibility and licensing.

Sentiment output must include:

- Target instrument/entity and text record ID.
- Label and score with documented semantics.
- Supporting text spans or source locations.
- Model and preprocessing versions.
- Timestamp and information cutoff.
- Status: supported, uncertain, conflicting, insufficient evidence, or failed.
- Confidence method, if any, and calibration status.

Separate sentiment toward the company, sentiment toward a specific event, and a hypothesis about future returns. Positive wording does not automatically imply a profitable long position.

Handle negation, mixed sentiment, comparative statements, quoted claims, guidance changes, ambiguous ticker mentions, and multi-company articles. Unsupported languages or document formats must return explicit statuses.

Do not present an LLM's self-reported confidence as a calibrated probability. Probabilities, uncertainty intervals, and calibration claims require suitable validation.

Aggregation must expose its time window, source weighting, recency policy, duplicate handling, coverage, and conflicting evidence. Fit or tune weighting policies using training/development data only.

## Agent design and orchestration

Inventory and retain useful existing roles. The following are logical responsibilities, not a requirement to create an LLM agent for every step:

| Responsibility | Required behavior |
|---|---|
| Evidence collection | Fetch eligible sources, resolve entities, validate provenance |
| Sentiment analysis | Produce entity-specific, source-grounded sentiment |
| Quantitative analysis | Call deterministic code for statistics and signal calculations |
| Evidence verification | Check citations, contradictions, timestamps, and unsupported claims |
| Report synthesis | Summarize accepted evidence, uncertainty, and research conclusions |

Use ordinary functions for deterministic validation, arithmetic, risk limits, and data processing. The LLM must not calculate authoritative portfolio metrics or enforce permissions.

Each retained agent needs a defined purpose, input/output schema, tool allowlist, timeout, retry policy, resource budget, and failure behavior. Use a bounded workflow with explicit state transitions and termination conditions. Repeated agent discussion without new evidence must terminate.

Validate every intermediate output before downstream use. Invalid JSON, missing required fields, nonexistent citations, and incompatible instruments are failures to handle, not text to pass blindly to another agent.

Persist run and step statuses such as queued, running, completed, partial, failed, and cancelled. Support cancellation, idempotent retries, and recovery from interrupted jobs without duplicating side effects. Display partial results as partial.

Record disagreement between agents when material. Majority agreement is not independent evidence. A verifier may challenge a claim but cannot invent replacement facts.

Compare the multi-agent design with a simpler workflow. If agents add no measured benefit, reduce the workflow and document the result instead of retaining complexity for appearances.

## Evidence retrieval and research reports

If retrieval is justified, preserve document identity, version, instrument applicability, publication/availability times, location, access scope, and chunk identity. Apply access, entity, and cutoff filters before retrieval results are supplied to the model. Retain metadata through ranking and generation.

Choose the simplest adequate search method first. Evaluate keyword retrieval against any proposed embedding or hybrid approach. Avoid adding a separate vector database where existing storage is sufficient.

Report fields:

- Research question, instruments, cutoff, run ID, and execution mode.
- Observed facts and evidence citations.
- Sentiment findings and source coverage.
- Quantitative observations computed by named tools.
- Hypotheses, counterevidence, and alternative interpretations.
- Uncertainty, unavailable data, and limitations.
- Optional research signal and its configured policy reference.
- Agent/model/prompt versions and trace reference.

Validate citation existence and source eligibility deterministically. Citation existence alone does not prove that a source supports the claim; evaluate claim support separately through reviewed examples and bounded semantic checks.

Do not expose private chain-of-thought. Store structured decisions, concise rationales, tool inputs/outputs under the data policy, and evidence references.

## Research signals and deterministic controls

Keep sentiment-to-signal conversion separate from report generation. Define signal horizon, eligible instruments, entry/exit timing, aggregation rules, thresholds, and no-signal conditions in versioned configuration.

If portfolio simulation is supported, enforce position sizing, concentration, leverage, liquidity assumptions, and cash constraints in deterministic code. Missing or stale required inputs must prevent a simulated action under the configured policy.

Do not treat a forecast, sentiment label, or narrative as an executable order. Internal simulated orders must be clearly labeled and isolated from any external execution interface.

Default new strategies to a simple bounded long/flat simulation where compatible with the audited project. Short selling, leverage, and complex instruments require explicit research assumptions and appropriate data; they are not automatic scope additions.

## Backtesting and experimental validity

Audit the existing engine first. Reuse it if correct; otherwise implement a minimal transparent event-driven or vectorized harness suited to the chosen frequency. Record the choice and assumptions.

Required controls:

- Chronological training, validation, and untouched test partitions.
- Train-only fitting for preprocessing, calibration, model selection, and signal thresholds.
- Purging or embargo where overlapping labels or horizons require it.
- Explicit decision and execution times, including after-hours news handling.
- No fills at a price preceding signal availability; same-bar assumptions require evidence.
- Transaction fees, spread/slippage assumptions, turnover, and liquidity limits.
- Corporate-action and price-adjustment consistency; avoid double-counting dividends.
- Universe-selection and survivorship-bias disclosure, including missing delisted assets.
- Missing observations, non-trading days, failed fills, and order-accounting checks.
- Currency and cash accounting, with reconciled positions and equity curves.

Separate benchmark validity tiers: synthetic pipeline tests, historical studies with limited availability metadata, and point-in-time validated experiments. Never combine them into one performance claim.

Modern pretrained language models may know historical outcomes. Timestamp-filtered retrieval does not eliminate this contamination. Record model provenance and knowledge-cutoff information when available, constrain tasks to supplied evidence, and disclose unresolved contamination. Do not call historical LLM-assisted returns leakage-free without sufficient evidence. Prospective frozen-policy evaluation is the stronger follow-up when feasible.

Compare, on consistent data and assumptions:

- Cash/no-trade and suitable passive benchmarks.
- A simple non-agent sentiment signal.
- A single-agent research workflow.
- The proposed multi-agent workflow.
- Ablations removing verification, retrieval, or other claimed contributors.

Report returns and risk metrics only where the experiment supports them. Include drawdown, volatility, turnover, exposure, costs, trade counts, and applicable risk-adjusted metrics with formulas and annualization assumptions. Keep classification quality separate from trading performance.

Report sample size, period, uncertainty, parameter-search history, and failure cases. Do not cherry-pick instruments or favorable windows. Where many strategies are tried, disclose selection effects and avoid unsupported significance claims.

A weak or negative result is acceptable if correctly measured. Do not optimize on the final test set to manufacture success.

## LLMOps and observability

Choose one primary tracing approach compatible with the repository. A supported tracing platform or a durable structured local trace store is acceptable; adding multiple overlapping platforms is not required.

Capture run/parent-step IDs, role, timestamps, prompt version/hash, provider/model identifier, model parameters, tool schema version, evidence IDs, data snapshot, retrieval configuration, retries, validation failures, completion status, latency, token usage, and cost when available.

Cost estimates require a dated rate source and calculation method. Unknown usage or cost must remain unknown, not zero. Redact secrets and restrict stored content according to provider and dataset usage terms.

Version prompts, tool contracts, orchestration, retrieval, evaluation datasets, and release configuration. Preserve exact served model identifiers when available. External model outputs may not be bit-for-bit reproducible; retain inputs, outputs, configuration, and repeated-run variability instead of promising determinism.

Provide trace inspection, evaluation comparison, model/prompt configuration rollback, and health visibility. Tracing failure must be explicit; it must not silently erase the audit trail of a supposedly accepted release.

## Agent evaluations and release gates

Build a versioned evaluation dataset with provenance, scenario IDs, eligible evidence, expected facts or labels, disallowed behavior, and scoring rubrics. Keep development and held-out evaluation sets separate. Do not use the same LLM's unreviewed answers as ground truth for itself.

Cover:

- Clear, neutral, mixed, and conflicting sentiment.
- Multi-entity articles and ambiguous symbols.
- Missing, duplicated, revised, stale, or future-dated evidence.
- Market-calendar and timezone boundaries.
- Provider timeouts, quota errors, malformed tool responses, and cancellation.
- Invalid citations, irrelevant evidence, and unsupported numerical claims.
- Tool misuse, cross-user access attempts where relevant, and prompt injection in sources.
- Insufficient evidence requiring abstention.
- Disagreement and repeated-loop termination.

Measure agent-level schema correctness, tool selection/arguments, citation validity, entity correctness, cutoff compliance, task success, and abstention. For labeled sentiment data, report appropriate per-class metrics and class balance; measure calibration only for meaningful probabilities.

Measure workflow-level grounding, claim support, contradiction handling, completeness, reproducibility, failure recovery, latency, and cost. Evaluate retrieval relevance only when retrieval exists. Run stochastic workflows repeatedly when needed to quantify variability.

Use deterministic checks for contracts, authorization, timestamps, budgets, and calculations. Use human-reviewed cases for meaning and grounding. LLM judges may assist but cannot be the sole authority; record their models, prompts, rubrics, and agreement with reviewed cases.

Create `evaluation/gates.yaml` or the repository equivalent. During baseline work, define concrete quality thresholds, regression tolerances, and performance budgets before evaluating held-out results. Treat initial thresholds as provisional engineering targets until approved; never imply user approval that was not given. Do not lower gates after failure without a documented, visible scope decision.

Release-blocking checks include forbidden execution paths, future-data contamination in controlled fixtures, permission failures, broken required contracts, invalid citation acceptance, and material baseline regressions. Deliberately inject a known fault and show that CI blocks it, then restore the correct code.

## Application, persistence, and APIs

Preserve the existing frontend and backend frameworks when practical. Use a modular application with isolated background work for long runs. Avoid introducing microservices, Kubernetes, or message infrastructure without a demonstrated requirement.

Provide integrated views for:

- Research dashboard and data-source freshness.
- Instrument evidence, source timeline, and sentiment history.
- Research-run creation, progress, cancellation, and reports.
- Agent traces and validation failures.
- Experiments, baseline comparisons, and backtest assumptions.
- Evaluation results, configuration versions, and system health.

Clearly label loading, empty, failed, partial, offline, synthetic, recorded, and live states. Do not fill dashboards with invented production metrics. Existing streaming must handle reconnects and resource cleanup.

Logical entities include Instrument, SourceDocument, DocumentRevision, MarketObservation, DatasetSnapshot, SentimentResult, ResearchRun, AgentStep, ToolCall, EvidenceReference, ResearchSignal, SimulationRun, SimulatedOrder, EvaluationCase, EvaluationRun, ConfigurationVersion, and AuditEvent. Add retrieval entities only if needed.

Use migrations, validated schemas, foreign-key relationships where appropriate, and durable references between reports, traces, and experiment inputs. Do not force a database migration solely to match a suggested stack.

Illustrative API domains, to reconcile with existing routes:

- Instruments and evidence queries.
- Data import and source health.
- Research-run creation, status, cancellation, and report retrieval.
- Trace and step inspection.
- Experiment creation and result comparison.
- Evaluation execution and results.
- Configuration versions and release status.

Validate requests and responses. Use structured errors, bounded queries/uploads, path and URL validation, and authorization for non-public resources. Keep provider credentials server-side. If only single-user local deployment is supported, bind securely and document that limitation; do not claim multi-user isolation without implementing and testing it.

## Security and operational resilience

Treat documents, news, retrieved text, and tool outputs as untrusted data. They cannot override system instructions, widen tool permissions, or reveal secrets.

Use narrow tools and server-side validation. No arbitrary shell execution, unrestricted SQL, or unrestricted URL fetching through an LLM. Protect importers against path traversal and source fetchers against server-side request forgery. Cap payload size and resource consumption.

Enforce configured per-run budgets, rate limits, timeouts, bounded retries, and cancellation. Honor provider terms and data licenses. Do not bypass authentication, paywalls, or access restrictions.

Protect secrets in configuration, logs, traces, exports, and tests. Supply an `.env.example` containing placeholders only. Do not read or print secret values to prove that configuration exists.

## Demonstration and validation modes

Provide a deterministic offline dataset containing normal, conflicting, insufficient-evidence, and adversarial scenarios. Freeze expected behavior separately from model-generated answers.

Distinguish modes throughout the API and UI:

- Offline deterministic fixtures validate plumbing and policy behavior.
- Recorded provider outputs validate replay, not current provider inference.
- Real model inference uses an actual local model or configured provider.
- Historical evaluation uses its declared data-validity tier.

No-key demo success does not establish live LLM integration quality. If credentials are unavailable, complete independent work and mark real-provider validation blocked. Preserve the ability to test it later with documented commands.

## Implementation phases and gates

| Phase | Work | Required completion evidence |
|---|---|---|
| Baseline and remediation | Audit, startup, defect fixes, regression tests | Reproducible baseline and issue status |
| Data foundation | Contracts, imports, provenance, deduplication, cutoff enforcement | Invalid/future/revised-data tests and durable snapshots |
| Sentiment and signals | Verified models, labeled outputs, aggregation, deterministic signal rules | Baseline comparison and correct uncertainty/status handling |
| Agent workflow and reports | Bounded orchestration, tools, verification, evidence reports | Integrated run with citations, failure handling, and cancellation |
| LLMOps and evaluations | Traces, versions, evaluation datasets, gates, rollback | Trace completeness and demonstrated regression blocking |
| Historical research | Time-aware simulation, baselines, leakage controls, ablations | Reproducible experiment with accounting and validity disclosures |
| Integration and delivery | UI integration, security, CI, deployment, demo | Full acceptance workflow and documented limitations |

Build minimal tracing and test scaffolding alongside earlier phases; the dedicated phase completes and validates them. Do not defer observability until every agent has already been implemented.

For every phase: explain affected files and architecture changes, implement, run relevant tests, debug, verify the gate, and update progress. A dependency-blocked phase is not complete. Continue independent work where possible without bypassing required dependencies.

## End-to-end acceptance workflow

Start from a clean documented local setup. Import a frozen fixture dataset and verify idempotency. Choose an instrument and cutoff. Include an otherwise relevant article that becomes available after the cutoff and prove it is excluded.

Run analysis through the actual application. Inspect sentiment evidence, agent steps, deterministic tool calculations, and the final report. Verify that citations resolve to the exact eligible source versions. Confirm conflicting evidence and uncertainty are visible.

Repeat with missing required evidence and show appropriate abstention or a partial result. Inject a provider failure and confirm bounded retries and honest error reporting. Cancel a run and confirm work stops without duplicate jobs or corrupt state.

Run a frozen research strategy through the simulator, compare it against the declared baselines, and reconcile positions, cash, costs, and reported metrics. Show that a known look-ahead bug fails a test.

Run the evaluation suite. Introduce a deliberate invalid-citation or future-data regression and demonstrate release rejection. Restore the code and rerun required checks.

Complete a real-model integration test when a legitimate model or provider is available. Otherwise record that part as blocked. Never describe deterministic fixtures as trained-model validation.

## Execution rules for Cursor

Work autonomously within this specification: Plan → Implement → Test → Debug → Validate → Continue.

Maintain these repository artifacts, adapting paths to existing conventions:

- `IMPLEMENTATION_PLAN.md`: dependencies, scoped work, architectural decisions, and gates.
- `PROGRESS.md`: each requirement's status, evidence, remaining work, and blockers.
- `docs/audits/BASELINE_AUDIT.md`: initial findings and remediation references.
- `docs/EVALUATION_REPORT.md`: commands, datasets, configurations, actual results, and limitations.
- `docs/DEMO.md`: reproducible startup and acceptance walkthrough.

Use stable requirement IDs and map every mandatory requirement to implementation locations and verification evidence. Statuses must distinguish not started, in progress, verified, failed, blocked, deferred, and not applicable. Every not-applicable designation needs a reason consistent with this specification.

Do not overwrite user work, discard artifacts, rewrite the repository wholesale, or replace working models without evidence. Do not publish, deploy externally, incur unapproved spending, or enable live trading as part of routine implementation.

For tests, record the exact command, environment/configuration identity, outcome, and relevant artifact. Syntax checks alone do not establish functionality. Run backend tests, integration tests, applicable frontend checks/builds, and the end-to-end workflow. Use browser testing when available; otherwise mark interaction coverage unverified.

Do not fabricate model weights, credentials, provider responses, datasets, performance metrics, citations, test outcomes, or successful deployment. Mocking is valid for isolated tests only when labeled; it does not satisfy a real-integration gate.

When blocked, explain the affected requirement, attempted approaches, missing input, and smallest next action needed. Stop only affected work and continue independent tasks. Never weaken tests, remove failing requirements, or substitute fabricated data to declare completion.

At session boundaries, update progress so a new agent can resume from the last verified state. Report concise evidence-based status, not a list of claimed features.

## Definition of Done

The core application runs locally with the documented setup, preserves verified existing functionality, and completes the acceptance workflow. Data provenance, cutoff rules, agent contracts, citations, execution boundaries, and failure handling are tested. LLMOps traces and versioned evaluations are usable. Historical experiments are reproducible within their declared limits and compared with simpler baselines.

Every mandatory requirement is verified with evidence. Any blocked requirement means the overall project remains incomplete; explicitly deferred optional integrations do not masquerade as delivered features. The final report identifies what works, what was tested, what did not improve, and what remains unvalidated.

Begin now with repository inspection and Phase 0. Do not begin by generating an unrelated replacement application.
