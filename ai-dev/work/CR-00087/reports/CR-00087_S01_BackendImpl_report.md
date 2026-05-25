# CR-00087 S01 BackendImpl Report

**Work Item**: CR-00087 — Auto-amend scope violations matching per-project allow-patterns
**Step**: S01 — Backend implementation (registry parsing)
**Agent**: backend-impl
**Status**: ✅ Complete

---

## What was done

Added the `auto_amend_scope` config parsing infrastructure to `orch/daemon/project_registry.py` — this is the foundation that S03's fix-cycle integration will consume in the daemon's `_complete_fix_cycle` path.

### Changes

**`orch/daemon/project_registry.py`** — 3 edits:

1. **Added two fields to `ProjectConfig`**: `auto_amend_allow_patterns: list[str]` (default `[]`) and `auto_amend_max_paths: int | None` (default `None`). Placed adjacent to the related `overlap_*` fields per project convention.

2. **Added `_parse_auto_amend_scope` helper function**: Mirrors the defensive style of `_parse_overlap_gate`. Validates:
   - `raw is None` → `([], None)` silently (feature off)
   - `raw` not a dict → WARNING, `([], None)`
   - `auto_allow_patterns` missing → `([], None)`
   - `auto_allow_patterns` not a list → WARNING, `([], None)`
   - Mixed-type entries → drop non-strings with per-entry WARNING; if nothing survives, `([], None)`
   - `max_paths` missing → `None` (no cap)
   - `max_paths` not an int (or is a bool — explicitly rejected so `True`/`False` don't coerce to `1`/`0`) → WARNING, `None`
   - `max_paths < 0` → WARNING, `None`

3. **Wired into `_build_project_config`**: After `_parse_overlap_gate`, called `_parse_auto_amend_scope(project_id, iw_config.get("auto_amend_scope"))` and passed the two values into the `ProjectConfig(...)` constructor.

**`tests/unit/daemon/test_project_registry_auto_amend_scope.py`** — NEW file with 11 tests:

- `TestParseAutoAmendScope` (10 tests for the pure function):
  - `test_none_returns_defaults`
  - `test_valid_block_with_both_fields`
  - `test_valid_block_patterns_only_max_paths_none`
  - `test_malformed_raw_is_list`
  - `test_malformed_auto_allow_patterns_is_string` (feature off, per spec — mirrors `_parse_overlap_gate` for same class of error)
  - `test_malformed_auto_allow_patterns_mixed_entries`
  - `test_malformed_max_paths_is_string`
  - `test_malformed_max_paths_is_bool_true`
  - `test_malformed_max_paths_is_negative`
  - `test_empty_patterns_returns_empty_and_does_not_fire`
- `TestProjectConfigAutoAmendScope` (1 test for the dataclass field defaults):
  - `test_auto_amend_scope_absent_uses_defaults`

### TDD RED evidence

First test written: `test_auto_amend_scope_absent_uses_defaults` (in `TestProjectConfigAutoAmendScope`)

```
ERROR tests/unit/daemon/test_project_registry_auto_amend_scope.py
ImportError: cannot import name '_parse_auto_amend_scope' from 'orch.daemon.project_registry'
```

The module-level import failed because the function didn't exist yet. After implementing, all 11 tests pass.

---

## Test results

```
11 passed in 13.18s
```

Coverage failure is expected — this is a single test file in a large codebase with a 50% global floor. The coverage check is not a test failure; the actual pytest result is all green.

---

## Pre-flight quality gates

| Gate | Result | Details |
|------|--------|---------|
| `make format` | ✅ ok | Applied `ruff format` to 2 files |
| `make lint` | ✅ ok | All checks passed (ruff + check_templates.py) |
| `make typecheck` | ✅ ok | Success: no issues found in 276 source files |

---

## Notes

- The test for `auto_allow_patterns` as a string (`test_malformed_auto_allow_patterns_is_string`) was updated after initial implementation to match the spec: when `auto_allow_patterns` is not a list, the entire block is treated as absent and the feature is disabled (both `patterns` and `max_paths` become `None`). This mirrors `_parse_overlap_gate`'s behaviour for the same class of error, where a non-list value causes the entire side to default.
- `_parse_auto_amend_scope` is a module-level function (not a method on `ProjectConfig`) — this is consistent with `_parse_overlap_gate` and `_parse_ai_assistant_block`, which are also module-level helpers consumed by `_build_project_config`.
- The `bool` explicit rejection in the `max_paths` validation uses `isinstance(raw_max, bool)` as a separate check before `isinstance(raw_max, int)` — this is correct because in Python `bool` is a subclass of `int`, so `isinstance(True, int)` is `True`. The separate bool check is required to reject `True`/`False` values.