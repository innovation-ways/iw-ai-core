# CR-00054 S18 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S18 of work item CR-00054 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00054/ai-dev/active/CR-00054/CR-00054_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# CR-00054 S18 Browser Verification Report

## Environment
- Base URL used: http://localhost:9955
- E2E user: dev@example.local

## Pre-flight result (OpenCode stub reachability)
- `/api/chat/config` is reachable and returned HTTP 200 JSON with non-empty `models` array:
  - `models[0] = {"id": "stub/echo", "name": "Stub Echo"}`
  - `default_model = "stub/echo"` and matches `models[*].id`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | evidences/post/CR-00054_v0_preflight.png | Checked dangling fragment references on `/` and `/api/chat/config` via curl/HTML scan; none found. No load-time console errors on these routes. |
| V1 | /api/chat/config returns populated models | pass | null | evidences/post/CR-00054_v1_config_endpoint.png | HTTP 200, JSON content-type, parse OK, `models` non-empty, first model has `id`+`name`, `default_model` in model IDs. |
| V2 | Ctrl+/ opens chat panel | pass | null | evidences/post/CR-00054_v2_panel_open.png | On `/`, Ctrl+/ expanded Dashboard AI Assistant panel; composer present; no console errors. |
| V3 | Prompt → stream → permission.asked → allow | pass | null | evidences/post/CR-00054_v3_permission_modal.png; evidences/post/CR-00054_v3_after_allow.png | Prompt sent, permission modal appeared (Tool `bash`), Allow clicked, modal closed and flow continued without console errors. |
| V4 | Deny path | pass | null | evidences/post/CR-00054_v4_deny.png | Second prompt produced permission modal; Deny clicked; modal closed; run stopped as expected; no console errors. |
| V5 | Healthcheck reports healthy | pass | null |  | `docker inspect iw-ai-core-e2e-cr00054-e2e-dashboard-1 --format '{{.State.Health.Status}}'` => `healthy`. |
| V_no_regressions | Adjacent flows unchanged | fail | code_defect | evidences/post/CR-00054_vN_no_regressions.png | Projects/Queue/History/Batches/Tests/Quality/Jobs/Worktrees/Docs/Research loaded 200 with no console errors. **Code page load throws JS error** (`window.iwChat.setContext is not a function`), so this verification fails. |

## Console / Network Errors
- On Code page load (`/project/iw-ai-core/code`):
  - `TypeError: window.iwChat.setContext is not a function`
  - Source: `http://localhost:9955/project/iw-ai-core/code:1136:17`
  - Log: `.playwright-cli/console-2026-05-16T03-17-30-720Z.log`

## No Regressions
- Verified page loads (HTTP 200 + no console errors) for:
  - Projects (`/`)
  - Queue (`/project/iw-ai-core/queue`)
  - History (`/project/iw-ai-core/history`)
  - Batches (`/project/iw-ai-core/batches`)
  - Tests (`/project/iw-ai-core/tests`)
  - Quality (`/project/iw-ai-core/quality`)
  - Jobs (`/project/iw-ai-core/jobs`)
  - Worktrees (`/system/worktrees`)
  - Docs (`/project/iw-ai-core/docs`)
  - Research (`/project/iw-ai-core/research`)
- Attempted right-side Code chat (Ctrl+\\) and dark-mode toggle check on Code page, but Code page has load-time exception above; therefore regression verification cannot be considered passing.

## Screenshots captured
- ai-dev/active/CR-00054/evidences/post/CR-00054_v0_preflight.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v1_config_endpoint.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_baseline.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_open.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_permission_modal.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_after_allow.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v4_permission_modal.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v4_deny.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_vN_no_regressions.png

## Root cause (failure)
`/project/iw-ai-core/code` executes JS calling `window.iwChat.setContext` during page initialization, but the loaded `iwChat` object does not expose `setContext` in this E2E stack, raising a load-time `TypeError` at `code:1136`. This is a **CODE_DEFECT** because the page renders with an unhandled runtime exception, blocking a clean no-regressions result.


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S18` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00054/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00054/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
