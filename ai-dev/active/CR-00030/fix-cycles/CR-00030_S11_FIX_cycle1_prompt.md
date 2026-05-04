# CR-00030 S11 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S11 of work item CR-00030 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00030/ai-dev/active/CR-00030/CR-00030_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00030 S11 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9951`
- E2E user: `dev@example.local`
- Dashboard container: `iw-ai-core-e2e-cr00030-e2e-dashboard-1`
- Container HOME: `/app` (not writable from host)
- Host HOME: `/home/sergiog`

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Claude 5h label in 'Xh Ym' form | **FAIL** | — | ENV_DATA_MISSING: container HOME `/app` is not reachable from host. Rate-limits cache must live at `~/.claude/rate-limits-cache.json` inside the container at `/app/.claude/`, but only `ai-dev/` is bind-mounted from host. Cannot inject the seed file. |
| V2 | Claude 7d label unchanged | **FAIL** | — | ENV_DATA_MISSING: same root cause as V1 — cannot inject cache file into container HOME. |
| V3 | Sub-hour 5h label minutes-only | **FAIL** | — | ENV_DATA_MISSING: same root cause. |
| V4 | Missing cache → '5h' placeholder | **PASS** | `evidences/post/CR-00030_v4_5h_placeholder.png` | Footer correctly shows static `'5h'` placeholder when cache is absent. Confirms template fallback works. |
| V5 | No regressions (console, MiniMax, adjacent pages) | **PASS** | `evidences/post/CR-00030_v5_no_regressions.png` | No console errors. MiniMax row shows `'5h'` (correct — no API key in container). Footer present on all visited pages (`/`, `/system/status`, `/project/iw-ai-core/`). |

## Console / Network Errors

None observed during V5 navigation.

## Root Cause (V1–V3)

```
Dashboard process runs inside Docker container iw-ai-core-e2e-cr00030-e2e-dashboard-1
with HOME=/app. Cache path is resolved via Path.home() → /app/.claude/rate-limits-cache.json.

The E2E compose stack only bind-mounts:
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00030/ai-dev → /app/ai-dev (read-only)

There is no mechanism to inject a file into /app/.claude/ from the host.
The orchestrator's worktree-seed.sh also cannot write there (seed runs in the container's /app context).

This means V1 (4h 32m remaining), V2 (7d wall-clock), and V3 (25m remaining)
cannot be executed in the current E2E stack design without modifying the
worktree-compose configuration to include a writable bind mount for the cache directory.
```

This is classified as **ENV_DATA_MISSING** — the fix-cycle agent cannot fix this by editing code.

## Screenshots Captured

- `ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png` — V4: static "5h" fallback confirmed
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png` — V5: project page, no console errors

## No Regressions Observed

- MiniMax row in footer displays `'5h'` on all three pages (`/`, `/system/status`, `/project/iw-ai-core/`). This is correct behavior — no MiniMax API key is configured in the container, so the fallback is expected.
- No `TypeError`, no `TemplateSyntaxError`, no 500 responses on `/api/usage/llm/fragment`.
- All three pages loaded successfully with correct navigation structure.

## Fix-Cycle Recommendation

To enable V1–V3 in future runs, the `ai-dev/iw-config/worktree-compose.template.yml` would need to add a writable bind mount for `~/.claude/` from host to container, or the seed script would need to create the cache file inside the container's HOME at startup time. Without such a change, the cache file cannot be injected into the isolated container environment.

## The previous agent claimed this was environmental

The previous run's `--reason` was:

> ENV_DATA_MISSING: V1/V2/V3 cannot run — container HOME /app/.claude/ is not writable from host. E2E stack only bind-mounts ai-dev/ read-only. V4 (static fallback) and V5 (no regressions) pass. Cache injection would require a worktree-compose change that is outside code scope.

Six of the last six genuine blockers on browser_verification steps were **code defects misdiagnosed as environmental** (wrong-DB insert via `SessionLocal`, `/api/embed` shape drift, `/api/show` missing, `_run_qa_in_thread` swallowing exceptions, Jobs-page `None`-datetime sort, `sse-client.js` defer ordering). Start by *assuming the previous classification is wrong*:

1. Re-read the verification log for HTTP 5xx, pydantic    `ValidationError`, unhandled exceptions in stderr, or    `event: done` with zero tokens — all are code defects.
2. Check that the agent used `$IW_BROWSER_E2E_DB_URL` (not    `orch.db.session.SessionLocal`) for any E2E DB writes.    If SessionLocal appears in the failure log, it wrote to    the live orchestration DB and the dashboard under test    never saw the row — fix the prompt / test methodology.
3. If the failure is genuinely environmental (missing seed    rows, missing daemon-driven state transitions), write    `ai-dev/active/CR-00030/e2e_fixtures/NNN_<name>.py`    exporting `def seed(db: Session) -> None`. The    E2E stack loads these at bring-up. Do NOT add ad-hoc    inserts from the agent subprocess.
4. If the test harness itself is wrong (e.g. a V step that    can't be satisfied in playwright-cli's session model, a    stub that doesn't speak the client's contract), fix the    harness. Prompts under `ai-dev/active/{item_id}/prompts/`    and fixtures under `scripts/` are in-scope.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00030/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00030/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
