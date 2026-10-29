# API response-contract coverage — 2026-10-29

Scope: successful V2 `/api` responses, inspected from the actual FastAPI route registry. Request validation and structured error handling are separate boundaries. **23 of 29 V2 routes have declared response models; six remain unfinished.** This count is coverage evidence, not full application acceptance.

| Domain | Routes | Response validation / status |
|---|---|---|
| Instruments | `GET /api/instruments` | `InstrumentList`: exact supported identity and metadata. |
| Imports | `POST /api/imports`, `/imports/csv/{kind}`, `/imports/recorded`, `/demo/import` | `ImportReceipt` / `DemoReceipt`: counts reconcile with IDs, bounded batch/rejections, explicit synthetic demo mode. |
| Evidence | `GET /api/evidence`, `/evidence/{document_id}` | `EvidenceList` / `DocumentResponse`: nested document/market contracts, record/content hashes, envelope identity and availability. |
| Snapshots | `POST /api/snapshots`, `GET /api/snapshots/{snapshot_id}` | `ReportSnapshot`: frozen request/manifest identity, duplicate groups and validity tier; preserves original timestamp serialization. |
| Source health | `GET /api/source-health` | `SourceHealthResponse`: typed availability/import times, counts and document/market kinds. Bounded `limit`/`offset`. Supplied timestamps are not certified live freshness. |
| Configurations | `GET/POST /api/configurations`, `POST /api/configurations/{configuration_id}/activate` | `ConfigurationList`, `ConfigurationResponse`, `ConfigurationActivation`: nested policy contracts and configuration hash; bounded listing. |
| Research runs | `POST/GET /api/runs`, `GET /api/runs/{run_id}`, `POST .../cancel`, `POST .../retry` | `RunResponse` / `RunList`: report/run linkage, status and request identity; final reports also rechecked against actual sources and market calculations. |
| Traces | `GET /api/runs/{run_id}/steps`, `.../tools` | `StepList` / `ToolList`: parent/child references, attempt identity, input hash, completion metadata and validated outputs; bounded pagination. |
| Datasets | `POST/GET /api/datasets`, `GET /api/datasets/{dataset_id}` | `DatasetResponse` / `DatasetList`: frozen identity, unique bounded references, provenance/tier, authoritative source membership/content and scope checks. Reads share a transaction; list pagination is bounded; corruption prevents experiment admission. |
| Studies | `POST /api/evaluations`, `POST /api/experiments`, `GET /api/studies`, `GET /api/studies/{study_id}`, `POST .../cancel` | **Incomplete:** request contracts exist; successful study/results responses still need declared schemas and cross-field checks. |
| Release state | `GET /api/release-status` | **Incomplete:** currently reports explicit blockers, but needs typed response and complete evidence-accounting audit. |

The non-`/api` health and disabled legacy routes also require a final boundary review. Do not add permissive `dict` wrappers solely to make the coverage count green.

## Evidence for the data-response increment

- `api/data_responses.py` validates instruments, import receipts, document/market records, source health and configurations. Route bindings live in `api/research_routes.py`.
- `tests/test_api_data.py`: 6 passed, including corrupted identity/content-hash rejection, inconsistent receipt counts, configuration hash mismatch, market-source visibility and pagination bounds. Invalid response errors omit source payloads.
- `RUN_REAL_MODEL=1 venv/bin/python -m unittest discover -s tests -v`: all 68 passed in 38.493 seconds, including real inference/replay and historical integration.
- Actual-model API acceptance: 16/16 passed; code hash `ec21a1bd5073b2d74405150f7e63dad64f15adf1a8b36962200a892f304daec8`.
- Frontend lint and isolated production build passed after displaying source kind and using distinct document/market source keys.

Remaining response work should validate study kind/request/result/status consistency, experiment/evaluation numerical contracts and release-evidence claims. Keep failed/partial states and unknown usage explicit.

## Frozen-dataset increment

`research/datasets.py` owns request/manifest/response contracts and authoritative reads. The historical harness and study admission both use the same checked reader. A digest alone cannot establish source eligibility: the reader also reconciles persisted membership, source hashes/envelopes, instrument, provenance and date scope. Data damage returns a sanitized server error; nonexistent dataset IDs remain 404. Repeat freeze detects broken links instead of repairing them implicitly.

`tests/test_dataset_contracts.py`: 5 tests passed in 0.452 s. They cover API round trips/idempotency/pagination, invalid hash/duplicates/tier, missing membership and blocked job creation, forged but internally hashed scope, and altered source content hashes. Faults occur only in isolated temporary databases. Existing historical experiment tests also passed (3 in 5.344 s). Full suite with real inference: 73 passed in 38.479 s. OpenAPI generated successfully with 23/29 typed routes.

Actual-model API acceptance after this increment: 16/16 passed; backend hash `fc9beaf756593fc194719d6ab47bdd6b45772e421920578cc9986f339c3b68ee`. Frontend was not changed in this increment.
