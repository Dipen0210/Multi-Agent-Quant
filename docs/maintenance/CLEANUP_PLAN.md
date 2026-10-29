# Required final repository cleanup

Added at the user's explicit request on 2026-10-28. Status: **not complete**. Perform the cleanup after the remaining functionality is integrated; do not delete files merely because their names look old.

## Intended organization

Keep application packages under `api/`, `research/` and `frontend/`; evaluations under `evaluation/`; tests under `tests/`; repeatable commands under `scripts/`. Documentation belongs under `docs/` with `specs/`, `audits/`, `product/` and `maintenance/` subdivisions. Root should retain only entry-point configuration, README/license and requested plan/progress files.

## Inventory requiring a disposition

| Area | Current dependency / next check |
|---|---|
| `agent/` | Legacy opt-in graph and baseline regression imports still use it. Map each module before removing or isolating it; retain verified functionality until replacements are demonstrated. |
| `api/routes/ask.py`, `stream.py`, `api/sse.py` | Opt-in legacy analysis path. Decide whether to retain a documented compatibility surface or remove it with the matching UI/tools and migration notes. |
| `api/routes/analytics.py`, `portfolio.py`, `evaluation/metrics.py`, `paper_trade_report.py` | Old metrics are excluded from V2; check every caller, remove dead code and stale claims together. |
| `frontend/app/legacy/`, `analytics/` | Preserved legacy views. Check navigation and endpoints before retaining or removing them. |
| `mcp_server/`, `huggingface/`, `infra/` | Separate legacy integrations/deployment entry points, not proven dead merely because V2 does not call them. Record reuse/removal decisions and check supported startup paths. |
| `frontend/public/` | Remove unused starter assets only after searching imports, URLs and metadata references. |
| `ModelSelection.ipynb`, `tradingStrategy.ipynb`, `Data/` | User-supplied provenance material. Organize sanitized shareable copies with a manifest when rights/credentials allow; preserve originals locally. Never publish an embedded key or call training material an untouched test set. |
| Root screenshot and PEM | User-owned artifacts. Preserve in a suitable ignored local location during final organization; never publish the key. Do not delete these as code cleanup. |
| Runtime/build/cache directories | Already ignored; remove only task-owned generated artifacts after checking live processes. Do not remove active preview data or the user's environment without a reason. |
| Documentation | Consolidate stale progress/history, preserve original specification and provenance evidence, update all links after moves. Keep PRD notes distinct from verified acceptance. |

## Completion evidence

1. Import/entry-point/reference map and explicit disposition for each area.
2. Moves/removals recorded in a cleanup checkpoint; no unrelated user work lost.
3. Dependency manifests and docs updated to the final structure.
4. Backend, real-model integration where available, frontend checks and end-to-end acceptance pass after affected changes.
5. No accidental secrets, notebooks with credentials, databases, weights, generated builds or unrelated screenshots in the commit.
6. Checkpoint commit pushed normally to the authorized repository; remote result verified. A clean Git status must not be achieved by deleting user data or hiding unfinished tracked changes.

## Incremental organization already performed

Frozen dataset contracts/storage moved from `research/experiments.py` into `research/datasets.py`. Existing experiment-module import paths remain available. Removed four unused imports from the experiment module after reference checks; no executable legacy features or user artifacts were deleted. This localized change does not complete the final repository-wide cleanup.
