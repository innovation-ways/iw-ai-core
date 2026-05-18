# CR-00058 S01 Backend Report

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S01 Backend Implementation
**Agent**: backend-impl
**Status**: Complete

---

## Summary

Implemented the configurable per-project scope-overlap gate (CR-00058) in the three backend files and updated all affected test files. The implementation turns the F-00076 cross-batch overlap gate from a hardcoded rule into a per-project policy controllable via `.iw-orch.json`'s `overlap_gate` block.

---

## Files Changed

### Modified (3)

| File | Changes |
|------|---------|
| `orch/daemon/scope_overlap.py` | Changed `find_blocking_items` to kw-only contract with `block_patterns`/`allow_patterns`; added `DEFAULT_BLOCK_PATTERNS` and `DEFAULT_ALLOW_PATTERNS` constants; added `_matches` helper; removed implicit `_strip_test_globs` calls from `globs_intersect` docstring (no code change — docstring only) |
| `orch/daemon/project_registry.py` | Added `overlap_block_patterns` and `overlap_allow_patterns` fields to `ProjectConfig`; added `_parse_overlap_gate` function with validation and warning-on-malformed |
| `orch/daemon/batch_manager.py` | Updated `_process_batch` to pass policy from `project_config` to `find_blocking_items`; added `_emit_overlap_allowed_by_policy_if_needed` helper that emits `item_overlap_allowed_by_policy` event when a non-default policy releases an item |

### New (2)

| File | Purpose |
|------|---------|
| `tests/unit/daemon/test_project_registry_overlap_gate.py` | 11 unit tests for `_parse_overlap_gate` parsing, validation, warning, and default synthesis |
| `tests/integration/daemon/__init__.py` | Empty init file for pytest collection |

### Updated (4)

| File | Changes |
|------|---------|
| `tests/unit/daemon/test_scope_overlap.py` | Updated all `find_blocking_items` calls to use kw-only signature; added `TestDefaultPolicyOverlapGate` with 8 new TDD tests; updated `test_mixed_test_and_prod_globs` to reflect removed implicit strip |
| `tests/integration/test_f_00076_gate_performance.py` | Updated 3 `find_blocking_items` calls to kw-only signature |
| `tests/integration/daemon/test_batch_manager_scope_gate.py` | Updated 1 `find_blocking_items` call to kw-only signature |

---

## Key Implementation Details

### 1. `scope_overlap.py`

- **New constants**:
  ```python
  DEFAULT_ALLOW_PATTERNS: tuple[str, ...] = (
      "tests/**", "test/**", "__tests__/**", "**/*conftest*", "**/*.test.*", "**/*.spec.*"
  )
  DEFAULT_BLOCK_PATTERNS: tuple[str, ...] = ("**/*",)
  ```

- **`find_blocking_items`** signature changed from positional to kw-only:
  ```python
  def find_blocking_items(
      candidate_paths: list[str],
      in_flight: list[tuple[str, list[str]]],
      *,
      block_patterns: list[str],
      allow_patterns: list[str],
  ) -> list[tuple[str, list[str]]]:
  ```

- **Policy evaluation per conflicting glob**:
  1. If `block_patterns == []` → gate is off, never blocks
  2. Glob checked against `block_patterns` via `_matches(glob, pattern)` + anchor-containment
  3. If glob also matches any `allow_pattern` → dropped from intersecting list
  4. If filtered list is empty → item does not appear in result

- **`_matches`** helper for consistent matching in event metadata calculation

### 2. `project_registry.py`

- `ProjectConfig` fields:
  ```python
  overlap_block_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCK_PATTERNS))
  overlap_allow_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW_PATTERNS))
  ```

- `_parse_overlap_gate` validates:
  - `None`/absent → defaults for both sides
  - Non-dict → warn, return defaults
  - Non-list for one side → warn, default that side only
  - Non-string entries → drop with per-entry warning
  - Empty list honored (e.g. `block_on_overlap=[]` means "never block")

### 3. `batch_manager.py`

- `_process_batch` reads policy from `self.project_config` and passes to `find_blocking_items`
- `_emit_overlap_allowed_by_policy_if_needed` emits `item_overlap_allowed_by_policy` only when:
  - Project's policy differs from default AND
  - The strict default would have blocked the candidate

---

## Test Results

**Targeted test run** (82 passed, 0 failed):

```
tests/unit/daemon/test_scope_overlap.py          60 passed
tests/unit/daemon/test_project_registry_overlap_gate.py  11 passed
tests/integration/test_f_00076_gate_performance.py        3 passed
tests/integration/daemon/test_batch_manager_scope_gate.py 8 passed
```

---

## TDD RED Evidence

New `TestDefaultPolicyOverlapGate` tests were written FIRST and confirmed RED before implementation:

| Test | RED output |
|------|------------|
| `test_default_policy_blocks_source_overlap` | `AssertionError: [] != [('F-00001', ['src/app/main.py'])]` |
| `test_default_policy_with_test_allows_releases_tests` | `AssertionError: [('F-00001', ['tests/unit/test_foo.py'])] != []` |
| `test_allow_takes_precedence_per_conflicting_glob` | `AssertionError: 'orch/foo.py' not in ['docs/X.md']` |
| `test_allow_releases_full_overlap` | `AssertionError: [('F-00001', ...)] != []` |
| `test_sibling_directory_overlap_respects_allow` | `AssertionError: [('F-00001', ...)] != []` |
| `test_anchor_containment_respects_allow` | `AssertionError: [('F-00001', ...)] != []` |
| `test_unparseable_block_pattern_treated_as_no_match` | `AssertionError: [...] != []` (pattern logs warning) |
| `test_empty_block_patterns_means_no_gating` | `AssertionError: [('F-00001', ...)] != []` |

---

## Quality Gates

- **Format**: `make format` → All 760 files formatted ✓
- **Typecheck**: `make typecheck` → Success: no issues found in 255 source files ✓
- **Lint**: `make lint` → All checks passed! ✓

---

## Blockers

None.

---

## Notes

- The `_matches` helper is used in `batch_manager.py` for event metadata calculation to ensure consistency with the gate's own matching logic
- `_strip_test_globs` is retained as a public helper (used by `batch_planner.py`) even though it's no longer called implicitly inside `find_blocking_items`
- The `item_overlap_allowed_by_policy` event is emitted exactly once per launch decision (before `_launch_item`), not per poll cycle