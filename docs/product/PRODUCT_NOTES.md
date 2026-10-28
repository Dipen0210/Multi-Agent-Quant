# Product notes for a later PRD

This is an evidence index and decision record, not the final PRD. Facts derive from the user-approved implementation scope and current repository; unresolved choices remain unresolved.

## Product intent

Help a researcher inspect company-specific sentiment and test whether a bounded agent workflow improves research over simpler alternatives. Support an engineer evaluating agents and a reviewer checking source/experiment validity. Positive trading returns and more agents are not success criteria.

## Supported scope and workflow

- Local single-user financial research and internal simulation; external orders are disabled.
- Fixed AAPL/MSFT/SPY universe, daily XNYS sessions, USD. Do not imply coverage of derivatives, intraday markets, delisted instruments or multi-user permissions.
- Import authorized evidence or load explicitly synthetic fixtures; choose instruments, question, cutoff and configuration; run bounded analysis; inspect exact citations, uncertainty, tool records and configured research signals.
- Freeze inputs for historical experiments and compare cash, passive exposure, direct sentiment and workflow/duplicate-handling variants under common accounting assumptions.
- Inspect diagnostic evaluations and immutable configurations; activate a previous configuration for subsequent runs.

Detailed acceptance criteria and stable IDs remain in [REQUIREMENTS.md](../REQUIREMENTS.md). UI interaction coverage is still unverified. The question field currently scopes a company-sentiment report; arbitrary financial reasoning is not a delivered capability.

## Decisions with supporting evidence

| Decision | Reason / evidence |
|---|---|
| Preserve FastAPI, Next.js, LangGraph and compatible local FinBERT | Existing stack and cached model are operational; see baseline/model audits. |
| Default to one research node with narrow validated tools | Synthetic staged-workflow comparison showed no added signal/return benefit; not proof about real-world generative agents. |
| Use direct eligible-evidence selection and SQLite | Bounded local corpus does not justify a separate retrieval service or distributed infrastructure. |
| Enforce timestamps, revisions, entity attribution and exact spans | Prevent future-data leakage and unsupported company attribution. Microsoft-positive text does not establish Apple sentiment. |
| Keep signal policy and accounting deterministic | Sentiment is not a calibrated return forecast or executable order. |
| Preserve unknown costs and explicit failure/partial states | Local compute is not priced; missing data and provider/model failures must remain visible. |
| Require full-release evidence separately from engineering checks | Provisional synthetic labels and passing tests cannot replace human grounding review. |

## Open items for the future PRD

- Human review of the semantic cases and representative real-world evaluation material.
- Original training-data source/rights, weights licensing and exact notebook/export linkage to the served checkpoint.
- Visual interaction acceptance, remaining response contracts and evidence/sentiment-history coverage.
- Full requirement audit and release-evidence accounting; initial gate thresholds remain explicitly provisional.
- Final file organization/dead-code cleanup with dependency and acceptance checks.

No dates, production SLOs, commercial-use permissions, accuracy guarantees, profitability targets or live-provider support should be invented when writing the PRD. Link measured outcomes to [EVALUATION_REPORT.md](../EVALUATION_REPORT.md), separate diagnostic from real inference, and keep deferred/blocked work explicit.
