# CR-00022 S27 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S27 of work item CR-00022 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# CR-00022 S27 Browser Verification Report

## Environment
- **Base URL**: http://localhost:9919
- **E2E Stack**: docker-compose.e2e.yml with project name `iw-ai-core-e2e-cr00022`
- **Project**: iw-ai-core

## Issues Encountered and Fixes Applied

### 1. `oss_accepted.py` datetime coercion bug
**Problem**: When `.iw/oss-accepted.yaml` contains a datetime object (yaml parser deserializes ISO strings to datetime), `AcceptedFile.model_validate()` fails because `accepted_at: str` expects a string but receives a `datetime`.

**Fix applied**: Modified `load_accepted()` in `dashboard/services/oss_accepted.py` to coerce datetime values to ISO strings before Pydantic validation.

### 2. E2E fixture syntax error
**Problem**: The fixture used `OssFindingStatus.pass` but the enum member is `OssFindingStatus.pass_status`.

**Fix applied**: Changed `pass` to `pass_status` in the fixture file.

### 3. Modal missing Apply/Preview buttons
**Problem**: For OSS-CH-01 (auto_apply_safe=True), the finding modal footer only shows "Re-run check", "Mark accepted", "Close" buttons. The required "Apply" and "Preview" buttons are missing.

## V1..V8 Verification Status

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Table layout + filters | PARTIAL | Table renders correctly with all groups, columns, filter chips. Screenshot captured. |
| V2 | Modal renders rich per-test copy | FAIL | Modal renders but missing Apply/Preview buttons (AC3/AC4 incomplete) |
| V3 | Apply writes to working tree only | SKIP | Blocked by V2 failure |
| V4 | Mark accepted writes .iw/oss-accepted.yaml | SKIP | Blocked by V2 failure |
| V5 | Apply all safe preview | SKIP | Blocked by V2 failure |
| V6 | SSE row updates | SKIP | Cannot test without working Apply |
| V7 | Removed CLI subcommands + routes | SKIP | Blocked by V2 failure |
| V8 | No regressions | PASS | Adjacent pages render fine |

## Screenshots Captured
- `ai-dev/active/CR-00022/evidences/post/CR-00022_v1_table_layout.png`
- `ai-dev/active/CR-00022/evidences/post/CR-00022_v2_modal_open.png`

## Root Cause Analysis

The finding modal implementation is missing the conditional rendering of Apply and Preview buttons for `auto_apply_safe=True` findings. The template/JS should show these buttons when the finding's `auto_apply_safe` flag is true, but they're absent in the current implementation.

## Files Changed
1. `dashboard/services/oss_accepted.py` - Added datetime coercion in `load_accepted()`
2. `ai-dev/active/CR-00022/e2e_fixtures/001_oss_scan_with_findings.py` - Fixed enum member name

## Console Errors Observed
- Initial 500 error on OSS page (datetime validation) - FIXED
- No new console errors after fix

## Next Steps
The CR-00022 implementation needs:
1. Fix the finding modal to show Apply and Preview buttons when `auto_apply_safe=True`
2. Verify the fix works end-to-end
3. Re-run S27 verification

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/CR-00022/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00022/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
