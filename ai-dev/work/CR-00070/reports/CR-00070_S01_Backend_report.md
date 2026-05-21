# CR-00070 S01 Backend Implementation Report

## Summary

Backend implementation complete for **CR-00070 S01**: "Show Resolved Agent + Model Instead of 'Inherit' in Step Runtime Dropdowns".

The backend now computes the effective inherited runtime for each work item and passes `inherited_runtime_label` to the steps table template — enabling S02 (frontend) to relabel the empty option from "— inherit —" to a descriptive, actionable label.

## What Was Done

### 1. `orch/agent_runtime/resolver.py` — `resolve_inherited_runtime()` helper

Added `resolve_inherited_runtime()` that answers "what does a step with no step-level override actually run?". It:
- Delegates to `resolve_runtime()` with a no-step-override sentinel (an object whose `agent_runtime_option_id` is `None`)
- Catches the `RuntimeError` from `resolve_runtime()`'s "unreachable" branch and returns `None` instead — so the dashboard degrades gracefully when the catalogue is empty
- Returns `AgentRuntimeOption | None`

### 2. `orch/agent_runtime/__init__.py` — exported the new helper

Added `resolve_inherited_runtime` to `__all__`.

### 3. `dashboard/routers/items.py` — `_get_inherited_runtime_label()` helper

Added a factored private helper at module level (thin-routers principle) that:
- Loads the project's `ProjectConfig` from `projects.toml` using `load_projects_toml(load_config().projects_toml).get(project_id)` — same source as the daemon
- Calls `resolve_inherited_runtime()` with the session, item, and project config
- Returns the `display_name` string or `None`

### 4. `dashboard/routers/items.py` — wired `item_detail` and `item_tab_overview`

Both routes now call `_get_inherited_runtime_label()` and pass `inherited_runtime_label` to the template context.

### 5. `dashboard/routers/runtime_overrides.py` — wired `_render_steps_fragment`

Added `inherited_runtime_label` to the template context in the PATCH-response fragment renderer.

### 6. Tests

#### Integration tests: `tests/integration/test_resolve_inherited_runtime.py`
- **AC2**: item-level override returned (not catalogue default)
- **AC2**: item-level override wins over `projects.toml` lookup
- **AC1**: cascade to `projects.toml` lookup when no item override
- **AC1**: cascade to catalogue default when `projects.toml` value not in catalogue
- **AC5**: empty catalogue → `None` (no raise)
- **AC5**: all-options-disabled → `None` (no raise)
- **Equivalence**: result matches `resolve_runtime()` for the no-step-override case

#### Dashboard render-path tests: `tests/dashboard/test_resolve_inherited_runtime_context.py`
- **AC1/AC3/AC6**: all three render paths (item_detail, tab/overview, PATCH fragment) render without error
- **AC3**: item-level override is respected by the inherited label
- **AC5**: empty catalogue → steps table still renders (200, no 500)
- **AC6**: all three paths render successfully for the same item

## Files Changed

| File | Change |
|------|--------|
| `orch/agent_runtime/resolver.py` | Added `resolve_inherited_runtime()` |
| `orch/agent_runtime/__init__.py` | Exported `resolve_inherited_runtime` |
| `dashboard/routers/items.py` | Added `_get_inherited_runtime_label()`, wired to `item_detail` and `item_tab_overview` |
| `dashboard/routers/runtime_overrides.py` | Added `inherited_runtime_label` to `_render_steps_fragment` context |
| `tests/integration/test_resolve_inherited_runtime.py` | New — 7 integration tests for the resolver helper |
| `tests/dashboard/test_resolve_inherited_runtime_context.py` | New — 6 dashboard tests for the three render paths |

## Test Results

```
13 passed in ~30s (with coverage) / ~13s (--no-cov)
```

All tests pass. No regressions in existing test suite (only targeted tests run, per CR-00023 policy).

## Preflight Checks

| Check | Result |
|-------|--------|
| `make format` | ✅ Fixed (3 files reformatted by ruff) |
| `make lint` | ✅ All checks passed |
| `make typecheck` | ✅ Success: no issues in 273 source files |

## TDD Evidence (RED phase)

**RED run output** (first failing run before implementation):

```
tests/integration/test_resolve_inherited_runtime.py
ImportError: cannot import name 'resolve_inherited_runtime' from 'orch.agent_runtime.resolver'
```

The import error at collection time confirmed the function was absent and the tests were correctly written to fail in RED phase with `ImportError` (not a logic error). After implementing the helper, all 13 tests pass.

## Notes

- The `inherited_runtime_label` value is `None` only when the catalogue is completely empty (no enabled rows and no default row). This triggers the template fallback to "— inherit —" per AC5.
- The helper intentionally does NOT load `AgentRuntimeOption` rows directly — it delegates entirely to `resolve_runtime()` so the cascade is guaranteed to match what the daemon resolves.
- No schema changes, no migrations, no Docker interactions.