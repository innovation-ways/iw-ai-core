# CR-00054 S18 Browser Verification Fix Cycle 2/5

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
- Auth wall: not present (dashboard loaded directly)

## Pre-flight result (OpenCode stub reachability)
- `GET /api/chat/config` returned **HTTP 200** with JSON body including `models` (non-empty) and `default_model`.
- Stub is reachable (PASS).

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | fail | code_defect | `ai-dev/active/CR-00054/evidences/post/CR-00054_v0_preflight_page_sanity.png` | Dangling DOM reference detected on `/project/iw-ai-core/research`: fragment reference `#research-state, [name='q']` had no matching `id`. |
| V1 | `/api/chat/config` returns populated models array (AC1) | pass | null | `ai-dev/active/CR-00054/evidences/post/CR-00054_v1_config_endpoint.png` | HTTP 200, `application/json`, `models[0]` has `id` + `name`, `default_model` matched one `models[*].id`. |
| V2 | Ctrl+/ opens chat panel without console errors (AC2) | pass | null | `ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_open.png` | Panel became visible and composer input rendered; no console errors recorded during toggle. |
| V3 | Prompt → stream → permission.asked → approval modal (AC2) | fail | code_defect | `ai-dev/active/CR-00054/evidences/post/CR-00054_v3_permission_modal.png`, `ai-dev/active/CR-00054/evidences/post/CR-00054_v3_after_allow.png` | Permission modal appeared and Allow worked, but expected visible streaming/message-updated/session-idle indicators were not rendered in the chat transcript after approval. |
| V4 | Deny path (AC2 secondary) | fail | code_defect | `ai-dev/active/CR-00054/evidences/post/CR-00054_v4_deny.png` | Deny closed modal, but expected aborted-run / `permission_denied: true` idle indicator was not visibly rendered in the panel. |
| V5 | Healthcheck integrity (AC3) | pass | null |  | `docker inspect iw-ai-core-e2e-cr00054-e2e-dashboard-1 --format '{{.State.Health.Status}}'` returned `healthy`. |
| V_no_regressions | Adjacent flows unchanged (AC3) | fail | code_defect | `ai-dev/active/CR-00054/evidences/post/CR-00054_vN_no_regressions.png` | Route navigations succeeded (Projects/Queue/History/Batches/Tests/Quality/Jobs/Worktrees/Docs/Research). On Code page, load-time console error occurred: `TypeError: window.iwChat.setContext is not a function` at `/project/iw-ai-core/code:1136`. Right-side Code chat (`Cmd+\`) still toggled; dark-mode toggle still worked. |

## Console / Network Errors
- On `/project/iw-ai-core/code` load:
  - `TypeError: window.iwChat.setContext is not a function`
  - `at http://localhost:9955/project/iw-ai-core/code:1136:17`

## No Regressions
- Checked: Projects, Queue, History, Batches, Tests, Quality, Jobs, Worktrees, Docs, Research pages — navigated and rendered.
- Code page right-side chat panel still toggles independently (`Expand chat panel (Cmd+\)` → `Collapse chat panel (Cmd+\)`).
- Dark-mode toggle still responds.
- **Regression found:** Code page now throws load-time JS error above.

## Screenshots captured
- ai-dev/active/CR-00054/evidences/post/CR-00054_v0_preflight_page_sanity.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v1_config_endpoint.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v2_panel_open.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_permission_modal.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v3_after_allow.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_v4_deny.png
- ai-dev/active/CR-00054/evidences/post/CR-00054_vN_no_regressions.png

## Root cause (failure)
The OpenCode stub endpoint itself is healthy (`/api/chat/config`), but the chat UI event/render path appears inconsistent with expected stub event handling after permission decisions: approval/deny flows do not surface the expected post-decision message/idle indicators in the transcript. Separately, the Code page emits a deterministic load-time JS failure (`window.iwChat.setContext is not a function` at `code:1136`), indicating a frontend integration mismatch (likely method contract drift between page script and `iwChat` object) and causing regression failure.


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
