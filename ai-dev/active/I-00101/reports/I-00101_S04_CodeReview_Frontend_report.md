# I-00101 S04 — Code Review: Frontend (S03)

**Work Item**: I-00101 — Scope-violation escalations strand work items with no UI surface or remedy
**Step**: S04 — CodeReview_Frontend
**Agent**: code-review-impl
**Reviewed**: S03 (Frontend)
**Status**: PASS

---

## Summary

Reviewed S03 Frontend implementation against the design document and CLAUDE.md conventions. All CRITICAL and HIGH checks pass. One MEDIUM_FIXABLE finding: per-step query loop (N+1 pattern) in `items.py` and `running.py` for `latest_scope_violation`.

---

## Pre-Flight Gate

| Check | Result |
|-------|--------|
| `make lint` | PASS — all checks passed |
| `make format` | PASS — 759 files already formatted |
| `make css` | PASS — "Nothing to be done" (plain CSS fallback in styles.css covers badge variant) |

---

## Files Changed (S03 Scope)

| File | Change |
|------|--------|
| `dashboard/templates/components/status_badge.html` | Added `scope_blocked` key |
| `dashboard/routers/items.py` | Added `scope_violations` to `StepDetail`; per-step query in `_get_steps()` |
| `dashboard/templates/fragments/item_steps_table.html` | Badge + Amend/Revert/Skip buttons |
| `dashboard/templates/components/scope_amend_modal.html` | **NEW** — modal fragment |
| `dashboard/routers/actions.py` | Three new endpoints |
| `dashboard/routers/running.py` | `FailedRow.scope_violations` + per-step query |
| `dashboard/templates/pages/system/running.html` | Badge + buttons in global table |
| `dashboard/static/styles.css` | `.badge-scope-blocked` plain CSS fallback |

**Scope discipline**: All changed files match the design doc's S03 File Manifest. No S01/S02 files were modified by S03.

---

## Review Checklist Findings

### 1. Badge variant correctness — PASS
- `status_badge.html` has `scope_blocked` key with distinct amber classes (`bg-amber-200 text-amber-900 border border-amber-400`)
- Existing mappings unchanged (PASS — git diff confirms no other keys modified)
- Badge is visually distinct from `needs_fix` (amber tone with explicit "Scope blocked" label)

### 2. Items.py wiring — MEDIUM_FIXABLE (N+1 query)
```python
for step_db_id in needs_fix_ids:
    violations = latest_scope_violation(db, step_db_id)
```
This loops over needs_fix steps calling `latest_scope_violation` per step. For an item with N needs_fix steps, this produces N+1 queries. A bulk fetch (single query with `IN` clause and `ORDER BY cycle_number DESC` per step) would eliminate the N+1.

**Impact**: Low-Medium — typically an item has 0-2 needs_fix steps; not a high-frequency path.

### 3. Template branch correctness — PASS
- `item_steps_table.html` uses `{% if step.scope_violations %}` (falsy on `None`, truthy on `list`)
- Restart button hidden on scope-blocked rows (confirmed via `{% if step.scope_violations %}` branch)
- Skip button rendered on scope-blocked rows
- "Amend scope & restart" uses `hx-get` to `/project/{project_id}/api/item/{item_id}/scope/amend-modal/{step_id}`
- "Revert & restart" uses `hx-post` with `hx-confirm`
- Badge has `title` and `aria-label` listing offending paths

### 4. Modal partial — PASS
- Does NOT extend `base.html` (correct for fragment)
- Form posts to `/project/{{ item.project_id }}/api/item/{{ item.id }}/scope/amend-and-restart/{{ step.step_id }}` (matches GET pattern)
- Checkboxes use `name="paths"` (FastAPI `paths: list[str] = Form(...)` collects from this)
- All violation paths pre-checked (`checked` attribute)
- Current `allowed_paths` rendered as read-only list (no inputs)
- No clipboard buttons present (no violation)

### 5. Endpoint correctness — PASS
- GET `amend-modal` validates `latest_scope_violation IS NOT None` → 422
- POST `amend-and-restart` validates same AND rejects off-list paths (HTTP 422)
- POST `amend-and-restart` emits `scope_amended_by_operator` with `{step_id, added_paths, manifests_updated}` ✓
- POST `amend-and-restart` DB mutations match `restart_step`: new `StepRun` (run_number+1, pending), step.status→pending, started_at/completed_at cleared, item.status fixed if failed, single `db.commit()` ✓
- POST `revert-and-restart` calls `revert_paths_in_worktree(violations)` ✓
- POST `revert-and-restart` emits `scope_reverted_by_operator` with `{step_id, reverted_paths, failed_paths}` ✓
- Both POSTs handle `needs_fix` correctly (do NOT reject it unlike `restart_step`) ✓
- No `restart_step` widening detected

### 6. Global needs-attention table — PASS
- `running.py::_query_failed_steps` builds `scope_violations_map` keyed on `step.id`
- Attached to each `FailedRow` as `scope_violations`
- Template renders `badge-scope-blocked` when `row.scope_violations` is set

### 7. CSS / styles — PASS
- `make css` reports "Nothing to be done" — `.badge-scope-blocked` plain CSS in `styles.css`
- CSS changes scoped to new badge variant only

### 8. Template linter — PASS
- `make lint` passes `scripts/check_templates.py`
- No new numeric/duration formatting introduced in templates

### 9. Scope discipline — PASS
- All S03 files match design doc S03 File Manifest
- `orch/daemon/fix_cycle.py` modified (but this is S01 scope, already reviewed in S02)
- `orch/daemon/scope_amendment.py` is new (S01 scope)

### 10. TDD RED Evidence — PASS
- S03 report has `tdd_red_evidence: "n/a — Frontend wires up…"` — correct per design

---

## Test Verification

```
uv run pytest tests/dashboard/ -v --no-cov
==== 940 passed, 15 skipped, 25 deselected, 1 xfailed in 177.04s (0:02:57) ====
```

No regressions in existing dashboard test suite.

---

## Findings Summary

| Severity | File | Line(s) | Issue | Suggested Fix |
|----------|------|---------|-------|---------------|
| MEDIUM_FIXABLE | `dashboard/routers/items.py` | 469-474 | N+1 query: loop calling `latest_scope_violation` per step | Bulk fetch with single query + dict construction |
| MEDIUM_FIXABLE | `dashboard/routers/running.py` | 186-192 | Same N+1 pattern in `_query_failed_steps` | Same as above |

**Mandatory fix count**: 0 (MEDIUM_FIXABLE does not block merge)

---

## Notes

- The N+1 pattern in `items.py` and `running.py` is acceptable for now given the low cardinality of needs_fix steps per item. A future optimization could batch the `latest_scope_violation` calls.
- The plain CSS `.badge-scope-blocked` fallback in `styles.css` is the correct mitigation for `make css` reporting "Nothing to be done" (per I-00067).
- The `scope_amendment.py` and `fix_cycle.py` changes visible in git diff are S01/S02 scope and were already reviewed in S02. S03 correctly imports from `scope_amendment.py` without modifying it.
