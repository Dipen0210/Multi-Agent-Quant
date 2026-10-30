# Local checkpoints and publication status

Repository: `https://github.com/Dipen0210/Multi-Agent-Quant`

Implementation branch: `codex/quantsentiment-v2`. Main has not been merged or changed by this work. Upstream commits through `ce58f9e` are preserved, including the license title correction and the legacy screenshots archived in `docs/LEGACY_README.md`.

| Checkpoint | Local commit / evidence | Publication |
|---|---|---|
| CP001 — research pipeline, report validation and durable tools | `58f6b1c`; 96 reviewed files. 64-test actual-model run, subsequent 9 report/trace tests, 6 isolated baseline tests, 16 API acceptance checks, frontend lint/build. | **Not pushed.** Automatic approval review rejected the push twice. |
| CP002 — data response boundaries and source health | `efe2cec`; changes described in `docs/audits/API_CONTRACT_AUDIT.md`; 68-test actual-model run and 16 acceptance checks passed, plus frontend checks. | Local only while publication approval is unresolved. |
| CP003 — frozen dataset integrity | `90d488e`; dataset contracts and membership checks; 73-test real-model suite and all 16 acceptance checks passed. Commit subject identifies this checkpoint in Git history. | Local only pending publication approval. |
| CP004 — evaluation result integrity | Frozen case/gate reconciliation, persisted result checks and evaluation code versioning. 79-test actual-model suite, all 16 acceptance checks and separate FinBERT diagnostic passed. | Local only pending publication approval. |
| CP005 — experiment result integrity and shared study contracts | Typed historical results, source-backed replay validation, per-execution identity and shared study lifecycle. 85-test actual-model suite, 6 focused contract tests, 3 focused replay tests and all 16 acceptance checks passed. Application hash `a66ced3dd0e31d98ed393fe1b49faa6f1ea7f4e6f1d05a5dd7cb341eeba6daa3`. Typed `/api` coverage 29/29. | Pending push at this checkpoint. |

## Publication approval state

The user requested commits/pushes at major checkpoints and supplied the repository URL. The approval system nevertheless rejected publication of CP001, requiring explicit authorization for the code payload. Read-only GitHub checks confirmed authenticated login `Dipen0210`, repository owner `Dipen0210/Multi-Agent-Quant`, ADMIN access and public visibility. A second push attempt was still rejected for lack of explicit payload-publication authorization.

The assistant asked whether to approve CP001 and subsequent verified V2 checkpoints. The user answered **“can i see in local host”**. That authorizes local review, not publication. Do not infer approval or retry pushing through another tool. Await an explicit publishing approval before retrying; do not treat generic goal-continuation messages as satisfying the rejection.

No notebooks, screenshots, keys, runtime databases, model weights or generated build artifacts were added to CP001. Public code publication is distinct from deployment, which remains unauthorized and disabled by default.

## Local review

Frontend: `http://127.0.0.1:3001`; API: `http://127.0.0.1:8001`. Current HTTP checks returned 200 and external execution false. The backend was refreshed for the current code and migrations; a previous preview process was gracefully stopped after its identity was checked. The dedicated database is `runtime/browser-demo.sqlite3`. Use **Load synthetic demo** in the UI. HTTP/build checks are not visual interaction verification.
