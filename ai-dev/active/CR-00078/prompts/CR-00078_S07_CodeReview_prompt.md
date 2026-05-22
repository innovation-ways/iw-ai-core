# CR-00078_S07_CodeReview_prompt

**Work Item**: CR-00078 -- Per-batch ignore overlap & force-start
**Step**: S07
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
No migration work in this step.

## Scope of Review

Per-agent review of S06's two new POST endpoints, the modified GET endpoint, and the Timeline extension.

1. **Idempotency** — both POST endpoints use `insert(...).on_conflict_do_nothing()` (NOT a try/except wrapper around an INSERT, which is the slow / lossy pattern). Verify `index_elements` (or `constraint=`) targets the composite PK.

2. **Event still emitted on idempotent path** (AC2) — the second POST to the same `/ignore` still emits a `batch_overlap_ignored_by_operator` event for audit. Verify by inspecting the order of statements in the handler (event emission must NOT be inside an `if inserted:` guard).

3. **`ignore-all` count** — the count in the emitted `batch_overlap_ignore_all_by_operator` event is the number of pairs derived from the events, NOT the row count from the INSERT (which can be 0 if all pairs were already ignored). Verify the count is computed from the deduped set BEFORE the insert.

4. **Window consistency** — `ignore-all` reads the 300s window using the same constant / helper as `_get_scope_statuses` and the CR-00077 GET endpoint. If a second hardcoded `300` appears in S06's diff, flag MAJOR.

5. **GET endpoint filters** — the modified GET correctly filters out ignored pairs. Important: it must filter at the (`blocking_item_id`, `file_pattern`) granularity, NOT just by `blocking_item_id` (which would over-filter when only some files are ignored).

6. **Timeline extension** — all 3 new event types (`batch_overlap_ignored_by_operator`, `batch_overlap_ignore_all_by_operator`, `batch_overlap_allowed_by_ignore`) have a render line; missing payload fields fall back to `(unknown)` rather than crashing.

7. **`ignored_by` placeholder** — exactly one literal `"operator"` in S06's diff, with a `# TODO(auth):` comment. No other actor strings sneaked in.

8. **No DB writes outside the two POST endpoints** — the modified GET endpoint and Timeline rendering are read-only. Verify by searching for `db.add(`, `db.commit(`, `db.flush(` in the changed lines of `batches.py` — there should be NONE in the changed regions.

9. **Route mounting** — endpoints are registered on the existing router; no new router module created.

10. **`hx-confirm` text** — server doesn't need to know it, but verify S06 didn't try to enforce the confirm server-side (htmx handles it client-side).

## Severity Guide

- CRITICAL: missing on_conflict_do_nothing; ignore filter at wrong granularity (only by blocking_item_id); event-emission inside an inserted-only guard.
- HIGH: hardcoded 300s window in a second location; GET endpoint writes to DB; missing fallback for missing event_metadata keys in Timeline rendering.
- MEDIUM: `ignored_by` literal duplicated; missing TODO comment.
- LOW: imports, docstring polish.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-impl",
  "work_item": "CR-00078",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
