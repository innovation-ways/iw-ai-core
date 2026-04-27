# I-00040 S13 Browser Verification - QvBrowser Report

## Step: S13
## Agent: qv-browser
## Work Item: I-00040
## Overall Status: FAIL

## What Was Done

Performed browser verification for the alembic version guard feature (I-00040). The verification tested whether:
1. The dashboard shows a banner when the DB is behind head
2. Write-action buttons are disabled when the DB is behind head
3. Mutating endpoints return HTTP 503 when the DB is behind head
4. The banner disappears when the DB is restored to head

## Verification Results

| V1 | Banner absent at head | PASS |
| V2 | Banner present after downgrade | FAIL |
| V3 | Write buttons disabled | SKIP |
| V4 | Mutating endpoint returns 503 | SKIP |
| V5 | Restoring DB clears banner | SKIP |
| V6 | No regressions | PASS |

## Bug Found

**CODE DEFECT** in `orch/db/safe_migrate.py:444`:
- `list_pending_revisions` uses wrong argument order for `walk_revisions`
- Should be `walk_revisions(current_rev, "head")` not `walk_revisions("head", current_rev)`

**CODE DEFECT** in `orch/db/alembic_guard.py:88-94`:
- `check_db_at_head` catches `RangeNotAncestorError` but not `CommandError`
- `list_pending_revisions` raises `CommandError` when the DB is behind head
- This causes `check_db_at_head` to raise an exception instead of returning `GuardStatus(ok=False)`

## Impact

Due to these bugs, when the DB is behind head:
1. `check_db_at_head()` raises an unhandled exception
2. The middleware's exception suppression keeps `_alembic_guard_status` as `None`
3. `is_db_stale(request)` returns `False` because status is `None`
4. The banner does not appear

## Screenshots Captured

No screenshots were captured for V2-V5 as the banner did not appear.

## Files Changed

No files were changed during this verification. The bugs are in the existing code.

## Test Results

No automated tests were run as part of this verification.

## Issues Found

1. **Bug in `orch/db/safe_migrate.py`**: `list_pending_revisions` uses incorrect argument order for `walk_revisions`
2. **Bug in `orch/db/alembic_guard.py`**: Missing `CommandError` exception handler

## Observations

- The E2E stack was accessible at `http://localhost:9926` during verification
- The E2E DB was accessible at `127.0.0.1:5458` during verification
- The dashboard rendered correctly and showed no console errors related to the alembic guard
- The console errors observed (`/system/nav/worktree-badge` 500) are unrelated to this issue

## Recommendation

Fix the two bugs identified above and re-run the browser verification.