# CR-00022 S27 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S27 of work item CR-00022 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# CR-00022 S27 Browser Verification Report

**Step**: S27
**Agent**: qv-browser
**Work Item**: CR-00022
**Base URL Used**: http://localhost:9919

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Table layout + filters | FAIL | - | Page returns HTTP 500 |
| V2 | Modal renders rich per-test copy | FAIL | - | Cannot test - page 500 |
| V3 | Apply writes to working tree only — no branch change + idempotent | FAIL | - | Cannot test - page 500 |
| V4 | Mark accepted writes .iw/oss-accepted.yaml | FAIL | - | Cannot test - page 500 |
| V5 | Apply all safe — deselectable preview, never operates on unsafe | FAIL | - | Cannot test - page 500 |
| V6 | SSE row updates — no full-page reload | FAIL | - | Cannot test - page 500 |
| V7 | Removed CLI subcommands + routes return errors | FAIL | - | Cannot test - page 500 |
| V8 | No regressions on adjacent pages | FAIL | - | Cannot test - page 500 |

## Root Cause

**CODE DEFECT** in `dashboard/routers/oss.py:115` and `dashboard/templates/pages/project/oss.html:281`.

The `oss_page` function passes `catalog` (a `dict[str, CheckCopy]`) directly to the template. The `CheckCopy` class is a Pydantic model. The template then calls `catalog | tojson` which fails because Pydantic models are not JSON serializable by default.

### Error from dashboard container logs:
```
TypeError: Object of type CheckCopy is not JSON serializable
  File "/app/dashboard/templates/pages/project/oss.html", line 281, in block 'scripts'
    window.OSS_CATALOG = {{ catalog | tojson }};
```

### Fix Required
In `dashboard/routers/oss.py` around line 115, change:
```python
catalog = load_catalog()
```
to:
```python
catalog = {k: v.model_dump() for k, v in load_catalog().items()}
```

Or alternatively, modify `load_catalog()` to return dicts instead of Pydantic models.

## Screenshots Captured

No screenshots were captured because the page failed to render.

## Console Errors Observed

1. `Failed to load resource: the server responded with a status of 500 (Internal Server Error)`
2. `Failed to load resource: the server responded with a status of 404 (Not Found)` (favicon.ico - not relevant)

## No Regressions Observed

Not applicable — unable to verify any pages due to the 500 error on the primary test target.

## Notes

- The E2E fixture `001_oss_scan_with_findings.py` was successfully seeded to the E2E database (port 5451) after correcting the connection.
- The OSS findings data is present in the database.
- The failure is in the rendering of the page, not in the data.


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


**ESCALATION**: This is the FINAL browser fix cycle (3/3). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
