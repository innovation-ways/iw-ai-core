# F-00090 S03 — Frontend Implementation Report

**Work Item**: F-00090 — Regression-rate tracking
**Step**: S03 (frontend-impl)
**Agent**: frontend-impl
**Date**: 2026-05-27

---

## What was done

Implemented the **Incident regression classification form** (AC5) for the F-00090 feature:

| File | Type | Purpose |
|------|------|---------|
| `dashboard/templates/fragments/regression_classification_form.html` | New | htmx form: searchable dropdown, commit SHA input, radio group, accept-suggestion button |
| `dashboard/templates/fragments/regression_suggestion_list.html` | New | Ranked heuristic suggestion list fragment |
| `dashboard/routers/items.py` | Modified | `GET /item/{id}/regression-suggestions` + `POST /item/{id}/regression-classify` + `_top_suggestion` helper |
| `dashboard/routers/search.py` | Modified | Added `GET /project/{pid}/work-items/search` (htmx-driven searchable dropdown) |
| `dashboard/templates/fragments/item_overview.html` | Modified | Mounted form include at bottom of overview tab |
| `tests/dashboard/test_regression_classification_form.py` | New | 8 tests covering AC5 + Boundary rows |

---

## TDD RED Evidence

The first test run (before the fragment existed) failed with:

```
tests/dashboard/test_regression_classification_form.py::test_form_renders_on_incident_detail_page FAILED

E   AssertionError: Expected searchable dropdown for introduced_by_work_item_id in response
E   assert 'name="introduced_by_work_item_id"' in '<!DOCTYPE html>\n<html lang="en">\n<head>...
```

This is the RED evidence captured per the TDD-first discipline in the design doc.

---

## Implementation Decisions

### Form design
- Searchable dropdown implemented via a `<datalist>` backed by `GET /project/{pid}/work-items/search` (htmx on `hx-get` with `change, keyup delay:200ms`). Not pre-loading all items — uses a DB query filtered by the typed query string.
- Commit SHA input uses HTML `pattern="[0-9a-fA-F]{7,40}"` for client-side validation and server-side regex re-validation in the route.
- "Accept suggestion" button only renders when `top_suggestion` is not None (computed from `suggest_introducer`).
- `classified_by` is `operator:{user}` for normal POST, `heuristic:auto` when `accept_top=1`.

### Route choices
- `POST /item/{item_id}/regression-classify` is **async** (required for `await request.form()` in FastAPI/Starlette).
- Error handling: `ValueError` → 422 with re-rendered form + inline error; `LookupError` → 404.
- `GET /item/{item_id}/regression-suggestions` uses `try/except` around `suggest_introducer` — never 500 on git failures.

### User identity
- Sourced from `request.headers.get("X-User-Name", "unknown")` — matches existing pattern in other routes.

### Search endpoint
- `GET /project/{pid}/work-items/search` added to `dashboard/routers/search.py` (logical home for work-item search). Filters merged (completed) items, orders by `updated_at DESC`, limits to 20 results.

---

## Test Coverage

| Test | Coverage |
|------|----------|
| `test_form_renders_on_incident_detail_page` | AC5: form elements + htmx target |
| `test_form_submit_persists_and_returns_row_fragment` | AC5: happy path, DB persisted |
| `test_form_validation_error_on_unknown_fk` | Boundary: ValueError → 422 + inline error |
| `test_accept_suggestion_uses_heuristic_auto` | Boundary: `accept_top=1` → `classified_by='heuristic:auto'` |
| `test_suggestion_button_hidden_when_no_candidates` | Boundary: no candidates → no accept button |
| `test_regression_suggestions_endpoint_returns_list` | Boundary: GET returns fragment (not full page) |
| `test_pre_existing_classification_omits_introduced_by` | Boundary: `pre_existing` sets FK=NULL |
| `test_commit_sha_validated_on_submit` | Boundary: invalid SHA → 422 |

---

## Test Results

```
tests/dashboard/test_regression_classification_form.py: 8 passed, 0 failed
```

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | `ruff format` — clean |
| `make typecheck` | `mypy` — no issues |
| `make lint` | `ruff check` + `scripts/check_templates.py` — all pass |

---

## Notes

- `WorkItemType` does not have an `Incident` value in the existing schema (only `Feature`, `Issue`, `ChangeRequest`, `Research`). Tests use `ChangeRequest` for I-NNNNN IDs.
- The regression classification form is mounted in the **overview tab** (`item_overview.html`), not on the detail page directly — this is the natural place since the form is part of the item metadata (not a separate action tab). The form appears on every incident item's detail page.
- The suggestions endpoint gracefully degrades: if the repo path is unavailable or git calls fail, it returns an empty list (no crash, no 500).