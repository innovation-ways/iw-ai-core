# I-00040 S13 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S13 of work item I-00040 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# I-00040 S13 BrowserVerification Report

## Step: S13
## Agent: qv-browser
## Overall Status: FAIL

## Base URL Used
`http://localhost:9926`

## Summary

The verification could not be completed due to critical environment and alembic migration issues.

## Verifications

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Banner absent at head | FAIL | Could not verify - DB downgrade mechanism unreliable |
| V2 | Banner present after downgrade | FAIL | Downgrade mechanism unreliable - alembic connects to wrong DB |
| V3 | Write buttons disabled | FAIL | Cannot proceed without V2 |
| V4 | Mutating endpoint returns 503 | FAIL | Cannot proceed without V2 |
| V5 | Restoring DB clears banner | FAIL | DB restoration mechanism unreliable |
| V6 | No regressions | FAIL | Banner check mechanism broken |

## Issues Found

### 1. Alembic connects to wrong database (CRITICAL)

**Description**: When running `uv run alembic ...` commands, alembic connects to `localhost:5433` (live orch DB) instead of the per-worktree DB at `127.0.0.1:5458`.

**Root Cause**: The `.env` file in the worktree has `IW_CORE_DB_*` variables pointing to the per-worktree DB, but shell environment variables (`IW_CORE_DB_HOST=localhost`, `IW_CORE_DB_PORT=5433`) take precedence over `.env` file because `load_dotenv()` does not override existing environment variables.

**Evidence**:
```
# .env file has:
IW_CORE_DB_HOST=127.0.0.1
IW_CORE_DB_PORT=5458
IW_CORE_DB_NAME=iw_e2e

# But shell has:
IW_CORE_DB_HOST=localhost
IW_CORE_DB_PORT=5433
```

**Alembic output shows**:
```
Current revision(s) for postgresql+psycopg://iw_orch:***@localhost:5433/iw_orch:
```

### 2. Alembic downgrade fails with RangeNotAncestorError

**Description**: When attempting to call `check_db_at_head()` for the per-worktree DB, a `RangeNotAncestorError` is raised inside `list_pending_revisions()`.

**Root Cause**: The `walk_revisions("head", "550aecbbd42b")` call fails because of what appears to be a migration graph issue or alembic bug.

**Error**:
```
alembic.util.exc.CommandError: Requested range head:550aecbbd42b does not refer to ancestor/descendant revisions along the same branch
```

**Impact**: The middleware's `contextlib.suppress(Exception)` silently catches this error, leaving `_alembic_guard_status` at its initial value (which was `ok=True` at startup when the DB was at head). This causes the banner check to always fail.

### 3. Alembic stamp/downgrade doesn't persist correctly

**Description**: When running `alembic downgrade -1` or `alembic stamp`, the alembic_version table is not properly updated. The database query shows a different revision than `alembic current` reports.

**Evidence**:
- `alembic current` reported: `550aecbbd42b`
- Direct DB query showed: `c062b6bf5eb3`
- After manual `UPDATE alembic_version SET version_num = 'c062b6bf5eb3'`, the DB correctly showed head

## Screenshots Captured

- `ai-dev/active/I-00040/evidences/post/I-00040_v1_banner_absent.png` - Initial state at head (no banner visible - but this was NOT verified as the DB was in an uncertain state)

## Files Changed

None - verification could not be completed.

## Recommendations

1. **Fix the alembic migration issue**: The `RangeNotAncestorError` in `list_pending_revisions()` needs to be investigated. The migration chain appears correct (c062b6bf5eb3 -> 550aecbbd42b), but `walk_revisions` fails.

2. **Fix the environment variable precedence**: Ensure that when running browser verification steps, the `IW_CORE_DB_*` variables correctly point to the per-worktree DB for alembic commands.

3. **Add explicit DB verification**: Before running V2, explicitly verify that the alembic downgrade actually persisted by querying the DB directly.

4. **Consider adding a debug endpoint**: Expose `request.state.alembic_guard_status` via a debug endpoint to verify the middleware's state without needing to inspect the page.

## Console Errors Observed

No console errors in the browser, but significant issues with alembic command reliability.

## Notes

The core alembic-version guard feature appears to be implemented correctly in the code (middleware, templates, `require_db_at_head` dependency). However, the alembic migration mechanism has issues that prevent proper verification:
- The `check_db_at_head()` function throws a `RangeNotAncestorError` when calling `list_pending_revisions()`
- The alembic CLI connects to the wrong database due to environment variable precedence
- Alembic stamp/downgrade operations don't properly persist to the alembic_version table

These issues are environment/setup related rather than code defects in the guard implementation itself.


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/I-00040/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00040/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
