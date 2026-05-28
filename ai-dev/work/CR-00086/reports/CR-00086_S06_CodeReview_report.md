# CR-00086 S06 CodeReview — Frontend Panel + Jobs Integration

**Step**: S06  
**Agent**: CodeReview  
**Work Item**: CR-00086  
**Status**: PASS

---

## Pre-Review Gate

| Gate | Result |
|------|--------|
| `make lint` | ✅ PASS — ruff + node template check + Jinja2 `%`-style format filter check all green |
| `make format` | ✅ PASS — ruff format check, 964 files already formatted |

---

## 1. Architecture Compliance

### ✅ Router endpoints share a single partial-render helper

Both `dashboard/routers/tests.py` and `dashboard/routers/quality.py` define `test_health_fragment()` and delegate to `_test_health_helpers.build_test_health_cards()`. The endpoint bodies are functionally identical (build cards + template render). This is acceptable — the duplication is trivial (3 lines each, identical structure) and both routes share the helper module which contains all non-trivial logic. **No copy-paste of fragment-prep code.**

### ✅ Jobs aggregator uses SQLAlchemy subquery for grouping (not Python concat)

`_fetch_test_health_capture()` groups by `func.date_trunc('minute', ts)` via a subquery, following the same pattern used for other job types. One capture invocation (up to 4 metric rows at the same ts) produces exactly one `JobRow`. **Not Python-side concat.**

### ✅ Jinja2 `%`-style format filters

`"+%.1f"|format(...)` and `"%.1f"|format(...)` used consistently throughout `test_health_panel.html`. No `{}.format`-style calls. `scripts/check_templates.py` (part of `make lint`) confirmed clean.

---

## 2. Code Quality

### ✅ Empty-state per metric (AC5): test asserts placeholder text, not hollow SVG

`test_panel_empty_state_per_metric` seeds only `mutation_score` (3 snapshots), then asserts:
- `html.count("no data yet") == 3` — correct, asserts the text placeholder
- `html.count('viewBox="0 0 80 28"') == 1` — correct, one sparkline for the seeded metric
- `"Test health data will appear after the first capture runs" not in html` — correct, no combined empty state

**No hollow `<svg>` assertion. No NaN. Test is behaviour-pinning.**

### ✅ Combined empty state test exists and asserts ONE message

`test_panel_combined_empty_state` asserts `"Test health data will appear after the first capture runs" in html` and confirms `"no data yet" not in html.lower()` and `"<svg" not in html`. **Correct.**

### ✅ Sparkline Y-axis inversion: test confirms decreasing y-coords for ascending values

`test_sparkline_ascending_values` extracts y-coords from the path with regex, then asserts:
```python
for i in range(1, len(ys)):
    assert ys[i] <= ys[i - 1], (f"Y-coords not monotonically decreasing at index {i}: {ys}")
```
Ascending values → decreasing y (SVG coordinate system inverted). **CRITICAL check: PASS.**

### ✅ Jobs aggregator de-duplication: one row per capture minute

`test_multiple_captures_one_job_row_per_minute` inserts 4 snapshots (2 metrics per capture, same minute) and asserts `len(th_job_rows) == 1`. Design explicitly called this out; test exists and passes. **HIGH check: PASS.**

---

## 3. Project Conventions

### ✅ `dashboard/CLAUDE.md` htmx patterns followed

- Fragment endpoint returns full fragment HTML (no wrapper div from router)
- `hx-get`, `hx-trigger="load"`, `hx-swap="innerHTML"` on mount div
- No `hx-indicator` or other non-standard attributes

### ✅ No new client-side JS dependencies

Panel is server-rendered SVG + plain htmx. No JS chart library imported. Delta arrows are inline SVGs.

### ✅ Tailwind utility classes reused

All CSS classes (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4`, `bg-card border border-border rounded-lg p-4`, etc.) are existing utilities from the Tests view. No new global CSS added. `make css` was not run (not broken).

---

## 4. Security

### ✅ No `|safe` on metric values; Jinja2 autoescape active

`test_health_panel.html` uses `{{ card.value_format | format(card.latest_value) }}` with no `|safe`. Delta display also uses `|format()` — no raw user input rendered unescaped. Values originate from the DB but still pass through autoescape.

### ✅ `slug` param not used in path traversal

Both router endpoints use `project_id` (not slug) for DB lookup. The htmx mount block uses `current_project.id` (the DB PK), not a slug. No `Path(...).resolve()` or similar path-traversal risk in this code.

---

## 5. Testing

### ✅ TDD file cross-check: all design test files exist

| Design TDD File | Present? | Notes |
|-----------------|----------|-------|
| `tests/unit/test_test_health_sparkline.py` | ✅ | 6 tests, all pass |
| `tests/dashboard/test_test_health_panel.py` | ✅ | 4 tests, all pass |
| `tests/integration/test_jobs_aggregator_test_health.py` | ✅ | 3 tests, all pass |
| `tests/integration/test_test_health_service.py` (S03) | ✅ | S04 confirmed |
| `tests/unit/test_test_health_service.py` (S03) | ✅ | S04 confirmed |

All five named test files present. No missing entries.

### ✅ TDD RED evidence: plausible and behaviour-pinning

S05 report documents two RED failures:

```python
# Panel: 4 <svg> tags test failed (delta arrow SVGs counted too)
tests/dashboard/test_test_health_panel.py::TestTestHealthPanel::test_panel_renders_with_snapshots
AssertionError: Expected 4 sparkline SVGs, got 8  ← initial assertion expected 4 <svg> tags

# Aggregator: job type not yet in union
tests/integration/test_jobs_aggregator_test_health.py::TestJobsAggregatorTestHealth::test_capture_appears_in_jobs_view
AssertionError: Expected 'test-health-capture' in ['batch_execution', ...]  ← before aggregator was extended
```

Both are genuine `AssertionError` snippets from behavioural tests, not ImportError or collection errors. **TDD RED evidence: PASS.**

**NOTE**: `tests/unit/test_test_health_sparkline.py` has no documented RED snippet in the S05 report. The tests were written before the helper existed (confirmed in report text), but the exact failure snippet is not recorded. This is a MEDIUM-gap: if the sparkline helper had subtle bugs, the RED state would not be reconstructable from the report. However, `test_sparkline_ascending_values` is behaviour-pinning (would fail if Y-coords were inverted), so the test itself is sound. No fix required — documentation gap only.

### ✅ Mutation-test heuristic: spot-check

`test_sparkline_ascending_values`: if the SVG y-coordinate calculation (`y = pad_y + (1 - (v - min_v) / range_v) * chart_h`) were reversed, the test would fail immediately. **Behaviour-pinning: YES.**

`test_panel_empty_state_per_metric`: if the template rendered an empty `<svg>` instead of the "no data yet" text, the test would fail on `html.count("no data yet") == 3`. **Behaviour-pinning: YES.**

---

## 6. Pre-flight Page Sanity

### ✅ All fragment ID references resolve in rendered HTML

`test_health_panel.html` has no `hx-target`, `hx-include`, `aria-controls`, `aria-labelledby`, `for`, or `href` references. The page templates (`tests.html`, `quality.html`) use:
- `id="test-health-panel"` (line 43/41 in each) — target of the htmx fragment load
- `id="tab-content"` (referenced in page scripts) — SSE reload target
- `id="confirm-dialog"` and `id="log-modal"` — existing modal containers

All IDs are present in the rendered page. No dangling references. **No pre-flight findings.**

### ✅ htmx mount block URL correct

Both pages mount the fragment via:
```html
<div id="test-health-panel"
     hx-get="/project/{{ current_project.id }}/test-health"
     hx-trigger="load"
     hx-swap="innerHTML">
```
The `project_id` is the database PK (not slug), matching the router's `project_id: str` path parameter. `get_project_or_404()` accepts both. URL convention is consistent with existing fragment routes (`/project/{project_id}/tests/fragment/...`).

---

## Test Verification (NON-NEGOTIABLE)

```
uv run pytest tests/dashboard/test_test_health_panel.py tests/unit/test_test_health_sparkline.py tests/integration/test_jobs_aggregator_test_health.py -v
```

```
13 passed, 0 failed, 8 warnings (SAWarning — testcontainer session-in-transaction,
                                 not code-related, pre-existing)
```

**Result: PASS**

---

## Findings

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| 1 | MEDIUM | documentation | `tests/unit/test_test_health_sparkline.py` has no RED snippet in the S05 report. Tests were written pre-implementation (confirmed in report text), but the exact `AssertionError` snippet is undocumented. No code fix required. |

---

## Verdict

```
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00086",
  "step_reviewed": "S05",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM",
      "category": "conventions",
      "description": "tests/unit/test_test_health_sparkline.py RED snippet not documented in S05 report. Tests are behaviour-pinning and correct. No code fix required.",
      "fixable": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "13 passed, 0 failed",
  "notes": "All critical architecture checks PASS. No copy-paste duplication between routers. Jobs aggregator follows SQLAlchemy union pattern. Jinja2 %-style format filters used throughout. Empty-state tests assert text placeholder, not hollow SVG. Sparkline Y-axis inversion test confirms decreasing coords for ascending values. TDD RED evidence documented for 2/3 new test files (sparkline unit test docs gap). No security issues. Pre-flight ID reference check clean."
}
```
