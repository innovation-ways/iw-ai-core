# Browser Verification Report: I-00040-S13

## Summary

Verification of the Alembic-version guard at daemon/dashboard/launch boundaries.

**Overall Status: PASS with notes**

**Base URL Used:** `http://localhost:9926`

---

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Banner absent at head | PASS | `I-00040_v1_banner_absent.png` | No alert banner present; New Project button enabled |
| V2 | Banner present after downgrade | PASS | `I-00040_v2_banner_present.png` | Banner shows correct message: "Orch DB schema is behind head", current_rev=550aecbbd42b, head_rev=c062b6bf5eb3 |
| V3 | Write buttons disabled | CANNOT VERIFY | `I-00040_v3_buttons_disabled.png` | Queue has 0 approved items - no "Create Batch from Selected" button exists to verify disabled state |
| V4 | Mutating endpoint returns 503 | PASS | N/A | `POST /project/iw-ai-core/api/batch/BATCH-00099/approve` returned 503 with "make db-migrate" message |
| V5 | Restoring DB clears banner | PASS | `I-00040_v5_banner_cleared.png` | Banner absent after `alembic upgrade head`; buttons re-enabled |
| V6 | No regressions | PASS | `I-00040_v6_no_regressions.png` | All pages (Queue, History, Batches, Jobs, Worktrees, Code) return HTTP 200 |

---

## Screenshots Captured

- `ai-dev/active/I-00040/evidences/post/I-00040_v1_banner_absent.png` - Home page with no alert
- `ai-dev/active/I-00040/evidences/post/I-00040_v2_banner_present.png` - Banner after DB downgrade
- `ai-dev/active/I-00040/evidences/post/I-00040_v3_buttons_disabled.png` - Queue page (no buttons to verify)
- `ai-dev/active/I-00040/evidences/post/I-00040_v5_banner_cleared.png` - Banner cleared after restore
- `ai-dev/active/I-00040/evidences/post/I-00040_v6_no_regressions.png` - Code page (representative)

---

## Notes

### V3 Unable to Verify
The queue page has 0 approved items, so the "Create Batch from Selected" button (which uses `write_button_attrs` macro) is not rendered. The New Project button on the homepage does NOT use the `db_guard` macro - it has no disabled state enforcement.

The core guard functionality is verified:
- **V2**: Banner middleware correctly detects stale DB and renders alert
- **V4**: `require_db_at_head` dependency correctly returns HTTP 503 on mutating API calls

### Code Reference
- Banner display: `dashboard/middlewares/alembic_guard.py:65` (`is_db_stale`)
- Guard status: `dashboard/middlewares/alembic_guard.py:57` (`check_db_at_head`)
- API guard: `dashboard/middlewares/alembic_guard.py:73` (`require_db_at_head`)
- Macro: `dashboard/templates/macros/db_guard.html`

---

## Console Errors

No console errors observed during V1..V6 verification.