# I-00055 S11 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S11 of work item I-00055 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00055/ai-dev/active/I-00055/I-00055_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00055 S11 Browser Verification Report

## Environment
- Base URL used: http://localhost:9954
- E2E user: dev@example.local

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | one diagram (light) | fail | evidences/post/I-00055_v1_initial_page.png | Page renders zero mermaid containers — architecture-map and diagram-architecture docs are absent from DB. div.mermaid=0, pre[data-lang="mermaid"]=0. Need fixture data. |
| V2 | one diagram + readable (dark) | n/a | — | Skipped — V1 failed (no data). |
| V3 | prose has no inline mermaid | n/a | — | Skipped — V1 failed (no data). |
| V4 | no regressions | fail | — | Component cards render (count=3) but no architecture section with diagram. |

## Console / Network Errors
None observed.

## No Regressions
Components section renders with 3 cards (orch-daemon, dashboard, orch-rag) — this partial check passed. However the architecture panel lacks diagram content.

## Screenshots captured
- ai-dev/active/I-00055/evidences/post/I-00055_v1_initial_page.png

## Root Cause (on failure only)
ENV_DATA_MISSING: The E2E stack's PostgreSQL is seeded by `scripts/e2e_seed.py` which auto-discovers `e2e_fixtures/*.py` files. The fixture `ai-dev/active/I-00055/e2e_fixtures/001_seed_arch_docs.py` was just created by this agent — it was not present when the stack was brought up. The database lacks the `architecture-map` ProjectDoc (with legacy trailing mermaid block), the `diagram-architecture` ProjectDoc, and the completed `CodeIndexJob` needed for the Code page to show the architecture diagram. The browser verification page rendered a clean Code page with components but zero mermaid containers.

**Fixture created:** `ai-dev/active/I-00055/e2e_fixtures/001_seed_arch_docs.py`

**Next step:** Orchestrator must re-provision the E2E stack so the daemon picks up the new fixture and seeds the DB with the required rows. Then re-run S11.


## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: E2E DB lacks architecture-map and diagram-architecture docs (and completed CodeIndexJob). Fixture file created at ai-dev/active/I-00055/e2e_fixtures/001_seed_arch_docs.py; orchestrator must re-provision E2E stack so daemon seeds it.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/I-00055/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00055/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00055/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
