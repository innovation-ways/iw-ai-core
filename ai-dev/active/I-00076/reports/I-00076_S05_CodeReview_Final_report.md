# I-00076 S05 Code Review — Final Cross-Agent Review

**Reviewer**: `code-review-final-impl`
**Step reviewed**: S01..S04 (frontend-impl → code-review-impl → tests-impl → code-review-impl)
**Work item**: I-00076
**Date**: 2026-05-10

---

## Summary

The fix is a single Jinja2 template hunk in `item_overview.html` plus 5 regression tests in `tests/dashboard/test_runtime_override_templates.py`. Both files are clean, minimal, and correctly scoped. No Python files were modified, no migrations generated, and no Tailwind classes touched. Pre-flight gates pass.

**Verdict: approve** — no CRITICAL or HIGH findings.

---

## Pre-flight

| Gate | Result |
|------|--------|
| `make format` | ok — 661 files already formatted |
| `make lint` | ok — All checks passed |
| `uv run pytest tests/dashboard/test_runtime_override_templates.py` | **15 passed** (5 new I-00076 + 10 pre-existing) |

Coverage threshold failure (18.88% vs 46% required) is pre-existing, unchanged from S01.

---

## Changed Files

Only two files changed relative to `main`:

| File | Change | Lines |
|------|--------|-------|
| `dashboard/templates/fragments/item_overview.html` | Replaced self-disabling `onchange` with `hx-disabled-elt="this"` + explanatory Jinja comment | +9/−2 |
| `tests/dashboard/test_runtime_override_templates.py` | Added 5 I-00076 regression tests (3 classes) | +219 |

---

## Checklist 1 — Completeness vs Design Document

### AC1: Bug is fixed (markup change + persistence test)

- ✅ **Template**: the editable-step `<select>` (lines 77–93) carries `hx-disabled-elt="this"` and no `onchange`.
- ✅ **Template**: a clarifying Jinja comment (lines 78–82) explains why the control must not self-disable.
- ✅ **Test** `test_i00076_patch_step_override_persists_chosen_option`: PATCH with `option_id="5"` → 204 → `step.agent_runtime_option_id == 5`. Verifies the full persistence path.
- ✅ **Test** `test_i00076_resolve_runtime_step_override_wins`: resolves to `cli_tool="claude"`, `model="claude-opus-4-7"` — the specific option, not just "a value was returned."

### AC2: Regression test exists (template-render test pins corrected markup)

- ✅ **Test** `test_i00076_editable_step_select_uses_hx_disabled_elt`: asserts `'hx-disabled-elt="this"'` present, and `this.disabled=true`, `this.disabled = true`, `htmx.trigger(this` all absent. Attribute-anchored, not bare-token.
- ✅ **Test** `test_i00076_failed_step_select_also_uses_hx_disabled_elt`: same checks for a `failed` step.
- ✅ Both would fail against pre-fix HTML (which had `this.disabled=true` and no `hx-disabled-elt`).

### AC3: No regression to the "inherit" path

- ✅ **Test** `test_i00076_patch_step_override_clears_on_empty_body`: pre-sets `agent_runtime_option_id = 3`, PATCH with `{"option_id": ""}` → `204`, then asserts `step.agent_runtime_option_id is None`.

---

## Checklist 2 — Cross-Step Consistency

### Template ↔ tests string alignment

| Assertion in test | What S01 wrote | Consistent? |
|---|---|---|
| `'hx-disabled-elt="this"' in html` | `hx-disabled-elt="this"` at line 87 | ✅ |
| `"this.disabled=true" not in html` | No `this.disabled` in template | ✅ |
| `"htmx.trigger(this" not in html` | No `htmx.trigger` in template | ✅ |

### Persistence test uses a real, enabled option

- ✅ Option id=5 (`cli_tool="claude"`, `model="claude-opus-4-7"`) is seeded by `_seed_runtime_options` and verified to be enabled before the PATCH call.
- ✅ The resolver test sets `step.agent_runtime_option_id = 5` (matching the seeded row) and asserts the exact `(cli_tool, model)` pair.

---

## Checklist 3 — Scope / Minimality

- ✅ **Only two files changed**: `item_overview.html` + `test_runtime_override_templates.py`.
- ✅ **`w-24` unchanged** — not `w-48`.
- ✅ **`{{ opt.cli_label }}` unchanged** — not `display_name`.
- ✅ **No Python files under `orch/` or `dashboard/routers/` changed.**
- ⚠️ **`step_pipeline.html` also has a diff** (format string change + trailing newline). This is a **pre-existing, unrelated cleanup** from I-00075 fix cycles — present in this worktree but not part of I-00076's scope. **Not a blocker**: it does not affect I-00076's correctness and will merge normally via the branch's normal history.

---

## Checklist 4 — Behavioural Soundness

### Request flow with the fix

1. User selects an option → `change` event fires (native `<select>` behaviour).
2. htmx computes the request: `shouldInclude()` sees the `<select>` is **not yet disabled** → `option_id=<chosen>` is in the form body.
3. htmx sends `PATCH /project/…/runtime-override` with `option_id=<chosen>`.
4. Server validates, writes `workflow_steps.agent_runtime_option_id = <chosen>`, emits one `runtime_override_changed` event.
5. htmx disables the element (visual feedback, after serialization).
6. htmx re-enables on completion.

**No path where `option_id` is dropped.** `hx-disabled-elt` disables *after* serialization, unlike `this.disabled=true` which disabled *before*.

### Inherit path (empty `option_id`)

`<option value="">— inherit —</option>` serializes as `option_id=` → server receives `option_id=""` → `_validate_option_id(db, "") → None` → `step.agent_runtime_option_id = None` → resolver cascade falls through to project default. AC3 is covered.

### No console-error risk

No inline JS was added. The old inline JS (`onchange`, `htmx.trigger`) was removed. No `navigator.clipboard` introduced.

---

## Out-of-Scope Observation (not a finding)

`dashboard/templates/components/step_pipeline.html` shows a diff (`%d/%s` → `{}` format + trailing newline). This is a pre-existing cleanup from I-00075 fix cycles that happens to be in this worktree's state. It does not touch I-00076's scope or any shared code path.

---

## Findings

| Severity | Category | Location | Description | Recommendation |
|----------|----------|----------|-------------|----------------|
| — | — | — | **No CRITICAL or HIGH findings.** | — |

---

## Verdict

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00076",
  "review_target": "S01..S04",
  "verdict": "approve",
  "mandatory_fix_count": 0,
  "findings": [],
  "preflight": {"format": "ok", "lint": "ok"},
  "notes": "Clean, minimal fix. Single template hunk replaces a self-disabling onchange that was silently dropping option_id with htmx's purpose-built hx-disabled-elt. Five regression tests pin the corrected markup (pending and failed step selects), the persistence path (option_id=5 persists), the inherit path (empty option_id clears), and the resolver cascade (step override wins over project default). All acceptance criteria are covered. No out-of-scope changes except a pre-existing step_pipeline.html cleanup from I-00075 that is unrelated to this work item."
}
```