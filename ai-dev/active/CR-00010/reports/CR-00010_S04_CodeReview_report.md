# CR-00010 S04 Code Review Report

## Summary

Reviewed S03 (frontend-impl) changes for CR-00010. All checklist items pass. One LOW observation noted (queue.html defense-in-depth template filter uses `.type` string comparison, consistent with `QueueItem.type` being a string set from `r.type.value`).

## Verdict

**PASS**

## Files Changed (S03)

| File | Purpose |
|------|---------|
| `dashboard/routers/actions.py` | Added `WorkItemType` import; `approve_item` and `unapprove_item` reject research items with HTTP 422 |
| `dashboard/routers/project_pages.py` | Added `WorkItem.type != WorkItemType.Research` to `_queue_items()` query |
| `dashboard/templates/fragments/item_header.html` | Added `{% elif item_type == 'Research' %}` branch for inline notice |
| `dashboard/templates/pages/project/queue.html` | Added `{% if item.type != 'Research' %}` guard on draft approve button |

## Checklist Findings

### 1. Template Audit Completeness (AC8) — PASS

- `item_header.html` uses `item_type == 'Research'` (pre-computed string from `items.py:814`), correct.
- `queue.html` uses `item.type != 'Research'` where `item` is a `QueueItem` dataclass whose `.type` field is a string set from `r.type.value` in `project_pages.py:89-90`. Correct.
- No template uses `item.item_type` — the incorrect attribute name does not appear.
- Inline notice is a `<p>` with descriptive text, starts capital, ends period. Accessible.
- No new CSS introduced.

**Template audit cross-check**: grep confirms only `item_header.html` and `queue.html` contain item-level approve/unapprove actions. Both are guarded.

### 2. Route-Handler Rejection — PASS

- `approve_item` (actions.py:460-468): checks `item.type == WorkItemType.Research` BEFORE status check — correct order.
- `unapprove_item` (actions.py:718-723): checks `item.type == WorkItemType.Research` BEFORE status check — correct order.
- Both use `item.type` (ORM attribute, not `item_type`), correct.
- Response style: `HTTPException(status_code=422)` matches existing invalid-transition pattern in the same file.
- Error message for approve: `"Research items cannot be approved — they auto-complete when the research document is created."` — contains "Research items".
- Error message for unapprove: `"Research items do not use the approval workflow."` — contains "Research items".
- `WorkItemType` imported at module top (line 35), no duplicate.

### 3. Batch-Queue Backend Filter (AC9) — PASS

- `_queue_items()` at `project_pages.py:81`: `WorkItem.type != WorkItemType.Research` added to query predicate.
- Filter applied server-side in SQLAlchemy, not post-filtered in Python.
- `WorkItemType` imported at line 22, no duplicate.

### 4. Batch-Queue Template (Defense-in-Depth) — PASS

- `queue.html:128`: `{% if item.type != 'Research' %}` wraps the draft approve button row.
- Uses `.type` on `QueueItem` (string), not `.item_type`.

### 5. Cross-Layer Consistency — PASS

- Jinja: `item_type == 'Research'` (string compare), `item.type != 'Research'` (string compare).
- Python: `item.type == WorkItemType.Research` (enum compare).
- `WorkItemType.Research.value == "Research"` confirmed via `models.py:52`.
- ORM attribute name `type` (not `item_type`) confirmed via `models.py:291`.

### 6. Accessibility / UX — PASS

- `item_header.html:91-95`: `<p class="text-xs text-muted-foreground ml-auto">` with complete sentence. No `aria-hidden`. Screen-reader accessible.

### 7. Regression Surface — PASS

- Non-research items: approve/unapprove buttons still render for draft/approved items.
- `queue.html` approved items section: no research items can appear (backend SQL filter).
- `queue.html` drafts section: non-Research drafts show approve button via `{% if item.type != 'Research' %}` guard.
- No new `<script>` blocks introduced.

### 8. Code Quality — PASS

- No `| safe` filters on user-controlled data.
- No new CSS (reuses existing utility classes).
- Comments: none needed for this simple change — behavior is self-explanatory.

### 9. Project Conventions — PASS

- Business logic stays in `orch/` — only UI rejection in router, correct.
- Jinja autoescape on (inferred from project conventions).
- No new JS bundler / build step.

## Test Verification

| Check | Result |
|-------|--------|
| `uv run ruff check dashboard/` | PASS — All checks passed |
| `uv run ruff format --check dashboard/` | PASS — 28 files already formatted |
| `uv run mypy dashboard/` | PASS — No issues found in 28 source files |
| `make test-unit` | PASS — 818 passed, 5 warnings (no regressions) |

## Observations

**LOW (non-blocking)**: `queue.html:128` uses `item.type != 'Research'` where `item` is a `QueueItem` (string field). This is defense-in-depth; the authoritative exclusion is the SQL filter in `_queue_items()`. The string comparison is correct since `QueueItem.type` is set from `r.type.value` (a string), not an enum. This is a documentation/trust marker, not a functional requirement.

## Conclusion

S03 implementation is correct and complete. All acceptance criteria for AC8 and AC9 are satisfied. No CRITICAL or HIGH findings. Implementation follows existing patterns and project conventions.