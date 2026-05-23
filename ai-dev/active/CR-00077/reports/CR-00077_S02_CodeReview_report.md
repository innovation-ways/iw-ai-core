# CR-00077 S02 Code Review Report — Overlap details popup (read-only)

**Reviewer**: code-review-impl  
**Step**: S02  
**Work Item**: CR-00077  
**Files Reviewed**: `dashboard/routers/batches.py`, `dashboard/templates/fragments/batch_overlap_modal.html`, `tests/unit/test_batch_overlap_grouping.py`  
**Reviewed Against**: `CR-00077_CR_Design.md`, `CR-00077_S01_API_report.md`, `git diff HEAD~..HEAD`

---

## Summary

S01 correctly implements the API endpoint, helper, and template stub. All preflight gates pass (lint ✅, format-check ✅, typecheck ✅). The critical `batch_items_fragment` context fix is confirmed present. However, **one CRITICAL finding** emerged from cross-checking the diff against the production event schema: `_get_scope_statuses` (an existing function, not written by S01) reads `blocker_item_id` but production daemon events write `blocking_item_id`.

---

## Findings

### ❌ CRITICAL — Schema drift: `_get_scope_statuses` reads `blocker_item_id` but production emits `blocking_item_id`

**Location**: `dashboard/routers/batches.py:202`

**What happened**: S01 changed line 202 from:
```python
blocking = meta.get("blocking_item_id", "")
```
to:
```python
blocking = meta.get("blocker_item_id", "")
```

**Problem**: The production daemon in `orch/daemon/batch_manager.py` (line 518) writes `blocking_item_id` into `item_held_for_scope` events, not `blocker_item_id`. The production schema was verified by `git show ed408e6c:orch/daemon/batch_manager.py | grep blocking_item_id`, which confirms `blocking_item_id` as the live key.

Cross-referencing: the pre-CR state of `_get_scope_statuses` (at `9e4aa553`) reads `blocking_item_id`. The S01 diff introduced `blocker_item_id`. This is a regression introduced by S01 (or possibly by a parallel CR-00078 commit that landed in the same merge).

**Impact**: Every held item on every batch detail page and queue page would display `Held: overlaps with on \`…\`` — the blocking item name is missing from the pill text and tooltip. This is a live data corruption issue affecting all users of the scope-gate feature, not limited to the overlap modal.

**Fix**: Revert line 202 to `blocking = meta.get("blocking_item_id", "")`.

---

### ✅ HIGH — Fragment discipline: `batch_overlap_modal.html` does not extend `base.html`

Confirmed: the stub has no `{% extends %}` directive. It renders only a `<div class="iw-overlap-modal-body">` root, suitable for htmx swap into the modal overlay container.

---

### ✅ HIGH — `batch_items_fragment` context fix: `batch` now passed

Confirmed at `batches.py:689-705`:
```python
batch = _get_batch_or_404(project_id, batch_id, db)
```
and passed as `"batch": batch` in the template context. The S03 `Held` pill trigger (which will have `hx-get="/project/{slug}/batch/{{ batch.id }}/overlap/{{ held_item_id }}"`) will survive htmx live refreshes of the Items tab. No regression risk.

---

### ✅ MEDIUM — Duplicate window literal: `_overlap_window_cutoff` introduced

`_overlap_window_cutoff(300)` now encapsulates `datetime.now(UTC) - timedelta(seconds=300)`. `_get_scope_statuses` still hardcodes the same literal inline (line 168). This is **not a new duplication** introduced by S01 — it pre-existed. S01 is correct to expose the helper so CR-00078 can reuse it without further duplication. No action required.

---

### ✅ LOW — `group_overlap_events` is pure, importable from `tests/unit/`

- No DB calls, no logging, no `datetime.now()` inside the function.
- Defensive on `None` metadata: `ev.event_metadata or {}`.
- Skips events without `blocker_item_id` or `conflicting_globs` silently.
- Explicit return type `list[tuple[str, list[str]]]` — no `Any` leakage.
- Importable without FastAPI/dashboard runtime dependencies.
- Signature: `def group_overlap_events(events: list[DaemonEvent]) -> list[tuple[str, list[str]]]:` — importable from `tests/unit/`.

---

### ✅ MEDIUM — `overlap_modal` endpoint: read-only, thin, 404 on empty

- No `db.add()`, `db.commit()`, `db.flush()`, `SELECT FOR UPDATE`.
- Returns 404 when `events` list is empty (correct per AC5).
- Thin: delegates to `group_overlap_events` + `db.get(WorkItem, ...)` for title lookup.
- Business logic stays in helpers.
- Returns `HTMLResponse` via `TemplateResponse`.

---

### ✅ LOW — Template: Jinja autoescape active

`batch_overlap_modal.html` uses `{{ section.blocking_item_id }}` and `{{ glob }}` inside `<code>` elements. FastAPI's `Jinja2Templates` (dashboard default) autoescapes HTML in `.html` templates. A glob like `<img src=x onerror=alert(1)>` would render as literal text, not as executable markup. ✅

---

### ✅ MEDIUM — Router hygiene

- Route mounted on existing `router` (no new router module).
- Path: `/batch/{batch_id}/overlap/{held_item_id}` (no conflict with existing routes).
- `project_id` from path parameter matches `DaemonEvent.project_id` in both conditions of the `where` clause.

---

### ✅ MEDIUM — Type hints: helper signature

`group_overlap_events` has explicit types. `overlap_modal` returns `Any` (common in FastAPI route handlers for `TemplateResponse`) — acceptable.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 867 files already formatted |
| `make typecheck` (mypy) | ✅ No issues in `batches.py` |
| Unit tests | ✅ 10/10 passed (coverage failure exit code irrelevant — just coverage threshold) |

---

## Verdict

**1 CRITICAL blocking finding**: revert `dashboard/routers/batches.py:202` to `blocking_item_id`.  
No other changes required.

---

## Files Changed (S01)

| File | Change |
|------|--------|
| `dashboard/routers/batches.py` | Added `group_overlap_events`, `_overlap_window_cutoff`, `overlap_modal`, `batch_items_fragment` context fix; **accidentally changed** `_get_scope_statuses` line 202 from `blocking_item_id` to `blocker_item_id` |
| `dashboard/templates/fragments/batch_overlap_modal.html` | New stub — handles empty (404) and populated (sections) states |
| `tests/unit/test_batch_overlap_grouping.py` | New — 10 tests for `group_overlap_events` |

---

## Notes

- `make test-unit` reported coverage failure (exit code 1) but the underlying tests all passed. The coverage threshold is set to 50% globally; the new test file alone does not lift the project-wide coverage above that. This is a pre-existing infrastructure issue, not an S01 problem.
- The `overlap_modal` endpoint's 404 empty-state message (`"No overlap details available — the item may have been released since this page rendered."`) matches AC5 exactly.
- CR-00078 code (`_get_item_scope_events`, `BatchOverlapIgnore` ignore endpoints) is present in the file as pre-existing context. Not reviewed here — S04 owns that.