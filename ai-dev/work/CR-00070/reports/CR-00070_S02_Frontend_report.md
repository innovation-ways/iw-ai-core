# CR-00070 S02 Frontend Implementation Report

## Summary

Frontend implementation complete for **CR-00070 S02**: "Show Resolved Agent + Model Instead of 'Inherit' in Step Runtime Dropdowns".

The `inherited_runtime_label` context variable (computed by S01) is now consumed in `item_steps_table.html` to relabel the empty options from `— inherit —` to `{display_name} (inherited)` in both per-step and bulk `<select>` dropdowns, with a graceful fallback when no option resolves.

## What Was Done

### 1. Template changes — `dashboard/templates/fragments/item_steps_table.html`

**Per-step `<select>` empty option (line ~74)**:
```jinja2
{# Before #}
<option value="">— inherit —</option>

{# After #}
<option value="">{% if inherited_runtime_label %}{{ inherited_runtime_label }} (inherited){% else %}— inherit —{% endif %}</option>
```

**Bulk "Apply to remaining steps" `<select>` empty option (line ~244)**:
```jinja2
{# Before #}
<option value="">— inherit —</option>

{# After #}
<option value="">{% if inherited_runtime_label %}{{ inherited_runtime_label }} (inherited){% else %}— inherit —{% endif %}</option>
```

**Bulk non-empty option labels (line ~248)**:
```jinja2
{# Before #}
<option value="{{ opt.id }}">{{ opt.cli_label }} / {{ opt.model_label }}</option>

{# After #}
<option value="{{ opt.id }}">{{ opt.display_name }}</option>
```

The `value=""` attributes, htmx attributes, and non-empty per-step option labels are unchanged.

### 2. Tests — `tests/dashboard/test_runtime_override_templates.py`

Added `TestInheritedRuntimeLabel` class with 6 tests covering all ACs:

| Test | AC | What it asserts |
|------|----|-----------------|
| `test_per_step_empty_option_shows_inherited_suffix` | AC1 | Per-step `<select>` empty option shows `(inherited)` suffix; no `— inherit —` |
| `test_bulk_empty_option_shows_inherited_suffix` | AC2 | Bulk "Apply to remaining steps" empty option shows `(inherited)` |
| `test_bulk_non_empty_options_use_display_name` | AC2 | Bulk non-empty options use `display_name`; old `cli_label / model_label` format absent |
| `test_none_inherited_label_falls_back_to_neutral_inherit` | AC5 | Empty catalogue → steps table renders (no 500); fallback to `— inherit —` |
| `test_item_override_reflected_in_inherited_label` | AC3 | Item-level override changes the inherited label to that option's `display_name` |
| `test_all_three_render_paths_show_inherited_suffix` | AC6 | All three render paths (item_detail, tab/overview, PATCH fragment) show `(inherited)` |

## TDD Evidence (RED phase)

The RED run output (before template changes) was:

```
tests/dashboard/test_runtime_override_templates.py::TestInheritedRuntimeLabel::test_per_step_empty_option_shows_inherited_suffix FAILED
tests/dashboard/test_runtime_override_templates.py::TestInheritedRuntimeLabel::test_bulk_empty_option_shows_inherited_suffix FAILED
tests/dashboard/test_runtime_override_templates.py::TestInheritedRuntimeLabel::test_bulk_non_empty_options_use_display_name FAILED
tests/dashboard/test_runtime_override_templates.py::TestInheritedRuntimeLabel::test_none_inherited_label_falls_back_to_neutral_inherit FAILED
tests/dashboard/test_runtime_override_templates.py::TestInheritedRuntimeLabel::test_item_override_reflected_in_inherited_label FAILED

AssertionError: Per-step empty option must show '(inherited)' suffix when a runtime resolves
AssertionError: '— inherit —' must not appear when inherited_runtime_label resolves
[and similar for bulk dropdown tests]
```

After template edits: all 6 tests pass. Full file: 21 passed, 0 failed.

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/item_steps_table.html` | 3 option-label changes (per-step empty, bulk empty, bulk non-empty) |
| `tests/dashboard/test_runtime_override_templates.py` | New `TestInheritedRuntimeLabel` class — 6 tests |

## Test Results

```
21 passed in ~12s (targeted run, no coverage)
0 failed
```

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | ✅ 827 files already formatted |
| `make lint` | ✅ All checks passed (ruff + check_templates.py) |
| `make typecheck` | ✅ Success: no issues in 273 source files |

## Acceptance Criteria Coverage

| AC | Covered By | Status |
|----|-----------|--------|
| AC1: Per-step `<select>` shows `{display_name} (inherited)` | `test_per_step_empty_option_shows_inherited_suffix` | ✅ |
| AC2: Bulk `<select>` empty option + non-empty uses `display_name` | `test_bulk_empty_option_shows_inherited_suffix` + `test_bulk_non_empty_options_use_display_name` | ✅ |
| AC3: Item-level override reflected in inherited label | `test_item_override_reflected_in_inherited_label` | ✅ |
| AC4: Inherit mechanism unchanged (implicit — no test needed, unchanged value="") | Template audit | ✅ |
| AC5: Graceful fallback when no option resolves | `test_none_inherited_label_falls_back_to_neutral_inherit` | ✅ |
| AC6: All three render paths show `(inherited)` | `test_all_three_render_paths_show_inherited_suffix` | ✅ |

## Notes

- The Jinja2 conditional `{% if inherited_runtime_label %}...{% else %}— inherit —{% endif %}` is the fallback for AC5 — when `inherited_runtime_label` is `None`, the neutral label renders, avoiding `None (inherited)` with an empty model name.
- `inherited_runtime_label` is `None` only when the catalogue has no enabled rows — a rare state, but the fallback ensures the steps table always renders.
- No CSS changes were required — this is a text-label change only.