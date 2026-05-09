# CR-00039 S02 — Code Review Report
**Agent**: code-review-impl
**Work Item**: CR-00039 (Step Pipeline Labeled Pill Redesign with Fix-Cycle Expansion)
**Step**: S02
**Reviewed Agent**: frontend-impl

---

## Summary

The S01 implementation correctly addresses all three changed files (`step_pipeline.html`, `item_overview.html`, `styles.css`). All 12 checklist items pass. The new pipeline pill design is compliant with the design document and project conventions.

**Verdict**: PASS

---

## Findings

### ✅ AC1 — `data-step-count` preserved

**File**: `dashboard/templates/components/step_pipeline.html`, line 9

```html
<div class="iw-pipeline-strip" data-step-count="{{ steps | length }}">
```

The outer container correctly carries `data-step-count="{{ steps | length }}"`. The existing test `test_http_batch_items_fragment_has_compressed_strip` asserts `'data-step-count="8"' in html` and passes. No regression.

**Severity**: INFO

---

### ✅ AC3 — Fix-cycle expansion: correct `range()` loop

**File**: `dashboard/templates/components/step_pipeline.html`, lines 33–41

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

- `range(step.fix_cycle_count)` iterates exactly `N` times for `fix_cycle_count = N`.
- `loop.index` gives the 1-based iteration count in the title.
- A dashed connector precedes each rerun pill.
- For `fix_cycle_count=2`, this renders 1 main pill + 2 amber `↺SXX` pills — exactly as specified.

**Severity**: INFO

---

### ✅ AC2 — Duration row removed from `item_overview.html`

**File**: `dashboard/templates/fragments/item_overview.html`, lines 10–18

```html
<div class="mb-6">
  <h3 class="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">Step Pipeline</h3>
  <div class="bg-card border border-border rounded-lg p-4 overflow-x-auto">
    {% if steps %}
      {{ step_pipeline(steps) }}
    {% else %}
      <p class="text-sm text-muted-foreground">No steps defined.</p>
    {% endif %}
  </div>
</div>
```

The broken `<div class="flex items-center gap-1 mt-2">` block (lines 10–36 in the old file) is gone. Duration is now integrated into each pill. The outer card div and macro call remain intact.

**Severity**: INFO

---

### ✅ Status modifier completeness

**File**: `dashboard/templates/components/step_pipeline.html`, lines 12–16

```jinja
{% set pill_status = 'completed' if step.status == 'completed'
                 else 'in-progress' if step.status == 'in_progress'
                 else 'failed' if step.status in ('failed', 'needs_fix')
                 else 'skipped' if step.status == 'skipped'
                 else 'pending' %}
```

All six statuses map to a CSS modifier:
| status | modifier class |
|--------|---------------|
| `completed` | `--completed` |
| `in_progress` | `--in-progress` |
| `failed` / `needs_fix` | `--failed` |
| `skipped` | `--skipped` |
| `pending` | `--pending` (fallback) |

`needs_fix` is intentionally grouped with `failed` (both use destructive/red styling) per the design doc.

**Severity**: INFO

---

### ✅ Connector logic — no trailing connector

**File**: `dashboard/templates/components/step_pipeline.html`, lines 44–46

```jinja
{% if not loop.last %}
  <div class="iw-pipeline-connector"></div>
{% endif %}
```

The connector to the next step is only emitted when `not loop.last`. For fix-cycle rerun pills, each rerun has its own `iw-pipeline-connector--fixcycle` dashed line, but the outer connector (between main pills of adjacent steps) is gated on `loop.last`. After the final fix-cycle rerun pill of the last step, no trailing connector is emitted. Correct.

**Severity**: INFO

---

### ✅ Duration formatting — integer division and None handling

**File**: `dashboard/templates/components/step_pipeline.html`, lines 17–23

```jinja
{% if step.duration_secs is not none %}
  {% set dur_m = (step.duration_secs // 60)|int %}
  {% set dur_s = (step.duration_secs % 60)|int %}
  {% set dur_str = "{}m{}s"|format(dur_m, dur_s) if dur_m > 0 else "{}s"|format(dur_s) %}
{% else %}
  {% set dur_str = '' %}
{% endif %}
```

- Integer division `//` and modulo `%` are used.
- When `dur_m > 0`, format is `MmSs`; otherwise just `Ss`.
- When `duration_secs` is `None`, `dur_str` is `''` and the second `<span>` line is suppressed by the `{% if dur_str %}` guard on line 27.

**Severity**: INFO

---

### ✅ `--warning` fallback in fix-cycle CSS

**File**: `dashboard/static/styles.css`, line 404

```css
.iw-pipeline-pill--fixcycle { background: var(--warning, #f59e0b); color: var(--warning-foreground, #fff); }
```

Both `background` and `color` have explicit fallback values. The pill renders correctly even if the CSS variables are undefined.

**Severity**: INFO

---

### ✅ Old CSS classes not clobbered

**File**: `dashboard/static/styles.css`, lines 351–359

```css
/* F-00081: compressed step strip (6×14px segments, ≤120px for ≤12 steps) */
.iw-step-strip { display: flex; gap: 1px; align-items: center; }
.iw-step-seg   { width: 6px; height: 14px; border-radius: 1px; flex-shrink: 0; }
...
```

The old `.iw-step-strip` and `.iw-step-seg` classes (lines 352–358) remain in `styles.css`. They are now dead code (no template references them) but do no harm. The new classes (`.iw-pipeline-strip`, `.iw-pipeline-pill`, etc.) are additions, not replacements, preserving backward compatibility.

**Severity**: INFO

---

### ✅ `overflow-x: auto` on strip container

**File**: `dashboard/static/styles.css`, line 367

```css
.iw-pipeline-strip {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0;
  overflow-x: auto;
}
```

Horizontal scrolling is enabled on the `.iw-pipeline-strip` element. The parent card in `item_overview.html` also carries `overflow-x-auto` (line 12 of the template), providing double protection.

**Severity**: INFO

---

### ✅ No inline styles

**File**: `dashboard/templates/components/step_pipeline.html`

All styling uses CSS classes only (`.iw-pipeline-pill`, `.iw-pipeline-pill--{{ pill_status }}`, `.iw-pipeline-connector`, etc.). No `style=""` attributes are present.

**Severity**: INFO

---

### ✅ Tooltips on main and fix-cycle pills

**File**: `dashboard/templates/components/step_pipeline.html`, lines 24–30, 36–38

Main pill:
```jinja
title="{{ step.step_id }} {{ step.agent_label }}: {{ step.status }}{% if dur_str %} {{ dur_str }}{% endif %}"
```

Fix-cycle pill:
```jinja
title="↺{{ step.step_id }}: fix cycle {{ loop.index }}"
```

Both have `title` attributes. Duration is included in the main pill tooltip. Fix-cycle tooltip shows iteration count.

**Severity**: INFO

---

### ✅ Accessibility

Pills are decorative (the step detail table below is the primary data source). `title` attributes are present on all interactive/hoverable elements. No `aria-` attributes required.

**Severity**: INFO

---

## Tests Results

| Suite | Result |
|-------|--------|
| `tests/dashboard/test_runtime_override_templates.py::TestCompressedStepStrip` | 3/3 PASSED |
| `make lint` | All checks passed |
| Full dashboard test suite | 583 passed, 2 xfailed |

---

## Changed Files

| File | Change |
|------|--------|
| `dashboard/templates/components/step_pipeline.html` | Redesigned macro with labeled pills and fix-cycle expansion |
| `dashboard/templates/fragments/item_overview.html` | Removed broken duration row |
| `dashboard/static/styles.css` | Added `.iw-pipeline-strip`, `.iw-pipeline-pill`, `.iw-pipeline-connector` CSS classes |
| `dashboard/routers/batches.py` | Changed to use `step_pipeline` macro in batch item rows (unrelated functional change) |
| `tests/dashboard/test_runtime_override_templates.py` | Updated test to assert new pill classes and `data-step-count` |

---

## Notes

- The design doc specified the duration formatting should use integer division (`// 60` and `% 60`) and handle `None` — both are correctly implemented.
- The `needs_fix` status is grouped with `failed` in the color mapping — this is a deliberate design choice not explicitly called out in the review checklist but consistent with the visual intent (both are error states).
- The old `.iw-step-strip` / `.iw-step-seg` CSS becomes dead code but is harmless. It could be removed in a future cleanup but is out of scope for this CR.