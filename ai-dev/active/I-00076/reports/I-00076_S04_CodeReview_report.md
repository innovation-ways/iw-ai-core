# I-00076 S04 Code Review Report — Tests (S03)

**Reviewer**: code-review-impl
**Step Reviewed**: S03 (tests-impl)
**Work Item**: I-00076
**Date**: 2026-05-10

---

## Summary

S03 wrote 5 new test cases covering template-render assertions, API persistence, and resolver integration. All tests pass. The pre-fix/pre-commit lint/format gate is clean. No critical or high findings.

---

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok — 661 files already formatted |
| `make lint` | ok — All checks passed |

---

## Files Changed

- `tests/dashboard/test_runtime_override_templates.py` — extended with 3 new test classes, 5 test methods
- `dashboard/templates/fragments/item_overview.html` — S01 fix (read-only for this review)

---

## Findings

### Checklist 1 — Reproduction test correctly targets the bug

**Template tests** (`test_i00076_editable_step_select_uses_hx_disabled_elt`, `test_i00076_failed_step_select_also_uses_hx_disabled_elt`):

- ✅ Asserts `'hx-disabled-elt="this"' in html` (positive — correct markup present)
- ✅ Asserts `"this.disabled=true" not in html` (negative — broken pattern absent)
- ✅ Asserts `"this.disabled = true" not in html` (negative — spaced variant absent)
- ✅ Asserts `"htmx.trigger(this" not in html` (negative — redundant trigger absent)
- ✅ Asserts `hx-patch=".../runtime-override"` still present (not broken by the fix)
- ✅ Asserts `name="option_id"` still present (not broken by the fix)

All assertions are **attribute-anchored** (e.g., `'hx-disabled-elt="this"'` not bare `hx-disabled-elt`), satisfying the I-00067 scoping rule.

**Pre-fix reasoning**: The pre-fix template had:
```html
onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');"
```
This contains `this.disabled=true` and `htmx.trigger(this`, so the negative assertions (`not in`) would fail against pre-fix HTML. The positive assertion `'hx-disabled-elt="this"' in html` would also fail pre-fix because that attribute was absent. The template test would fail against pre-fix code.

→ **No issue.**

### Checklist 2 — Persistence test verifies the override is actually set

`test_i00076_patch_step_override_persists_chosen_option`:
- ✅ PATCHes with `data={"option_id": "5"}` (a real id)
- ✅ Asserts `resp.status_code == 204`
- ✅ **Crucially**: after `db_session.expire_all()` + `refresh(step)`, asserts `step.agent_runtime_option_id == 5` — not just "some value was set" but "specifically id=5 was set"

`test_i00076_patch_step_override_clears_on_empty_body`:
- ✅ PATCHes with `data={"option_id": ""}` (empty string → clears)
- ✅ Pre-sets step override to `3` to ensure clearing is detectable
- ✅ Asserts `step.agent_runtime_option_id is None` — covers AC3 (inherit path)

→ **No issue.**

### Checklist 3 — Test hygiene

- ✅ Test names: `test_i00076_*` prefix traces directly to incident I-00076
- ✅ Tests live in `tests/dashboard/test_runtime_override_templates.py` (not unit/ or integration/) — uses `client` + `db_session` fixtures from `tests/dashboard/conftest.py`
- ✅ No live DB connection — `db_session` from testcontainers
- ✅ Seed helpers: `_seed_runtime_options`, `_seed_project_and_batch`, `_seed_work_item_with_steps` reused — no copy-paste bloat
- ✅ Imports: `os` was imported in the original file but unused (`client` fixture pops `IW_CORE_EXPECTED_INSTANCE_ID` before importing `dashboard.app`); no new unused imports introduced by S03
- ✅ No `print()` statements

→ **No issue.**

### Checklist 4 — Coverage adequacy vs Acceptance Criteria

| AC | Covered By | Status |
|----|-----------|--------|
| AC1 (bug fixed) | `test_i00076_editable_step_select_uses_hx_disabled_elt` + `test_i00076_patch_step_override_persists_chosen_option` together | ✅ |
| AC2 (regression test exists) | `test_i00076_editable_step_select_uses_hx_disabled_elt` + `test_i00076_failed_step_select_also_uses_hx_disabled_elt` serve as regression guards | ✅ |
| AC3 (inherit path still works) | `test_i00076_patch_step_override_clears_on_empty_body` | ✅ |
| Optional resolver assertion | `test_i00076_resolve_runtime_step_override_wins` asserts `(cli_tool="claude", model="claude-opus-4-7", id=5)` — not just "a row returned" | ✅ |

→ **No issue.**

### Additional checks

- **Migration in test scope?** S03 wrote tests only. No migration was generated or applied. No finding.
- **Coverage threshold failure**: 19% vs 46% — pre-existing, unchanged from S01. Not a regression from S03.
- **No new `conftest` needed**: existing `tests/dashboard/conftest.py` already exports `db_session` and `client` fixtures.

---

## Verdict

```
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00076",
  "review_target": "S03",
  "verdict": "approve",
  "findings": [],
  "preflight": {"format": "ok", "lint": "ok"},
  "notes": "All 5 tests pass. Template assertions correctly fail pre-fix (missing hx-disabled-elt + present self-disable pattern) and pass post-fix. Persistence tests assert the specific option_id value, not just response code. AC3 (empty body clears override) covered. No lint/format violations. No migration in scope."
}
```