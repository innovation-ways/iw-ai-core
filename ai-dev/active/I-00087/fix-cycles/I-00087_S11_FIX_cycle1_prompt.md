# I-00087 S11 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S11 of work item I-00087 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Scope (allowed_paths from workflow-manifest.json)

You MAY only modify files matching these globs:

  dashboard/static/chat_assistant/chat.js
  tests/dashboard/test_chat_panel_event_protocol.py

Edits to files outside this list will block the cycle. If the failing gate
appears to require an out-of-scope edit, do NOT make it — instead document
the required out-of-scope path(s) under "blockers" in your result contract,
and the operator will amend allowed_paths.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00087/ai-dev/active/I-00087/I-00087_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

browser env setup failed:  Container iw-ai-core-e2e-i00087-e2e-db-1 Created 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-i00087-e2e-daemon-stub-1 Creating 
 Container iw-ai-core-e2e-i00087-e2e-daemon-stub-1 Created 
 Container iw-ai-core-e2e-i00087-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Starting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Started 
 Container iw-ai-core-e2e-i00087-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-i00087-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-i00087-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-i00087-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-i00087-e2e-dashboard-1 Error dependency e2e-dashboard failed to start
dependency failed to start: container iw-ai-core-e2e-i00087-e2e-dashboard-1 is unhealthy

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00087/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00087/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
