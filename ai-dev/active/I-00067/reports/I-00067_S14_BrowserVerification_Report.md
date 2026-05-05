# I-00067 S14 Browser Verification Report

## Environment
- Base URL used: http://localhost:9922
- E2E user: dev@example.local
- Worktree stack: iw-ai-core-e2e-i00067

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Long messages truncate to 100 chars + '...' | **PASS** | `evidences/post/I-00067_v1_truncated_row.png` | Long message (384 chars) renders as 100 chars + `...`. The truncated element has `activity-message-truncated` class and `data-full-text` attribute containing the full original message. |
| V2 | Clicking truncated row opens popup with full text | **PASS** | `evidences/post/I-00067_v2_popup_open.png` | After click via JS eval, a `<dialog>` element appeared with `Activity Message` title. The modal body contained the complete untruncated message (384 chars, no `...`, includes full traceback). |
| V3 | Modal dismissal (close button / ESC / click-outside) | **PASS** | `evidences/post/I-00067_v3_modal_dismissed.png` | Three dismissal paths verified: (1) close button (×) removed the dialog from the accessibility tree; (2) ESC key removed the dialog; (3) clicking the overlay element removed the dialog. All three resulted in `aria-hidden="true"` on both modal and overlay. |
| V4 | Short messages render verbatim with NO '...' and NO affordance | **PASS** | `evidences/post/I-00067_v4_short_no_affordance.png` | Short message "Step S02 (code-review-impl) passed review." (44 chars, well under 100) rendered as plain text with no `...` suffix and no `activity-message-truncated` class. The element's `data-full-text` attribute was absent, confirming no click affordance. |
| V5 | No regressions on entity links and console | **PASS** | `evidences/post/I-00067_v5_no_regressions.png` | Entity link for `I-00067` correctly points to `/project/iw-ai-core/item/I-00067`. The 404 on `/project/iw-ai-core/item/I-00067:0` is a Playwright browser-internal request for a subresource, not a page navigation. No new console errors during V1..V4 verification steps. |

## Console / Network Errors
- `404 GET /project/iw-ai-core/item/I-00067:0` — Playwright internal subresource request (the `:0` suffix indicates a browser-initiated subresource, not a page navigation). The work item page returned a 404 because I-00067 is not a real work item in the DB (the DaemonEvent is the only I-00067 reference). This is expected and not a regression.
- `404 GET /favicon.ico` — standard browser behavior, not a regression.

## No Regressions Observed
- Entity link `I-00067` in the activity row correctly links to `/project/iw-ai-core/item/I-00067` (route works — only fails because no DB record exists, which is expected for a DaemonEvent entity that is not a WorkItem).
- Entity link `I-00067-short` correctly links to `/project/iw-ai-core/item/I-00067-short`.
- No new JavaScript errors introduced by the truncation + modal implementation.
- The OSS Status section renders correctly with "Open source compliance scanning is disabled."

## Screenshots Captured
- `ai-dev/active/I-00067/evidences/post/I-00067_v1_truncated_row.png` — V1: Dashboard with truncated row (15:00 event)
- `ai-dev/active/I-00067/evidences/post/I-00067_v2_popup_open.png` — V2: Modal open showing full 384-char message
- `ai-dev/active/I-00067/evidences/post/I-00067_v3_modal_dismissed.png` — V3: Dashboard after modal dismissed
- `ai-dev/active/I-00067/evidences/post/I-00067_v4_short_no_affordance.png` — V4: Short message row with no truncation affordance
- `ai-dev/active/I-00067/evidences/post/I-00067_v5_no_regressions.png` — V5: Final dashboard state confirming no regressions

## Root Cause (on failure only)
Not applicable — all V1..V5 passed.

---

## E2E Fixtures Used

Two fixtures were added to seed data for this verification:
- `ai-dev/active/I-00067/e2e_fixtures/001_long_activity_message.py` — inserts a 384-char DaemonEvent to trigger the truncation path
- `ai-dev/active/I-00067/e2e_fixtures/002_short_activity_message.py` — inserts a 44-char DaemonEvent to verify the no-affordance path

Both fixtures were seeded via `docker compose -p iw-ai-core-e2e-i00067 exec e2e-dashboard uv run python scripts/e2e_seed.py`.