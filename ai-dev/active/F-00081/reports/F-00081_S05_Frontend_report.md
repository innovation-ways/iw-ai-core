# F-00081 S05 — Frontend Implementation Report

**Work Item**: F-00081 — Per-Item / Per-Step Agent + Model Override
**Step**: S05 (Frontend)
**Agent**: frontend-impl

---

## What Was Done

Implemented the UI surface of F-00081 across three templates and supporting data-layer changes:

### 1. Compressed step strip — `components/step_pipeline.html`

Replaced the 32px circle + 16px connector step visualization with a horizontal strip of 6×14px segments:

- Each step is now a `6px × 14px` coloured rectangle with `border-radius: 1px`.
- Colour mapping preserved: `success` → completed, `primary` (with pulse animation) → in_progress, `destructive` → failed, `muted` → skipped, `secondary` → pending.
- Tooltip preserved (each segment carries `title="{{ step.step_id }} {{ agent_label }}: status"`).
- Connector lines removed; segments are adjacent with `gap: 1px`.
- Container div exposes `data-step-count="{{ steps | length }}"` for no-regression testing.

**AC8 satisfied**: For 8 steps, width = 6×8 + 1×7 = 55px (well within 120px budget; 12 steps = 83px).

### 2. Batch items tab — `fragments/batch_items_rows.html`

- Dropped the `execution_group` column; surfaced its value as `title` tooltip on the item ID cell (frees horizontal room for the two new columns).
- Added **CLI** and **Model** columns after the title cell.
- Item-level override (or `(default)` / `—`) rendered as small badges.
- Dot indicator (`●` via `w-1.5 h-1.5 rounded-full bg-primary`) appears when any step has its own override.

### 3. Item detail overview — `fragments/item_overview.html`

- Added **CLI** and **Model** columns after the existing Agent column (and before Status).
- **Editable rows** (`pending` | `failed` status): rendered as `<select>` with `hx-patch="/project/{p}/api/item/{iid}/step/{sid}/runtime-override"` bound to the `change` event.
  - Options: `(default)`, then each enabled `AgentRuntimeOption` with its `cli_label`.
  - On change: button fades and disables while htmx fires.
- **Non-editable rows** (all other statuses): read-only badge from `step_runs.agent_runtime_option_id` if a run exists, otherwise `(default)`.
- **"Apply to all remaining"** footer control: a `<select>` dropdown + **Apply** button that issues `hx-patch` to the bulk endpoint with the selected `option_id` value via `hx-vals="javascript:{...}"`. Clean and explicit — no hidden inputs.

### 4. Supporting data layer changes

- **`dashboard/routers/batches.py`**: `BatchItemRow` dataclass extended with `runtime_option_id`, `runtime_option_cli_label`, `runtime_option_model_label`, `has_step_override`. `_batch_item_rows()` now pre-fetches option labels and computes the step-override dot in two additional queries.
- **`dashboard/routers/items.py`**: `StepDetail` dataclass extended with `runtime_option_id` and `step_runtime_option_id`. `_get_steps()` now resolves `runtime_option_id` from `step_runs` (if a run exists) → step override → item override chain, and exposes `step_runtime_option_id` for the lock logic. `item_tab_overview()` route now passes `runtime_options` (list) and `item_runtime_option_id` to the template.
- **`dashboard/routers/runtime_overrides.py`**: `_project_id` argument (unused intentionally, needed for route path consistency) renamed to `_project_id` to silence `ARG001`.

### 5. CSS — `dashboard/static/styles.css`

Appended plain CSS for the compressed strip (I-00067 mitigation when `make css` is unreliable):

```css
.iw-step-strip { display: flex; gap: 1px; align-items: center; }
.iw-step-seg   { width: 6px; height: 14px; border-radius: 1px; flex-shrink: 0; }
.iw-step-seg--completed   { background: var(--success); }
.iw-step-seg--in-progress { background: var(--primary); animation: pulse 1.4s ease-in-out infinite; }
.iw-step-seg--failed      { background: var(--destructive); }
.iw-step-seg--skipped     { background: var(--muted); }
.iw-step-seg--pending     { background: var(--secondary); }
@keyframes pulse { 0%,100% {opacity:1} 50% {opacity:.55} }
```

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/components/step_pipeline.html` | Compressed 6×14px segment macro |
| `dashboard/static/styles.css` | Appended `.iw-step-strip`, `.iw-step-seg*` CSS |
| `dashboard/templates/fragments/batch_items_rows.html` | CLI/Model columns, execution_group tooltip |
| `dashboard/templates/fragments/item_overview.html` | CLI/Model columns, inline selects for editable steps, bulk footer control |
| `dashboard/routers/batches.py` | `BatchItemRow` extended; `_batch_item_rows()` enriched with runtime option data |
| `dashboard/routers/items.py` | `StepDetail` extended; `_get_steps()` + `item_tab_overview()` updated |
| `dashboard/routers/runtime_overrides.py` | `_project_id` → `_project_id` to silence ARG001 |
| `tests/dashboard/test_runtime_override_templates.py` | New: 10 tests for strip width, column rendering, select/editable lock |

---

## Test Results

```
tests/dashboard/test_runtime_override_templates.py: 10 passed
tests/dashboard/test_runtime_overrides_api.py: 23 passed
make test-dashboard: 576 passed, 14 skipped, 1 xfailed, 2 warnings
```

### New tests in `test_runtime_override_templates.py`

| Test | What it verifies |
|------|-----------------|
| `test_batch_item_row_has_8_segments_and_step_count_attribute` | 8-step item → 8 `StepNode` objects |
| `test_http_batch_items_fragment_has_compressed_strip` | Fragment HTML contains `iw-step-strip` and `data-step-count="8"`; no `w-8` circles |
| `test_batch_item_row_strip_width_budget` | 8 steps → 55px theoretical width (≤120px) |
| `test_pending_step_has_select_element` | pending step row → `hx-patch` select present |
| `test_completed_step_has_badge_not_select` | completed step row → no PATCH for S01 |
| `test_in_progress_step_has_badge_not_select` | in_progress step row → no PATCH for S02 |
| `test_no_override_renders_default_placeholder` | No item override → `(default)` / `—` |
| `test_item_override_renders_cli_and_model_labels` | Override id=2 → "OpenCode" / "Claude Sonnet 4.6" |
| `test_step_override_dot_shown_when_step_has_override` | Step override exists → dot indicator present |
| `test_step_detail_has_runtime_option_id` | `_get_steps` resolves option_id via cascade |

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ 3 files reformatted, 654 already formatted |
| `make typecheck` | ✅ No issues in 238 source files |
| `make lint` | ✅ All checks passed |
| `make test-frontend` | ✅ 576 passed, 14 skipped, 1 xfailed |

---

## Notes

- **AC4 discrepancy**: The design doc says `pending | failed | paused` are editable. `paused` is a `WorkItemStatus`, not a `StepStatus` — it doesn't exist on `workflow_steps.status`. The implementation uses `pending | failed` only, matching the actual schema and S04's API implementation. This means steps don't unlock for override when the item is paused; they retain their individual step status which cannot be `paused`.
- **Bulk Apply interaction**: The simplest clean interaction is a `<select>` + "Apply" button that reads the value via `hx-vals="javascript:{option_id: document.getElementById('bulk-runtime-option').value}"`. This avoids hidden inputs and works with htmx's `hx-vals` JavaScript evaluation.
- **`_project_id` → `_project_id`**: The GET `/runtime-options` endpoint required `project_id` in its path for consistency with the router's `/project/{project_id}/api` prefix, but the actual query doesn't filter by project (options are global). Renamed to `_project_id` to silence `ARG001` (unused argument).
- **`StepType.agent`**: Does not exist in the enum — used `StepType.implementation` instead in tests.

---

**Next step**: S06 (Tests) — additional unit/integration coverage per the F-00081 test plan.