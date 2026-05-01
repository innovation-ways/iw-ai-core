# I-00054 S11 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S11 of work item I-00054 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00054 S11 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9940` (from `$IW_BROWSER_BASE_URL`)
- E2E user: `dev@example.local`
- Coverage data: present (last run: 2026-05-01T06:24:01)

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Expand — label changes to "click to collapse" | **FAIL** | `evidences/post/I-00054_v1_expand_label.png` | After clicking `dashboard` row, label cell still reads "click to expand" — the fix was not applied |
| V2 | Collapse — label returns to "click to expand" | **FAIL** | `evidences/post/I-00054_v2_collapse_label.png` | After second click, row did not collapse; label still "click to expand" |
| V3 | Re-expand — toggle works a second time | **FAIL** | `evidences/post/I-00054_v3_re_expand.png` | Third click re-fetches; label never changes to "click to collapse" |
| V4 | No regressions — other rows independent | **FAIL** | `evidences/post/I-00054_v4_no_regressions.png` | While dashboard was expanded, executor row still showed "click to expand" — but dashboard's own label was also wrong |
| V5 | No console errors | **PASS** | `evidences/post/I-00054_v5_no_console_errors.png` | Navigated to `/system/status` without errors |

## Console / Network Errors
None observed. The htmx request to `/system/coverage/files/dashboard` succeeded (HTTP 200) and returned file-level rows. The issue is purely a UI state tracking problem — no network failures.

## No Regressions
V5 confirms adjacent pages (System Status) load cleanly. No JS errors were thrown during any of the V1–V4 interactions. The fix's absence does not break navigation or cause crashes — it only prevents the label from updating and prevents collapse.

## Screenshots captured
- `evidences/post/I-00054_v1_expand_label.png` — after first click (V1): dashboard row expanded, file rows visible, but label still "click to expand"
- `evidences/post/I-00054_v2_collapse_label.png` — after second click (V2): row still expanded, label unchanged
- `evidences/post/I-00054_v3_re_expand.png` — after third click (V3): row re-expanded, label unchanged
- `evidences/post/I-00054_v4_no_regressions.png` — after clicking executor row (V4): dashboard still expanded (label wrong), executor just expanded (label also wrong)
- `evidences/post/I-00054_v5_no_console_errors.png` — navigated to System Status page (V5)

## Root Cause

**File**: `dashboard/templates/pages/system/coverage.html`
**Lines**: 73–79, 92

The fix described in the design document (I-00054_Issue_Design.md §"Detailed Fix Specification for S01") was **not applied** to this worktree.

Current state of the template:
- Line 73–79: `<tr>` row has no `data-pkg-toggle`, no `data-expanded` attributes, and no guard in `hx-trigger` — `hx-trigger="click, keydown[key=='Enter']"` fires unconditionally on every click
- Line 92: `<td>` label is static text `"click to expand"` with no `id` attribute — JavaScript has no anchor to update the label

Without the JavaScript block (the `htmx:afterSwap` listener and collapse handler), and without the data attributes that gate the htmx trigger, the toggle is non-functional:
1. Every click fires the `hx-get` request regardless of expanded state
2. The label text is never updated after content is injected
3. There is no collapse path — the row stays permanently expanded after the first click

The design document specifies exact changes including `data-pkg-toggle`, `data-expanded="false"`, `id="expand-label-{{ pkg.name }}"`, and a `<script>` block. None of these are present in the current template.

## Conclusion

All 5 verifications failed (V5 is navigation-only, not a toggle check). The toggle fix was not applied to this worktree. The bug is present exactly as described in the issue design.

**This is a CODE DEFECT** — the template lacks all fix components described in the S01 implementation specification.

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00054/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00054/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
