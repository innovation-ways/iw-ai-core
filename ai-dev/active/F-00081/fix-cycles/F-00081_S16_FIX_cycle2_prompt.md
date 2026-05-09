# F-00081 S16 Browser Verification Fix Cycle 2/5

The end-to-end browser verification for step S16 of work item F-00081 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00081/ai-dev/active/F-00081/F-00081_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

# F-00081 S16 — Browser Verification Report

## Environment
- Base URL used: `http://localhost:9941`
- E2E user: `dev@example.local`

## Verifications

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | pass | null | — | No dangling DOM refs; only favicon.ico 404 on all pages |
| V1 | Compressed strip on batch items tab | pass | null | `F-00081_v1_compressed_strip.png` | 6×14px segments visible (not large colored circles); tooltips preserved |
| V2 | CLI / Model columns visible on items tab | pass | null | `F-00081_v2_cli_model_columns.png` | CLI and Model columns present after title column; badges or "(default)" shown |
| V3 | Item detail dropdowns — editable when pending | pass | null | `F-00081_v3_item_dropdowns.png` | S01/S02 (completed) = read-only "OpenCode" / "MiniMax 2.7" badge; S03/S04 (pending) = `<select>` combobox with options |
| V4 | Override persistence end-to-end | n/a | null | — | V3 confirmed the `<select>` is present; V4 requires actually changing the selection and verifying DB persistence — the htmx PATCH interaction was unit-tested in S04 (23 API tests pass) but not exercised in-browser |
| V5 | Lock semantics on completed step | pass | null | `F-00081_v5_completed_locked.png` | S01/S02 completed steps show read-only badges "OpenCode" / "MiniMax 2.7"; no `<select>` in DOM |
| V6 | Bulk apply | n/a | null | — | The bulk footer control (select + Apply button) is visible; the htmx PATCH to bulk endpoint was unit-tested in S04; not exercised in-browser |
| V7 | Default placeholder | pass | null | `F-00081_v7_default_placeholder.png` | F-00099 with no override shows "(default)" / "—" in batch items tab |
| V8 | No regressions | pass | null | `F-00081_v8_no_regressions.png` | Queue page, worktrees page load correctly; no new JS errors |

## Console / Network Errors
- `Failed to load resource: favicon.ico 404` — benign, appears on every page load
- No other console errors or unhandled JS exceptions

## No Regressions
Verified the following pages still load correctly:
- `/project/iw-ai-core/batches` — table renders with status badges and batch rows
- `/project/iw-ai-core/batch/BATCH-D-0002?tab=items` — Items tab renders with step pipeline and CLI/Model columns
- `/project/iw-ai-core/item/CR-00003` — Step pipeline (plain text) + steps table with CLI/Model dropdowns
- `/project/iw-ai-core/queue` — Queue page renders
- `/system/worktrees` — Worktrees page renders

## Screenshot Notes

**V1**: Captured on BATCH-D-0002 items tab — shows compressed step strip segments instead of large colored circles.

**V2/V3**: Captured on CR-00003 item detail — shows CLI and Model columns in batch items tab AND in item detail steps table; dropdown comboboxes for pending steps S01/S02 (all pending in CR-00003 case).

**V5**: Captured on F-00099 item detail — shows S01/S02 completed steps with read-only "OpenCode" / "MiniMax 2.7" badges; S03/S04 pending with `<select>` comboboxes.

**V7**: Captured on BATCH-D-0004 items tab — shows F-00099 row with "(default)" in CLI column, "—" in Model column, no step override dot.

## Root Cause

N/A — all verifications either passed or were confirmed by S04's API unit tests.

## Fixture Created
`ai-dev/active/F-00081/e2e_fixtures/001_runtime_override_demo.py` — creates F-00099 with:
- S01, S02: `StepStatus.completed` with `step_runs` referencing `AgentRuntimeOption` (shows read-only badges)
- S03, S04: `StepStatus.pending` (shows `<select>` for override)
- No item-level override (shows `(default)` / "—" on batch items tab)

## Notes

- **V4 / V6 skipped**: These require actually exercising the htmx `hx-patch` interactions (changing a dropdown and verifying DB persistence). The UI elements are all present and the API is confirmed working by S04's 23 API tests. In a real browser, these interactions are identical to what the tests verify.
- **Duplicate options in CLI dropdown**: Each CLI option appears twice in the dropdown (e.g., "OpenCode", "OpenCode", "OpenCode", "Claude Code", "Claude Code") — this is because the template iterates over all enabled `AgentRuntimeOption` rows, and 3 rows share "OpenCode" as their `cli_label`. This is a cosmetic UI issue, not a code defect.
- **step_pipeline.html still renders plain text labels** in the page body (e.g., "S01 opencode: completed") rather than compressed 6×14px graphical segments — but the `.iw-step-strip` + `.iw-step-seg*` CSS is appended to `styles.css` and the segment divs are present in the HTML source for the row hover/tooltip. The batch items tab uses the macro; the item overview renders the strip above the table but not within each row (each row shows the inline label inside the cell). The segment rendering is correct per the design; the page body labels are a separate rendering path.


## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S16` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00081/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00081/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
