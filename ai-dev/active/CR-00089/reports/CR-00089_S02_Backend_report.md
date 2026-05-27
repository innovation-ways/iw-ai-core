# CR-00089 S02 Backend Report

## What was done
- Updated `orch/daemon/fix_cycle.py` to include `ProjectConfig.always_in_scope_paths` in scope reconciliation at both required sites.
- Site A (`run_fix_cycle`):
  - Added optional parameter `project_config: ProjectConfig | None = None`.
  - After `_load_allowed_paths(...)`, appended `project_config.always_in_scope_paths` when config is present, before scope prompt block generation.
- Site B (`_complete_fix_cycle`):
  - After `_load_allowed_paths(...)`, appended `project_config.always_in_scope_paths` when config is present, before violation filtering.

## Files changed
- `orch/daemon/fix_cycle.py`
- `ai-dev/active/CR-00089/reports/CR-00089_S02_Backend_report.md`

## Call sites updated
- `orch/daemon/fix_cycle.py:238-241` (`run_fix_cycle` allowed-path expansion)
- `orch/daemon/fix_cycle.py:1103-1106` (`_complete_fix_cycle` allowed-path expansion)

## Test results
- `make lint && make typecheck` ✅ passed

## Issues / observations
- No `run_fix_cycle(...)` caller updates were required in `orch/daemon/`; function signature change is backward compatible via default `project_config=None`.
