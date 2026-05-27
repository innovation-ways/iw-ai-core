# CR-00089_S05_Tests_prompt

**Work Item**: CR-00089 -- Fix-Cycle Pipeline Systemic Hardening (I-00113 RCA Follow-up)
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00089 --json`
- `ai-dev/active/CR-00089/CR-00089_CR_Design.md` — design (AC1–AC6 drive the test plan)
- `ai-dev/work/CR-00089/reports/CR-00089_S01_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S02_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S03_Backend_report.md`
- `ai-dev/work/CR-00089/reports/CR-00089_S04_Backend_report.md`
- `orch/daemon/project_registry.py` — check `ProjectConfig.always_in_scope_paths` field name
- `orch/daemon/fix_cycle.py` — check `_GATE_RELEVANT_EXTENSIONS`, `_gate_is_relevant`, updated signatures
- `orch/daemon/step_monitor.py` — check `completed_at` guard location
- `tests/unit/daemon/test_scope_overlap.py` — reference for unit test patterns
- `tests/unit/daemon/test_step_monitor_i00113_probe_unit.py` — reference for step_monitor mock patterns
- `tests/unit/daemon/test_fix_cycle_budget_exemption.py` — reference for fix_cycle unit test patterns

## Output Files

- `ai-dev/work/CR-00089/reports/CR-00089_S05_Tests_report.md`

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

In our case, that means:

- BAD: `assert len(violations) == 0` (just shape)
- GOOD: `assert violations == []` (exact value)
- BAD: `assert _handle_crashed.called is False` without asserting the early return path
- GOOD: `assert not mock_handle_crashed.called` and also assert `run.completed_at` was not mutated
- BAD: `assert gate_id in reset_ids` (membership only)
- GOOD: `assert reset_ids == ["assertion-check"]` and `assert lint_gate.status == StepStatus.completed` (exact outcome)

## Context

You are implementing **Step 5 of 13** of CR-00089. S01–S04 added the implementation. Your job is comprehensive unit test coverage across all four changes. S01 and S03 each created a starter test file with RED-first tests; extend them and add the cascade and scope tests.

Read `CLAUDE.md` and `tests/CLAUDE.md` before writing tests.

## Requirements

### 1. Extend tests/unit/daemon/test_always_in_scope.py (S01's starter file)

Check what S01 already added. Extend with:

**`test_always_in_scope_appended_to_allowed`** — Mock `_load_allowed_paths` to return `["orch/foo.py"]`. Build a `ProjectConfig` with `always_in_scope_paths=["tests/assertion_free_baseline.txt"]`. Simulate the reconciliation logic from S02: `allowed = manifest_paths + project_config.always_in_scope_paths`. Assert `"tests/assertion_free_baseline.txt"` is in `allowed`.

**`test_always_in_scope_no_violation_for_global_file`** — Call the actual scope reconciliation path (or test the logic directly): given `allowed=["orch/foo.py"]` and `always_in_scope_paths=["tests/assertion_free_baseline.txt"]`, a file `tests/assertion_free_baseline.txt` in `agent_touched` must produce zero violations.

**`test_always_in_scope_empty_by_default`** — Construct `ProjectConfig` from a dict with no `always_in_scope` key. Assert `always_in_scope_paths == []`.

**`test_always_in_scope_invalid_paths_type_defaults_to_empty`** — Pass `always_in_scope={"paths": "not-a-list"}`. Assert `always_in_scope_paths == []` (and no exception).

### 2. Extend tests/unit/daemon/test_step_monitor_completed_at_guard.py (S03's starter file)

Check what S03 already added. Extend with:

**`test_completed_at_none_still_calls_handle_crashed`** — `run.completed_at = None`. Patch `_is_pid_alive → False`, `_probe_for_child → False`. Assert `_handle_crashed` IS called (regression guard).

**`test_completed_at_set_and_child_alive_is_child_check_first`** — `run.completed_at = datetime.now(UTC)`. Patch `_is_pid_alive → False`, `_probe_for_child → True`. Assert `_handle_crashed` is NOT called (child check takes priority over completed_at guard — both are early returns, so order doesn't change the outcome, but the child case must remain functional).

### 3. Create tests/unit/daemon/test_cascade_smarter_scope.py (new file)

**`test_gate_is_relevant_python_file_resets_all_known_gates`** — For each gate name in `_GATE_RELEVANT_EXTENSIONS`, call `_gate_is_relevant(gate_name, ["orch/foo.py"])`. Assert all return True.

**`test_gate_is_relevant_txt_file_skips_python_only_gates`** — Call `_gate_is_relevant("lint", ["tests/assertion_free_baseline.txt"])`. Assert False. Call `_gate_is_relevant("format", ["tests/assertion_free_baseline.txt"])`. Assert False. Call `_gate_is_relevant("assertion-check", ["tests/assertion_free_baseline.txt"])`. Assert True.

**`test_gate_is_relevant_empty_changed_files_is_conservative`** — Call `_gate_is_relevant("lint", [])`. Assert True (AC5: conservative fallback).

**`test_gate_is_relevant_unknown_gate_is_conservative`** — Unknown gates must always return True regardless of what files changed — the pipeline must never silently skip resetting a gate it doesn't recognise. Call `_gate_is_relevant("some-new-gate", ["README.md"])`. Assert True. Also call `_gate_is_relevant("some-new-gate", ["orch/foo.py"])`. Assert True. Both return True because an unknown gate name is treated as "conservative reset always".

**`test_cascade_reset_skips_irrelevant_gates`** — Build a minimal mock DB session with two upstream `WorkflowStep` objects: one with `gate="lint"` and one with `gate="assertion-check"`, both `status=completed`. Call `_cascade_reset_upstream_qv_gates(db, cycle, failing_step, project_id, changed_files=["tests/assertion_free_baseline.txt"])`. Assert only the `assertion-check` gate is reset to `pending`; the `lint` gate remains `completed`.

**`test_cascade_reset_empty_changed_files_resets_all`** — Same setup but `changed_files=[]`. Assert both gates are reset (AC5).

Use SQLAlchemy in-memory session or MagicMock for DB — follow the pattern in `test_fix_cycle_budget_exemption.py`.

### 4. Run targeted tests only

```bash
uv run pytest tests/unit/daemon/test_always_in_scope.py \
              tests/unit/daemon/test_step_monitor_completed_at_guard.py \
              tests/unit/daemon/test_cascade_smarter_scope.py -v
```

Do NOT run `make test-unit` — that is S11's job.

Also run:
```bash
make lint
make format-check
make typecheck
```

Fix any violations in the new test files before submitting.

## Hard Rules

- Allowed paths: `tests/unit/daemon/test_always_in_scope.py`, `tests/unit/daemon/test_step_monitor_completed_at_guard.py`, `tests/unit/daemon/test_cascade_smarter_scope.py`, `ai-dev/work/CR-00089/reports/**`.
- Do NOT modify implementation files (`fix_cycle.py`, `step_monitor.py`, `project_registry.py`).
- Use strong assertions (exact equality, not `assert x in y`).
- No `assert isinstance(x, ...)` without also checking the value.

## Result Contract

Emit standard `iw step-done` JSON with:
- `files_changed`: exact list.
- `tests_added`: all new test function names.
- `tests_passed`: boolean.
- `test_summary`: "X passed, 0 failed".
