# Baseline audit — 2026-10-27

Audit is based on inspected source and executed commands, not README claims. Initial working tree had an untracked screenshot and key file. Preserved both; no key contents inspected.

## Inventory

| Capability | Status | Evidence / limitation |
|---|---|---|
| FastAPI startup and health | VERIFIED_WORKING | `venv/bin/python` imports api.main; TestClient /health = 200 |
| LangGraph construction | VERIFIED_WORKING | app import constructs agent/graph.py; provider-backed graph run unverified |
| FinBERT local weights/tokenizer | VERIFIED_WORKING | offline AutoConfig/AutoTokenizer/AutoModel load, actual finite 3-class output; accuracy unverified |
| News/Reddit/SEC/ratings/macro integrations | PRESENT_UNVERIFIED | agent/nodes and agent/tools; no live provider checks performed |
| Groq/Bedrock synthesis | PRESENT_UNVERIFIED | agent/tools/llm_client.py; no paid/provider calls performed |
| Pinecone filing retrieval | PRESENT_UNVERIFIED | destructive latest-only cache; historical reproducibility BROKEN |
| Paper order path | PRESENT_UNVERIFIED | API and tool allow submission; must be disabled for V2 |
| Frontend lint | BROKEN | npm run lint: 18 errors |
| Frontend production build | PRESENT_UNVERIFIED | npm run build: sandbox port-binding error in Turbopack |
| MCP tools | PRESENT_UNVERIFIED | mcp_server/tools.py wraps backend endpoints |
| Historical backtest | MISSING | evaluation only contains trade summaries, no time-aware engine |
| Agent evals, durable jobs, cutoff validation | MISSING | no tests or persistence found |
| CI deployment configuration | PRESENT_UNVERIFIED | .github/workflows/deploy.yml import smoke only; no deployment attempted |

## Issues and reproductions

| ID | Severity | Expected vs observed | Owner |
|---|---|---|---|
| B01 | critical | /trade and alpaca_tool.place_order must refuse external execution; currently submit without research evidence checks | P0 |
| B02 | critical | model exception should fail; patched _get_pipeline raising RuntimeError instead yields neutral score .5 | P0 |
| B03 | critical | unavailable market/account inputs should prevent action; yfinance defaults VIX=20/yield=4.3/SPY=0/DXY=104; risk defaults account=100000/exposure=0 | P0 |
| B04 | high | both confidence and agreement required; BUY .9 with one neutral source returns PROCEED | P0 |
| B05 | high | exposure sizing must use remaining capacity and allow zero shares; allocates full cap and forces at least one share | P0 |
| B06 | high | advertised stop loss should be an actual order; place_order only returns it as metadata | P0: disable execution; no brokerage expansion |
| B07 | high | source versions should persist; SEC cache deletes old chunks before successful fetch; text limited to 3000 chars | P1; legacy not eligible for historical studies |
| B08 | high | daily Sharpe annualization is sqrt(252), not sqrt(252/n); irregular trade returns cannot establish portfolio performance | P5; legacy outputs excluded until repaired |
| B09 | high | portfolio return needs actual initial equity/cash flows; analytics assumes $100000 and pairs sells incorrectly | P5; legacy metrics excluded |
| B10 | high | secrets must not enter images; no .dockerignore and an untracked PEM exists in build context | P0 |
| B11 | medium | frontend lint should pass; nested components and any/effect violations | P0 |
| B12 | medium | documentation should reflect current graph/model: README hosted model and PROJECT_MAP technical/chart agents not current code | P6 documentation; label legacy claims now |

## Startup / dependency decisions

Existing backend: `venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000`.
Existing frontend: `cd frontend && npm run dev -- --hostname 127.0.0.1`.
Tests: no prior suite; use standard-library unittest plus installed httpx/TestClient.
Reuse FastAPI/Pydantic, Next.js, LangGraph, torch/transformers, FinBERT and adapters. SQLite adds no dependency. Avoid new queues/vector stores/tracing vendors. Pytest absent, unnecessary for baseline.
Remote provider availability, licensing and quota compliance require adapter-specific verification. `.env` values were not read or printed. Cached model inference is available; model training dataset provenance/calibration remains unverified.

## Remediation status after implementation

- B01/B06: external orders blocked unconditionally in both `/trade` and `alpaca_tool.place_order`; graph execution returns an explicit skipped result. Tests never submit an order.
- B02/B03: model/provider failures propagate explicitly; invented market/account defaults removed. Required unavailable inputs veto legacy sizing; V2 reports missing/failed states.
- B04/B05: critic requires confidence, agreement and risk evidence; remaining exposure capacity and zero-share outcomes enforced. Focused tests pass.
- B07: legacy destructive Pinecone cache remains excluded from historical research. V2 uses immutable source revisions and frozen historical subsets; cutoff/revision tests pass. No claim that the legacy cache was repaired.
- B08/B09: old brokerage analytics remain excluded. V2 simulation computes equity-based daily metrics with documented annualization and reconciled cash/positions. Legacy metric functions are not accepted evidence.
- B10: `.dockerignore` and Git ignores exclude local keys/configuration. Container build no longer silently downloads a model or ignores load failure. Docker runtime itself remains unverified (Docker CLI unavailable here).
- B11: frontend lint, TypeScript and webpack build passed after fixes and V2 integration. Default Turbopack restriction was resolved with supported webpack builds.
- B12: README now describes actual V2 status; original text preserved in docs/LEGACY_README.md; PROJECT_MAP.md explicitly marked historical.

Additional findings repaired: entity-mismatched exact quotes now fail verification; opposite sentiments within a near-duplicate group remain conflicting; local-model subprocess pipes close on cancellation; inherited remote tracing is disabled for V2.

Remaining audits: custom-model training/license provenance, human-reviewed grounding, visual/browser interaction, full requirement acceptance and remote CI/container runtime. These remain explicit rather than inferred from a passing unit suite.

## Supplied notebooks and boundary follow-up — 2026-10-28

Both notebooks are inspected in [NOTEBOOK_AUDIT.md](NOTEBOOK_AUDIT.md), with hashes, cell references and ranked findings. The training code names `yiyanghkust/finbert-tone`; the local CSV matches saved class counts but contains exact duplicates and conflicting labels. Exact training/export linkage and usage rights remain unresolved. The strategy notebook's earlier-price search, cross-ticker accounting, unsigned confidence aggregation and implicit SPY fallback are excluded from V2 acceptance. Originals were preserved.

A literal provider API key is present in the supplied strategy notebook. No value was printed or used. The untracked notebook is ignored by Git, and notebooks are excluded from container context. Docker build/runtime itself remains unverified.

Request rate limits were missing despite queue/time budgets; `api/rate_limits.py` now enforces rolling limits with separate cancellation capacity. `Jobs.retry` now enforces the same 20-run cap as initial admission. `tests/test_api_limits.py` and `test_retry_cannot_bypass_queue_capacity` cover these fixes. Latest suite: 56 tests, 54 passed / 2 explicitly skipped; actual-model API acceptance separately passed 16/16.
