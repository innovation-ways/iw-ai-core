# CR-00089 S01 Backend Report

## What was done
- Added `always_in_scope_paths: list[str] = field(default_factory=list)` to `ProjectConfig` in `orch/daemon/project_registry.py`.
- Added parsing for `[projects.<id>.always_in_scope] paths = [...]` inside `_build_project_config`, with defensive validation and warning on invalid `paths` type/content.
- Threaded `always_in_scope_paths` into the `ProjectConfig(...)` constructor.
- Added `[projects.iw-ai-core.always_in_scope]` to `projects.toml` with:
  - `tests/assertion_free_baseline.txt`
- Implemented RED→GREEN TDD in `tests/unit/daemon/test_always_in_scope.py`:
  - verifies explicit parsing of `always_in_scope.paths`
  - verifies missing block defaults to `[]`.

## TDD RED evidence
- `uv run pytest -q tests/unit/daemon/test_always_in_scope.py`
- Initial failure mode: `AttributeError: 'ProjectConfig' object has no attribute 'always_in_scope_paths'` in both new tests.

## Test results
- `uv run pytest -q tests/unit/daemon/test_always_in_scope.py` → **2 passed**
- `make lint && make typecheck` → **passed**

## Files changed
- `orch/daemon/project_registry.py`
- `projects.toml`
- `tests/unit/daemon/test_always_in_scope.py`
- `ai-dev/active/CR-00089/reports/CR-00089_S01_Backend_report.md`

## Issues / observations
- Running `pytest` directly (without `uv run`) picked up a different environment; project-standard `uv run pytest` was used for authoritative results.
