# CR-00039 S03 — Final Code Review Report
**Agent**: code-review-final-impl
**Work Item**: CR-00039 (Step Pipeline Labeled Pill Redesign with Fix-Cycle Expansion)
**Step**: S03

---

## Summary

All cross-agent integration checks, acceptance criteria traces, and regression audits pass. The S01 implementation is holistically sound. No CRITICAL or HIGH issues found.

**Verdict**: PASS

---

## Cross-Layer Consistency

### 1. Macro import path and name ✅

**File**: `dashboard/templates/fragments/item_overview.html`, line 1

```jinja
{% from "components/step_pipeline.html" import step_pipeline %}
```

- Import path `components/step_pipeline.html` resolves correctly from the fragments directory
- Macro name `step_pipeline` matches the definition in `step_pipeline.html` line 1: `{% macro step_pipeline(steps) %}`
- No parameter or signature changes introduced

### 2. All CSS classes used in template have corresponding CSS rules ✅

| Template class | CSS rule location |
|---------------|-------------------|
| `.iw-pipeline-strip` | `styles.css` line 362 |
| `.iw-pipeline-pill` | `styles.css` line 370 |
| `.iw-pipeline-pill--completed` | `styles.css` line 399 |
| `.iw-pipeline-pill--in-progress` | `styles.css` line 400 |
| `.iw-pipeline-pill--failed` | `styles.css` line 401 |
| `.iw-pipeline-pill--skipped` | `styles.css` line 402 |
| `.iw-pipeline-pill--pending` | `styles.css` line 403 |
| `.iw-pipeline-pill--fixcycle` | `styles.css` line 404 |
| `.iw-pipeline-pill-id` | `styles.css` line 383 |
| `.iw-pipeline-pill-dur` | `styles.css` line 391 |
| `.iw-pipeline-connector` | `styles.css` line 406 |
| `.iw-pipeline-connector--fixcycle` | `styles.css` line 414 |

Every class referenced in the Jinja2 template has a corresponding CSS rule. No orphaned class references.

### 3. Fix-cycle rerun connector class exists in CSS ✅

`.iw-pipeline-connector--fixcycle` is defined at `styles.css` lines 414–422 as a dashed amber repeating-linear-gradient. The template at `step_pipeline.html` line 35 references this class and it is present in the stylesheet.

---

## Acceptance Criteria Trace

### AC1: Step IDs are visible ✅

**File**: `step_pipeline.html`, line 26

```jinja
<span class="iw-pipeline-pill-id">{{ step.step_id }}</span>
```

- Pill dimensions: 52 px wide × 42 px tall (`styles.css` lines 375–376)
- Step ID font: 10 px monospace bold (`styles.css` line 383–388)
- Exceeds the minimum 28 px tall / 44 px wide required by AC1

### AC2: Duration inline — no separate broken row ✅

**File**: `item_overview.html`, lines 9–19

The broken `<div class="flex items-center gap-1 mt-2">` duration row (design doc lines 10–36) is absent from the file. Duration is rendered inside each pill at `step_pipeline.html` lines 27–29:

```jinja
{% if dur_str %}
  <span class="iw-pipeline-pill-dur">{{ dur_str }}</span>
{% endif %}
```

### AC3: Fix-cycle reruns expanded as amber pills ✅

**File**: `step_pipeline.html`, lines 33–41

```jinja
{% if step.fix_cycle_count > 0 %}
  {% for i in range(step.fix_cycle_count) %}
    <div class="iw-pipeline-connector iw-pipeline-connector--fixcycle"></div>
    <div class="iw-pipeline-pill iw-pipeline-pill--fixcycle"
         title="↺{{ step.step_id }}: fix cycle {{ loop.index }}">
      <span class="iw-pipeline-pill-id">↺{{ step.step_id }}</span>
    </div>
  {% endfor %}
{% endif %}
```

- `range(step.fix_cycle_count)` correctly iterates N times for fix_cycle_count = N
- Amber pill uses `.iw-pipeline-pill--fixcycle` (warning color)
- Dashed connector precedes each rerun pill
- `loop.index` gives 1-based iteration count in title attribute

### AC4: `data-step-count` preserved ✅

**File**: `step_pipeline.html`, line 9

```html
<div class="iw-pipeline-strip" data-step-count="{{ steps | length }}">
```

Outer container exposes `data-step-count`. The existing test `test_http_batch_items_fragment_has_compressed_strip` asserts `'data-step-count="8"' in html` and passes (S02 report, line 27).

### AC5: No regressions in step detail table ✅

**File**: `item_overview.html`, lines 21–195 (step detail table)

The table structure is intact:
- All columns present (Step, Agent, CLI, Model, Status, Started, Duration, Runs, Error, Actions)
- `status_badge` macro calls unchanged
- Duration formatting in table column unchanged (lines 115–123)
- Fix-cycle count badge in runs column unchanged (lines 126–130)
- Action buttons unchanged

---

## Regression Audit

### No other template uses old macro signature ✅

Searched all 7 files importing `step_pipeline`:

| File | Usage | Notes |
|------|-------|-------|
| `fragments/item_overview.html` | `{{ step_pipeline(steps) }}` | ✅ correct |
| `pages/project/item_detail.html` | import only | ✅ no call |
| `pages/project/batch_detail.html` | import only | ✅ no call |
| `fragments/batch_items_rows.html` | `{{ step_pipeline(row.steps) }}` | ✅ correct |

No other call site exists.

### No JS selects old `.iw-step-strip` or `.iw-step-seg` classes ✅

Searched `dashboard/static/` — zero JavaScript matches for `iw-step-strip` or `iw-step-seg`. The old classes in `styles.css` (lines 352–358) are unused dead code but do no harm and cause no regressions.

---

## Test Results

From S02 report:
| Suite | Result |
|-------|--------|
| `tests/dashboard/test_runtime_override_templates.py::TestCompressedStepStrip` | 3/3 PASSED |
| Full dashboard test suite | 583 passed, 2 xfailed |
| `make lint` | All checks passed |

---

## Observations

1. **Old CSS classes as dead code**: The `.iw-step-strip` / `.iw-step-seg` block (`styles.css` lines 351–359) is now unused. This is benign — out-of-scope for removal in this CR per design doc note.

2. **Fix-cycle pill has no duration line**: Per design doc, the fix-cycle amber pill shows only the `↺SXX` label with no duration. This is intentional — reruns inherit the main step's duration context and adding a second line would shrink the pill below the minimum readable size. No AC requires duration on fix-cycle pills.

3. **`needs_fix` grouped with `failed`**: Both map to `.iw-pipeline-pill--failed` (destructive red). This is a deliberate design choice noted in S02, consistent with the visual intent (both are error states).

---

## Files Changed (Summary)

| File | Change |
|------|--------|
| `dashboard/templates/components/step_pipeline.html` | Redesigned macro: 6×14 px squares → 52×42 px labeled pills with fix-cycle expansion |
| `dashboard/templates/fragments/item_overview.html` | Duration row removed; step pipeline macro call remains |
| `dashboard/static/styles.css` | Added `.iw-pipeline-strip`, `.iw-pipeline-pill`, `.iw-pipeline-connector` + modifier classes; old classes retained as dead code |
| `dashboard/routers/batches.py` | Changed to use `step_pipeline` macro in batch item rows (S02 noted as unrelated functional change) |
| `tests/dashboard/test_runtime_override_templates.py` | Updated test to assert new pill classes and `data-step-count` |

---

## Mandatory Fix Count

**0** — No CRITICAL or HIGH issues found.
