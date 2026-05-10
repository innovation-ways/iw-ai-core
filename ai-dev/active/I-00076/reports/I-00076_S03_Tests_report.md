# I-00076 S03 Tests Implementation Report

## What Was Done

Added 5 new test cases to `tests/dashboard/test_runtime_override_templates.py` (extended the existing file rather than creating a sibling, per the prompt's "prefer extending the existing file if it stays cohesive" guidance):

### Test Class 1: `TestI00076EditableStepSelect` (template render assertions)
- **`test_i00076_editable_step_select_uses_hx_disabled_elt`** — verifies `pending` step's `<select>` renders with `hx-disabled-elt="this"` (replaces the broken `onchange="this.disabled=true; htmx.trigger(this,'change')"`), and that the broken patterns are absent.
- **`test_i00076_failed_step_select_also_uses_hx_disabled_elt`** — same check for a `failed` step (S04), ensuring the fix applies to both editable statuses.

### Test Class 2: `TestI00076PatchStepOverride` (API persistence)
- **`test_i00076_patch_step_override_persists_chosen_option`** — PATCH with `option_id=5` (claude, claude-opus-4-7) → 204, then `workflow_steps.agent_runtime_option_id == 5` after refresh. Semantic: verifies the specific expected ID, not just "a value was set."
- **`test_i00076_patch_step_override_clears_on_empty_body`** — PATCH with empty `option_id=""` → clears the override to `None` (the "— inherit —" / AC3 path).

### Test Class 3: `TestI00076ResolveRuntime` (resolver integration)
- **`test_i00076_resolve_runtime_step_override_wins`** — verifies `resolve_runtime()` with `step.agent_runtime_option_id=5` returns the `claude`/`claude-opus-4-7` row, not the project default (`opencode`/`minimax`). Inline comment notes why `_seed_runtime_options` is called even though its return value isn't used.

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_runtime_override_templates.py` | Added 3 new test classes, 5 new test methods; reused existing seed helpers (`_seed_runtime_options`, `_seed_project_and_batch`, `_seed_work_item_with_steps`) and `client` fixture pattern |

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | Fixed — reformatted the new section with ruff |
| `make typecheck` | ok — 0 errors in 239 source files |
| `make lint` | ok — All checks passed |

## Test Results

```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -v
# 15 passed, 1 warning in ~22s
# Coverage failure (19% vs 46% threshold) is pre-existing — unchanged from S01
```

The coverage threshold failure was present before my edits (reported by S01 as well). It is not a regression from these test additions.

## Notes

- **Semantic correctness**: All assertions verify specific values (e.g., `assert resolved.cli_tool == "claude"`), not just shape (e.g., `assert "cli_tool" in data`). This follows the I003 lesson emphasized in the prompt.
- **Resolver test**: included as recommended (it required only `FakeProject` — no heavy fixture). The `_seed_runtime_options()` call is necessary to ensure id=5 exists in the DB; a comment explains why the return value is discarded.
- **No new seed helpers needed**: existing `_seed_runtime_options`, `_seed_project_and_batch`, and `_seed_work_item_with_steps` were sufficient. No new scaffolding was added.
- **No live DB connection**: all tests use the testcontainer-backed `db_session` fixture from `tests/integration/conftest.py` (re-exported by `tests/dashboard/conftest.py`).

## How These Tests Validate the Fix

| Test | Pre-fix expectation | Post-fix expectation |
|------|---------------------|---------------------|
| `test_i00076_editable_step_select_uses_hx_disabled_elt` | FAIL — pre-fix HTML has `this.disabled=true` and no `hx-disabled-elt` | PASS — HTML has `hx-disabled-elt="this"`, no self-disabling pattern |
| `test_i00076_failed_step_select_also_uses_hx_disabled_elt` | FAIL — same | PASS — same |
| `test_i00076_patch_step_override_persists_chosen_option` | PASS — endpoint already works; this validates the full path | PASS |
| `test_i00076_patch_step_override_clears_on_empty_body` | PASS — validates AC3 | PASS |
| `test_i00076_resolve_runtime_step_override_wins` | PASS — resolver cascade was already correct (it fell through because override was never set) | PASS |