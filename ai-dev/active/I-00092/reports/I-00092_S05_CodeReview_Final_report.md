# I-00092_S05_CodeReview_Final_report

## Work Item
I-00092 — Auto-merge filter chip never highlights the active filter

## Step
S05 — Final Code Review (cross-agent integration review)

---

## What Was Reviewed

- **Design doc**: `I-00092_Issue_Design.md` (AC1–AC4, root cause, fix plan)
- **Functional doc**: `I-00092_Functional.md`
- **S01 report**: Frontend implementation of filter chip fix
- **S02 report**: Per-agent review of S01 → PASS
- **S03 report**: Regression tests for chip active-state
- **S04 report**: Per-agent review of S03 → PASS

---

## Pre-Review Gates (NON-NEGOTIABLE)

| Gate | Command | Result |
|------|---------|--------|
| Lint | `make lint` | ✅ All checks passed |
| Format | `make format` | ✅ 750 files already formatted |

---

## Template Implementation Review

**File**: `dashboard/templates/fragments/auto_merge_events_table.html`

**Root cause**: Old comparison `type_filter == key` compared URL value `"merge_auto_resolved"` to short label `"resolved"` → always False.

**Fix applied** (line 17):
```jinja
{% set _is_active = (mapped is none and not request.query_params.get('type')) or (mapped is not none and type_filter == mapped) %}
{% if _is_active %}bg-primary text-primary-foreground border-primary{% else %}border-border text-muted-foreground{% endif %}
```

- For `?type=merge_auto_resolved`: `type_filter='merge_auto_resolved'`, `mapped='merge_auto_resolved'` → `_is_active=True` ✅
- For no `type` param (all chip): `mapped is none and not request.query_params.get('type')` → `_is_active=True` ✅
- Mutual exclusivity enforced — exactly one chip is active per render ✅

**Accessibility attributes**:
- `title="{{ mapped or 'all event types' }}"` on every chip (line 18) ✅
- `aria-pressed="{{ 'true' if _is_active else 'false' }}"` on every chip (line 19) ✅

---

## Test Review

**File**: `tests/dashboard/test_auto_merge_routes.py` (3 new tests + helper)

### `_extract_filter_chip_blocks` helper
- Parses `<a>` elements from fragment HTML keyed by chip label
- Asserts all 7 chips present — future template refactor that drops a chip fails clearly ✅

### `test_filter_chip_resolved_is_highlighted_when_active` (AC1)
- GET `/auto-merge/events?type=merge_auto_resolved`
- `resolved` chip: `re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chips["resolved"])` ✅
- `resolved` chip: `'aria-pressed="true"' in chips["resolved"]` ✅
- All other 6 chips: `"bg-primary" not in chips[other]` ✅
- All other 6 chips: `'aria-pressed="false"' in chips[other]` ✅

### `test_filter_chip_all_is_highlighted_when_no_type_param` (AC2)
- GET `/auto-merge/events` (no `type` param)
- `all` chip: `bg-primary` via attribute-scoped regex ✅
- `all` chip: `aria-pressed="true"` ✅
- All other 6 chips: `bg-primary` absent ✅

### `test_filter_chip_title_tooltips_match_event_types` (AC3)
- Each chip's `<a title="...">` verified against expected event_type string ✅
- `all` chip: `title="all event types"` ✅

### I-00067 compliance (attribute-scoped assertions)
All CSS class assertions use `re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', ...)` — anchors to `class` attribute, cannot be satisfied by CSS definitions elsewhere in the document.

### Test placement
All tests using `client` fixture are under `tests/dashboard/` — correct location ✅

---

## Cross-Agent Integration Check

| Check | Status |
|-------|--------|
| Template emits CSS classes that tests look for (`bg-primary`, `border-primary`, `text-primary-foreground`) | ✅ Exact match |
| Template `aria-pressed` values match what tests assert (`"true"` / `"false"`) | ✅ Exact match |
| Template `title` values match what tests assert (`merge_auto_resolved`, etc.) | ✅ Exact match |
| Template comparison uses `mapped` (URL values), not `key` (short labels) | ✅ Correct |
| No `| safe` filter on user-controlled values | ✅ Jinja2 auto-escape used |
| No docker commands in implementation | ✅ Policy compliant |
| No migration files created | ✅ Policy compliant |

---

## Test Run Results

### Unit tests (`make test-unit`)
```
3075 passed, 4 skipped, 5 xfailed, 2 xpassed, 46 warnings in 68.93s
Required coverage 50.0% reached — Total: 52.55%
```

### Dashboard auto-merge tests (`uv run pytest tests/dashboard/test_auto_merge_routes.py -v`)
```
28 passed in 39.16s
```

All three I-00092 regression tests pass:
- `test_filter_chip_resolved_is_highlighted_when_active` ✅
- `test_filter_chip_all_is_highlighted_when_no_type_param` ✅
- `test_filter_chip_title_tooltips_match_event_types` ✅

Coverage warning (20%) is pre-existing and unrelated to this change.

---

## Acceptance Criteria Verification

| AC | Requirement | Implementation | Status |
|----|-------------|----------------|--------|
| AC1 | Selected chip highlighted with `bg-primary`; no other chip has it | Template: `_is_active` + `bg-primary`; tests: attribute-scoped regex | ✅ |
| AC2 | "all" chip active when no `type` param | Template: special case `mapped is none and not request.query_params.get('type')`; test: no-param request | ✅ |
| AC3 | Each chip has `title` tooltip + `aria-pressed` | Template: lines 18–19; test: `title=` assertions + `aria-pressed` checks | ✅ |
| AC4 | Regression test exists and passes | `tests/dashboard/test_auto_merge_routes.py` — 3 tests present and green | ✅ |

---

## Mandatory Fix Count
**0** — no issues found.

---

## Verdict

**PASS**

The implementation is minimal, correct, and complete. The filter chip active-state comparison has been fixed (`type_filter` compared to `mapped` URL values instead of short `key` labels), accessibility attributes are properly applied, and regression tests with attribute-scoped assertions cover AC1–AC3.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/auto_merge_events_table.html` | Fixed active-chip comparison logic (compares `type_filter` to `mapped`); added `title` tooltip and `aria-pressed` to each chip |
| `tests/dashboard/test_auto_merge_routes.py` | Added `_extract_filter_chip_blocks` helper and 3 regression tests covering AC1, AC2, AC3 |

---

## JSON Result

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00092",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3075 unit tests passed; 28 auto-merge route tests (incl. 3 I-00092 regression tests) passed",
  "missing_requirements": [],
  "notes": "All ACs satisfied. Template fix is a single focused change. Tests use attribute-scoped assertions (I-00067). No docker commands, no migrations, no | safe filters. Jinja2 auto-escape used for title attribute."
}
```