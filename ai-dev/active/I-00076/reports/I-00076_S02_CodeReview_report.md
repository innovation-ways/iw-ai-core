# I-00076 S02 Code Review — Frontend (S01)

## Review Summary

S01 applied the correct fix to the per-step CLI/runtime override `<select>` in `item_overview.html`. The self-disabling `onchange` handler that was breaking htmx form serialization has been replaced with `hx-disabled-elt="this"`. All acceptance criteria from the design doc are met.

---

## Pre-flight Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ ok — 661 files already formatted |
| `make lint` | ✅ ok — All checks passed |

---

## Diff Analysis

**File changed**: `dashboard/templates/fragments/item_overview.html`

```diff
-                onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');">
+              {# Do NOT disable this <select> in an onchange handler — htmx omits disabled
+                 form controls from the request body (shouldInclude), which drops option_id
+                 and clears the override instead of setting it. Use hx-disabled-elt so htmx
+                 disables it only after serialising the value. A <select> already triggers
+                 htmx on `change` by default — no explicit htmx.trigger needed. #}
               <select
                 class="text-xs border border-border rounded bg-background text-foreground px-1 py-0.5 cursor-pointer w-24"
                 hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
                 hx-swap="none"
-                name="option_id"
-                onchange="…">
+                hx-disabled-elt="this"
+                name="option_id">
```

**Second file changed**: `tests/dashboard/test_runtime_override_templates.py` (219 lines added)

---

## Checklist

### 1. Correctness Against Design Contract

| Criterion | Status | Notes |
|-----------|--------|-------|
| No `this.disabled` on the `<select>` | ✅ | Removed |
| No `htmx.trigger(` anywhere near the `<select>` | ✅ | Removed |
| `hx-disabled-elt="this"` present on `<select>` | ✅ | Added at line 87 |
| `hx-patch` endpoint preserved | ✅ | Unchanged |
| `hx-swap="none"` preserved | ✅ | Unchanged |
| `name="option_id"` preserved | ✅ | Unchanged |
| `<option value="">— inherit —</option>` preserved | ✅ | Unchanged |
| `{% for opt in runtime_options %}` loop preserved | ✅ | Unchanged |
| Comment explaining non-self-disabling behaviour | ✅ | Jinja comment above `<select>` (lines 78–82) |

### 2. Minimality / Scope

| Criterion | Status | Notes |
|-----------|--------|-------|
| `w-24` class unchanged (NOT `w-48`) | ✅ | `w-24` still present |
| `opt.cli_label` unchanged (NOT `opt.display_name`) | ✅ | `cli_label` still used |
| `dashboard/routers/runtime_overrides.py` untouched | ✅ | No changes |
| `orch/agent_runtime/resolver.py` untouched | ✅ | No changes |
| No other template elements changed | ✅ | Only the editable-step `<select>` |
| No new Tailwind classes added | ✅ | `make css` not required |

### 3. Template Hygiene

| Criterion | Status | Notes |
|-----------|--------|-------|
| Fragment does not extend `base.html` | ✅ | Confirmed (fragment file) |
| htmx attribute spelled correctly (`hx-disabled-elt`) | ✅ | Correct |
| Indentation matches surrounding code | ✅ | 16-space indent, correct |
| Jinja comment uses `{# … #}` syntax | ✅ | Correct |

### 4. Behavioural Reasoning

The htmx flow for a user selecting an option:

1. User picks option → `change` event fires (default behaviour for `<select>`)
2. htmx serialises `{option_id: <value>}` — element is **not yet disabled**, so `shouldInclude()` includes it ✅
3. htmx adds `disabled` attribute to `<select>` ✅
4. PATCH sent to `/project/{p}/api/item/{iid}/step/{sid}/runtime-override` with `option_id` in body ✅
5. Server validates, persists `workflow_steps.agent_runtime_option_id = <value>`, emits one `runtime_override_changed` event ✅
6. htmx re-enables `<select>` on completion ✅

No scenario exists where the value is dropped post-fix. The fix is correct and complete.

---

## Test Results

```
tests/dashboard/test_runtime_override_templates.py::TestI00076EditableStepSelect
  test_i00076_editable_step_select_uses_hx_disabled_elt          ✅ PASSED
  test_i00076_failed_step_select_also_uses_hx_disabled_elt      ✅ PASSED

tests/dashboard/test_runtime_override_templates.py::TestI00076PatchStepOverride
  test_i00076_patch_step_override_persists_chosen_option         ✅ PASSED
  test_i00076_patch_step_override_clears_on_empty_body          ✅ PASSED

tests/dashboard/test_runtime_override_templates.py::TestI00076ResolveRuntime
  test_i00076_resolve_runtime_step_override_wins                ✅ PASSED

5 passed, 1 warning in 22.99s
```

Coverage warning (46% threshold vs 18.53% actual) is **pre-existing** and unrelated to this template edit.

---

## Findings

No CRITICAL or HIGH findings. Zero issues.

---

## Verdict

**Approve** — S01 is correct, minimal, well-commented, and fully covered by regression tests.

