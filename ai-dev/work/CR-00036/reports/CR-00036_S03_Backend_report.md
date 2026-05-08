# CR-00036 S03 Backend Implementation Report

## Work Item
CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge

## Step
S03 — Backend implementation (service layer, CLI, daemon integration)

---

## What Was Done

### 1. ProjectConfig `auto_merge_default` parsing (`orch/daemon/project_registry.py`)
- Added `auto_merge_default: bool = True` field to the `ProjectConfig` dataclass
- Added parsing in `_build_project_config` following the same pattern as `self_assess`:
  - Reads from `projects.toml` top-level key `auto_merge`
  - Defaults to `True` when absent
  - Warns and defaults to `True` for non-bool values
- Unit tests: `test_auto_merge_default_true_when_absent`, `test_auto_merge_true_when_explicit`, `test_auto_merge_false_when_explicit`, `test_auto_merge_non_bool_warns_and_defaults_to_true`

### 2. BatchManager gate (`orch/daemon/batch_manager.py`)
- Modified `_complete_item` to check `batch.auto_merge` before setting `BatchItem.status`
- When `batch.auto_merge = false`: sets status to `awaiting_merge_approval` instead of `completed`; emits `DaemonEvent(event_type="batch_item_awaiting_merge_approval", ...)`
- When `batch.auto_merge = true`: unchanged behavior → `completed`
- Unit tests: `TestAutoMergeGate::test_auto_merge_true_transitions_to_completed`, `TestAutoMergeGate::test_auto_merge_false_transitions_to_awaiting_merge_approval`

### 3. approve_merge service (`orch/services/__init__.py`)
- New `approve_merge(db, project_id, item_id) -> BatchItem` function
- Uses `SELECT ... FOR UPDATE` (matches `merge_queue._merge_item` pattern)
- Raises `ValueError` if item is not in `awaiting_merge_approval` (includes actual status in error message)
- Transitions to `completed` and emits `DaemonEvent(event_type="merge_approved_by_operator", ...)`
- Commits and returns refreshed `BatchItem`
- Integration tests: `test_approves_item_and_transitions_to_completed`, `test_emits_merge_approved_by_operator_event`, `test_returns_batch_item`, `test_raises_if_item_not_found`, `test_raises_if_item_is_completed`, `test_raises_if_item_is_merged`, `test_error_message_includes_actual_status`

### 4. `iw item approve-merge` CLI (`orch/cli/item_commands.py` + `orch/cli/main.py`)
- New `approve_merge_cmd` click command with `item_id` argument and `--project` override option
- Resolves project via existing helper; uses `approve_merge` service
- Exit code 4 on `ValueError`, exit code 1 on other errors
- JSON mode output: `{"item_id": ..., "status": "completed"}`
- Registered in `cli.add_command(approve_merge_cmd, name="approve-merge")`

### 5. `iw batch-create --auto-merge/--no-auto-merge` (`orch/cli/batch_commands.py`)
- Added `--auto-merge/--no-auto-merge` click option (flag pair, default `None`)
- When `None` (no flag): resolves to project's `ProjectConfig.auto_merge_default` via `load_projects_toml(load_config().projects_toml)`
- Passes resolved `auto_merge_value` to `Batch(...)` constructor
- Included in JSON output (`"auto_merge": ...`) and human output (auto-merge: yes/no)

### 6. Dashboard merge status (`dashboard/routers/items.py`)
- Updated `_merge_status`: added branch for `awaiting_merge_approval` returning `"awaiting_approval"` (before the `in_progress` branch)
- `_synthetic_merge_step` unchanged (uses `_merge_status` which now propagates the new state)

### 7. CLI spec doc update (`docs/IW_AI_Core_CLI_Spec.md`)
- Updated `iw batch-create` synopsis to include `[--auto-merge | --no-auto-merge]`
- Added `--auto-merge / --no-auto-merge` row in flag table with default description
- Added new section for `iw item approve-merge <item_id>` documenting:
  - Inputs/outputs
  - Exit codes (0 = success, 4 = invalid state)
  - Human and JSON output shapes

### 8. Daemon design doc update (`docs/IW_AI_Core_Daemon_Design.md`)
- Added §4.7.2 "Auto-merge Gate (CR-00036)" paragraph explaining:
  - New behavior when `auto_merge = false` (park in `awaiting_merge_approval`)
  - How the merge queue continues to pick only `completed` items
  - How operators release items via dashboard or CLI
- Added **stall-checker exemption**: `awaiting_merge_approval` items are exempt from stall-fail timers

### 9. Stall-handling audit
- Ran `grep -rn "IW_CORE_STALL_THRESHOLD|stall|stalled" orch/daemon/ orch/db/models.py`
- Result: No auto-fail path exists for `BatchItem` rows based on `IW_CORE_STALL_THRESHOLD`. Stall monitoring in this codebase applies to `StepRun` (step monitor) and async jobs (doc_index_poller, doc_job_poller), not to `BatchItem` objects. The doc note in §4.7.2 suffices.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/project_registry.py` | Added `auto_merge_default` field + parsing logic |
| `orch/daemon/batch_manager.py` | Gate logic in `_complete_item` + `batch_item_awaiting_merge_approval` event |
| `orch/services/__init__.py` | New `approve_merge` service function |
| `orch/cli/item_commands.py` | New `approve_merge_cmd` click command |
| `orch/cli/main.py` | Registered `approve_merge_cmd` |
| `orch/cli/batch_commands.py` | Added `--auto-merge/--no-auto-merge` flag + resolution logic |
| `dashboard/routers/items.py` | Added `awaiting_merge_approval` branch in `_merge_status` |
| `docs/IW_AI_Core_CLI_Spec.md` | Updated batch-create synopsis, flag table; added `approve-merge` command section |
| `docs/IW_AI_Core_Daemon_Design.md` | Added §4.7.2 Auto-merge Gate + stall-checker exemption |
| `tests/unit/test_project_registry.py` | 4 new tests for `auto_merge` parsing |
| `tests/unit/test_batch_manager.py` | 2 new tests for `TestAutoMergeGate` |
| `tests/integration/test_batch_item_approval.py` | 7 new integration tests for `approve_merge` |

---

## Test Results

| Suite | Result | Details |
|-------|--------|---------|
| `make test-unit` | ✅ 2689 passed | All unit tests including new CR-00036 tests |
| `tests/integration/test_batch_item_approval.py` | ✅ 7 passed | All approve_merge service tests |
| `make typecheck` | ✅ Success | No issues in 232 source files |
| `make lint` | ✅ All checks passed | ruff + node checks clean |

---

## Quality Checks

- **format**: `make format` — clean (ruff format applied where needed)
- **typecheck**: `make typecheck` — `Success: no issues found in 232 source files`
- **lint**: `make lint` — `All checks passed!`

---

## Notes / Observations

1. **Integration test fixtures**: The `test_batch_item_approval.py` tests initially failed at fixture setup because `work_item` and `batch_with_auto_merge_false` fixtures didn't depend on `test_project`. The FK constraint requires the `projects` row to exist first. Fixed by adding `test_project: Project` as a dependency.

2. **CLI project resolution**: `batch-create` now calls `load_projects_toml(load_config().projects_toml)` to look up the project default when `--auto-merge/--no-auto-merge` is not passed. This is the simplest approach that works without restructuring the session factory pattern. An alternative would be to thread `projects_toml` via `ctx.obj`, but that would require broader changes to the CLI context setup.

3. **Stall exemption**: Confirmed there is no actual stall auto-fail code path for `BatchItem` in the daemon. The stall-monitor scope is limited to `StepRun` (via step_monitor) and async jobs (via doc_index_poller/doc_job_poller). The doc note suffices; no code change was needed.

4. **`awaiting_merge_approval` status string**: The `_merge_status` function now returns `"awaiting_approval"` for items in that state. The `_synthetic_merge_step` function simply passes this through to `StepDetail(status=...)`. The actual UI rendering (button appearance, click handling) is S07's responsibility — the backend correctly surfaces the state.

---

## Pre-flight Results

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00036",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/project_registry.py",
    "orch/daemon/batch_manager.py",
    "orch/services/__init__.py",
    "orch/cli/item_commands.py",
    "orch/cli/main.py",
    "orch/cli/batch_commands.py",
    "dashboard/routers/items.py",
    "docs/IW_AI_Core_CLI_Spec.md",
    "docs/IW_AI_Core_Daemon_Design.md",
    "tests/unit/test_project_registry.py",
    "tests/unit/test_batch_manager.py",
    "tests/integration/test_batch_item_approval.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "2689 unit tests passed (including 6 new CR-00036 tests); 7 approve_merge integration tests passed",
  "blockers": [],
  "notes": "Stall audit: no auto-fail path exists for BatchItem in daemon code; doc note added. Integration tests required test_project fixture dependency fix."
}
```
