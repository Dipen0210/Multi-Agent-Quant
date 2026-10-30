# Local checkpoints and publication status

Repository: `https://github.com/Dipen0210/Multi-Agent-Quant`

Implementation branch: `codex/quantsentiment-v2`. Main has not been merged or changed by this work. Upstream commits through `ce58f9e` are preserved, including the license title correction and the legacy screenshots archived in `docs/LEGACY_README.md`.

| Checkpoint | Local commit / evidence | Publication |
|---|---|---|
| CP001 — research pipeline, report validation and durable tools | `58f6b1c`; 96 reviewed files. 64-test actual-model run, subsequent 9 report/trace tests, 6 isolated baseline tests, 16 API acceptance checks, frontend lint/build. | **Published** in `codex/quantsentiment-v2` at `98c9a2a`. |
| CP002 — data response boundaries and source health | `efe2cec`; changes described in `docs/audits/API_CONTRACT_AUDIT.md`; 68-test actual-model run and 16 acceptance checks passed, plus frontend checks. | **Published** in `codex/quantsentiment-v2` at `98c9a2a`. |
| CP003 — frozen dataset integrity | `90d488e`; dataset contracts and membership checks; 73-test real-model suite and all 16 acceptance checks passed. Commit subject identifies this checkpoint in Git history. | **Published** in `codex/quantsentiment-v2` at `98c9a2a`. |
| CP004 — evaluation result integrity | Frozen case/gate reconciliation, persisted result checks and evaluation code versioning. 79-test actual-model suite, all 16 acceptance checks and separate FinBERT diagnostic passed. | **Published** in `codex/quantsentiment-v2` at `98c9a2a`. |
| CP005 — experiment result integrity and shared study contracts | Typed historical results, source-backed replay validation, per-execution identity and shared study lifecycle. 85-test actual-model suite, 6 focused contract tests, 3 focused replay tests and all 16 acceptance checks passed. Application hash `a66ced3dd0e31d98ed393fe1b49faa6f1ea7f4e6f1d05a5dd7cb341eeba6daa3`. Typed `/api` coverage 29/29. | **Published**; branch head `98c9a2a`. |

## Publication approval state

**Resolved 2026-10-29.** The user explicitly authorized publication of the verified checkpoints in response to a direct
question naming the push. All five local checkpoints CP001–CP005 were published together to
`https://github.com/Dipen0210/Multi-Agent-Quant` on branch `codex/quantsentiment-v2`, remote head `98c9a2a`.

The push was a normal fast-forward creating a new remote branch. No force push occurred, `main` remains at the upstream
commit `ce58f9e`, and no pull request was opened or merged. Earlier automatic approval rejections of CP001 are retained
above as history; they no longer apply.

Pre-publication audit of the 107 published files: no `.env`, PEM key, notebook, screenshot, runtime database, model
weight or build artifact was included. `ModelSelection.ipynb`, `tradingStrategy.ipynb` and the user screenshot remain
untracked local artifacts, and `.gitignore` covers keys, runtime data and the notebook holding an embedded provider
credential. The published diff was scanned for provider key, AWS, GitHub, Slack, JWT and private-key patterns; none were
found. `.env.example` contains empty placeholder values only.

Publication of source code remains distinct from deployment. Deployment and live trading are still unauthorized, and the
legacy deploy workflow still requires manual dispatch with a false-by-default input.

## Local review

Frontend: `http://127.0.0.1:3001`; API: `http://127.0.0.1:8001`. Current HTTP checks returned 200 and external execution false. The backend was refreshed for the current code and migrations; a previous preview process was gracefully stopped after its identity was checked. The dedicated database is `runtime/browser-demo.sqlite3`. Use **Load synthetic demo** in the UI. HTTP/build checks are not visual interaction verification.
