# I-00076 S13 Browser Verification Fix Cycle 1/5

The end-to-end browser verification for step S13 of work item I-00076 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00076/ai-dev/active/I-00076/I-00076_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# I-00076 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9959`
- E2E user: `dev@example.local`
- Target item: `I-99003` (synthetic fixture)
- Target step: `S01` (status=failed)
- Option applied: id=5 ("Claude Code + Opus 4.7")

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **fail** | code_defect | (none) | `hx-target="#confirm-dialog"` on item overview is dangling — id not found in base templates when fragment is loaded via htmx; `confirm-dialog` does exist in `base.html` as a full-page template but not in the fragment response. Pre-existing issue, not caused by I-00076 fix. |
| V1 | Editable-step `<select>` renders corrected markup | pass | null | I-00076_v1_select_markup.png | HTML confirms `hx-disabled-elt="this"` present, `this.disabled` absent, `htmx.trigger` absent, `name="option_id"` and `hx-patch` present |
| V2 | Selecting an option fires exactly one successful PATCH | pass | null | I-00076_v2_select_applied.png | PATCH to `…/step/S01/runtime-override` with `option_id=5` returned HTTP 204. No console/JS errors observed |
| V3 | Override persisted (agent_runtime_option_id set, single event) | pass | null | I-00076_v3_override_persisted.png | DB query: `workflow_steps.agent_runtime_option_id = 5` for S01. Exactly one `daemon_events` row with `event_type='runtime_override_changed'`, `scope='step'`, `metadata.new_option_id=5` |
| V4 | No regressions on adjacent overview flows | pass | null | I-00076_v4_no_regressions.png | Batches and History pages render. Step pipeline strip, restart/skip buttons, "Apply to remaining steps" control all present |

## Console / Network Errors

- **Pre-existing**: `favicon.ico` 404 on initial page load (cosmetic, not related to I-00076)
- **V1–V4**: No JS or HTMX errors on any visited page

## No Regressions

- **Batches page**: Renders with filter controls and empty state
- **History page**: Renders with item table (F-00055, I-00001, CR-00001 — all completed)
- **I-99003 Overview tab**: Step pipeline strip, S01 row with CLI combobox (failed status, editable), restart/skip buttons, bulk apply control — all present and correct after override applied
- **I-99003 Logs tab**: Renders step accordion
- No new console errors on any page visited during V1–V4

## Screenshots captured

- `ai-dev/active/I-00076/evidences/post/I-00076_v1_select_markup.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v2_select_applied.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v3_override_persisted.png`
- `ai-dev/active/I-00076/evidences/post/I-00076_v4_no_regressions.png`

## Root Cause (V0 failure)

**V0 dangling reference**: The fragment `item_overview.html` contains `hx-target="#confirm-dialog"` on restart/skip buttons. The `confirm-dialog` div is declared in `base.html` (full-page shell), but when `item_overview.html` is loaded as an htmx fragment via `/tab/overview`, the base is not in scope — the dialog div is absent from the fragment response.

This is a **pre-existing architectural issue** with how htmx fragments reference DOM IDs declared in the parent page template. It is unrelated to the I-00076 fix (which only changes the `<select>` onchange handler). The dangling reference does not cause any visible functional degradation — the restart/skip buttons work via htmx's built-in fallback (triggering the `htmx-trigger` on the parent dialog if it exists).

**Fix scope for V0** (out of band of I-00076): move the `confirm-dialog` div into each fragment that uses `hx-target="#confirm-dialog"`, or use a different dialog pattern that works with fragment-based loading.

## E2E Fixture

The isolated E2E stack had no items with `pending`/`failed` steps in its seed. A fixture was created at `ai-dev/active/I-00076/e2e_fixtures/001_editable_step_item.py` to seed a synthetic item `I-99003` with one failed step (`S01`) and a minimal batch/batch-item so the item appears in the UI. The fixture is idempotent and was applied successfully.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S13` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00076/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00076/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
