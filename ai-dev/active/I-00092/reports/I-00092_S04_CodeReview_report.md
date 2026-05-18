# I-00092_S04_CodeReview_report

## Work Item
I-00092 — Auto-merge filter chip never highlights the active filter

## Step
S04 — Code review of S03 (tests-impl)

---

## What Was Reviewed

The S03 agent added 3 regression tests to `tests/dashboard/test_auto_merge_routes.py` plus a `_extract_filter_chip_blocks` helper.

---

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 750 files already formatted |
| `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` | ✅ 28 passed in ~32s |

Coverage failure is pre-existing and unrelated to these changes (total 20% vs 50% fail-under across the full suite).

---

## Review Checklist

### 1. Test placement (I-00067)
✅ All tests using `client` are under `tests/dashboard/test_auto_merge_routes.py`.

### 2. Semantic correctness over shape (I003)
✅ All three tests use attribute-scoped assertions:

- `test_filter_chip_resolved_is_highlighted_when_active`:
  ```python
  assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"])
  ```
- `test_filter_chip_all_is_highlighted_when_no_type_param`:
  ```python
  assert re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["all"])
  ```
- `test_filter_chip_title_tooltips_match_event_types`:
  ```python
  assert 'title="merge_auto_resolved"' in chips["resolved"]
  ```
  No bare `status_code == 200` as the only assertion anywhere.

### 3. Coverage — minimum 3 tests present
| Required test | Status |
|---|---|
| `test_filter_chip_resolved_is_highlighted_when_active` | ✅ Present |
| `test_filter_chip_all_is_highlighted_when_no_type_param` | ✅ Present |
| `test_filter_chip_title_tooltips_match_event_types` | ✅ Present |

### 4. Helper isolation
✅ `_extract_filter_chip_blocks` (line 44) asserts all 7 chips are found:
```python
assert expected <= out.keys(), f"missing chips: {expected - out.keys()}"
```
A future template refactor that drops a chip will surface as a clear failure.

### 5. Attribute-scoped CSS class assertions (I-00067)
✅ Both highlight tests use `re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chip)` — anchors the match to the `class` attribute, cannot be satisfied by CSS definitions elsewhere in the document.

### 6. Targeted-run discipline
✅ `tests_passed` reflects the `test_auto_merge_routes.py` file only, not `make test-unit` or `make test-integration`.

### 7. TDD RED evidence
The S03 report correctly states `n/a — coverage step (tests-impl)`.

---

## Template Fix Verification

The S01 fix was reviewed as part of this step. `auto_merge_events_table.html` line 17:

```jinja
{% set _is_active = (mapped is none and not request.query_params.get('type')) or (mapped is not none and type_filter == mapped) %}
```

- `type_filter = request.query_params.get('type', 'all')` (line 1)
- For `?type=merge_auto_resolved`: `type_filter = 'merge_auto_resolved'`, `mapped = 'merge_auto_resolved'` → `True` ✅
- For `?type=` (empty / all chip): `mapped is none` → `True` ✅
- For other chips with `?type=merge_auto_resolved`: `mapped is not none and 'merge_auto_resolved' == 'merge_auto_resolved'` → `False` ✅

---

## Files Changed

- `tests/dashboard/test_auto_merge_routes.py` — added `_extract_filter_chip_blocks` helper and 3 regression tests

---

## Verdict

**PASS** — no mandatory fixes required. All review checklist items are satisfied.

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00092",
  "step_reviewed": "S03",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "28 passed in 32s (all new tests green, coverage failure is pre-existing)",
  "notes": "All 3 required tests present with correct attribute-scoped assertions; helper raises on missing chips; targeted-run discipline followed."
}
```