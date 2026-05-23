# CR-00078 S07 — Code Review Report

**Agent**: code-review-impl
**Work Item**: CR-00078 — Per-batch ignore overlap & force-start
**Step**: S07

---

## Scope

Per-agent review of S06's two new POST endpoints, the modified GET endpoint, and the Timeline extension.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | `BatchOverlapIgnore` model (composite PK on 5 columns) |
| `dashboard/routers/actions.py` | Two new POST endpoints (`ignore_single_overlap`, `ignore_all_overlaps`) |
| `dashboard/routers/batches.py` | New GET endpoint `overlap_modal` + shared `_get_item_scope_events` helper |
| `orch/daemon/batch_manager.py` | Ignore-set filtering before held-branch decision |
| `orch/daemon/scope_overlap.py` | Pure `filter_blocked_by_ignores()` helper |

---

## Finding Summary

| Severity | Count | Notes |
|----------|-------|-------|
| CRITICAL | 0 | |
| HIGH | 0 | |
| MEDIUM | 0 | |
| LOW | 1 | `actions.py` has a duplicate copy of `_get_item_scope_events` (both modules define it independently); not a correctness issue — identical implementation. |

---

## Detailed Review

### 1. Idempotency — ✅ PASS

Both POST endpoints use `pg_insert(...).on_conflict_do_nothing(index_elements=[...])` against the full composite PK `(project_id, batch_id, held_item_id, blocking_item_id, file_pattern)`. Not wrapped in try/except.

### 2. Event emitted on idempotent path (AC2) — ✅ PASS

`ignore_single_overlap`: `db.execute(stmt)` is unconditional. `_emit(...)` / `db.commit()` follow immediately. No `if inserted:` guard.

`ignore_all_overlaps`: event emitted after the `if pairs:` block, so it fires even when all pairs were already ignored.

### 3. `ignore-all` count — ✅ PASS

Count is computed from `len(pairs)` — the deduped set extracted from events — before the insert. When all pairs are already ignored the count is still correct (non-zero, since events exist to trigger the endpoint).

### 4. Window consistency — ✅ PASS

All three event-reading locations (`_get_scope_statuses` in `batches.py`, `_get_item_scope_events` in `batches.py`, `_get_item_scope_events` in `actions.py`) use `window_secs=300` as a function parameter default. One hardcoded `300` literal in the call sites — consistent.

### 5. GET endpoint filters — ✅ PASS

`overlap_modal` loads the `ignored_set` keyed by `(blocking_item_id, file_pattern)` and filters events by that granularity. Not just `blocking_item_id`.

### 6. Timeline extension — ✅ PASS (partial — no template changes needed)

The `logs` tab in `batch_detail.html` renders all `DaemonEvent` rows with `ev.event_type` and `ev.message or '—'` directly — no special-case per-type logic required. All 3 new event types render automatically with their `message` field as the primary text. `event_metadata` is read-only.

### 7. `ignored_by` placeholder — ✅ PASS

Exactly one literal `"operator"` with `# TODO(auth): replace placeholder when session subjects land` comment in `actions.py`. No other actor strings.

### 8. No DB writes outside POST endpoints — ✅ PASS

Searched `db.add(`, `db.commit(`, `db.flush(` in changed lines of `batches.py` — none. `batch_manager.py` has writes but in the daemon path (legitimate). `overlap_modal` is read-only.

### 9. Route mounting — ✅ PASS

New endpoints use the existing `actions.router` and `batches.router`. No new router module created.

### 10. `hx-confirm` — ✅ PASS

`hx-confirm` is a htmx client-side attribute set in templates. Not enforced server-side.

---

## Quality Gates

| Check | Result |
|-------|--------|
| `uv run ruff check` | ✅ All checks passed |
| `uv run mypy` | ✅ No issues found |
| Unit tests (`tests/unit/test_daemon_overlap_filter.py`) | ✅ 1 passed (1 test for the new pure helper) |

---

## Notes

1. **Duplicate helper (`LOW`)**: `actions.py` defines its own `_get_item_scope_events` copy. `batches.py` also has one. Both are identical. Not a correctness issue but a maintenance surface — if the 300s window ever changes, both copies need updating. This could be extracted to a shared utility. Acceptable as-is given the review scope.

2. **Timeline rendering**: The `logs` tab in `batch_detail.html` uses a generic event-type badge + message fallback pattern. New event types are rendered automatically without template changes.

3. **No new router module**: Endpoints registered on existing `actions.router` and `batches.router`.

4. **`batch_overlap_allowed_by_ignore` event**: Emitted only when all overlapping pairs were ignored (clears `blocked_by` to `[]`). Correct — prevents duplicate "allowed" events when only some pairs are ignored.

---

## Completion Status

**complete** — All 10 review items pass. No CRITICAL or HIGH findings. 1 LOW (duplicate helper).