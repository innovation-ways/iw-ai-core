# I-00061_S03_Tests_prompt

**Work Item**: I-00061 — Auto-skip phantom QV gates at item approval
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Standard policy — see `ai-dev/templates/Implementation_Prompt_Template.md`. Testcontainer fixtures spun up by `tests/conftest.py` are exempt and required for integration tests.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This step adds tests only — no migrations, no schema changes.)

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00061 --json`.
- `ai-dev/active/I-00061/I-00061_Issue_Design.md` — Design (READ FULLY; the AC1-AC5 section IS the test plan)
- `ai-dev/active/I-00061/reports/I-00061_S01_Backend_report.md` — S01 report (lists exact files changed and any nuances)
- `orch/qv_gate_validator.py` — the module under test
- `orch/cli/item_commands.py` and `orch/cli/batch_commands.py` — for integration-test entry points
- `tests/CLAUDE.md` — testcontainer rules, FTS trigger registration, fixture conventions
- `tests/conftest.py` — existing fixtures (DB session, project setup, work item creation helpers)

## Output Files

- `tests/unit/test_qv_gate_validator.py` (NEW)
- `tests/integration/test_phantom_gate_auto_skip.py` (NEW)
- `ai-dev/active/I-00061/reports/I-00061_S03_Tests_report.md` — Step report

## Context

You are writing the regression-prevention test suite for I-00061. The fix is already in place from S01 (validator + 2 CLI hooks). Your job is to lock in correct behaviour and prove it with a failing-then-passing test.

This is TWO test files:

1. **Unit tests (`tests/unit/test_qv_gate_validator.py`)** — exercise `validate_qv_gate` and `classify_qv_gate` (the pure functions) with a temp directory standing in for `repo_root`. No database needed. Fast.
2. **Integration tests (`tests/integration/test_phantom_gate_auto_skip.py`)** — exercise the full `iw approve` and `iw batch-approve` paths against a real PostgreSQL testcontainer, with real `WorkflowStep` rows registered. Verify status transitions and `DaemonEvent` rows.

## Requirements

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "auto_skipped_steps" in result.output` (shape only)
- BAD: `assert len(skipped) > 0` (non-empty only)
- GOOD: `assert ("S05", "arch-check", "missing_makefile_target") in skipped` (semantic — verifies specific tuple)
- GOOD: `assert step.status == StepStatus.skipped` (semantic — verifies exact enum)
- GOOD: `assert ev.event_metadata["reason"] == "missing_directory"` (semantic — exact string)

Apply this to EVERY assertion. Never assert "something happened" — assert "this specific thing happened with this specific value."

### 1. Unit tests (`tests/unit/test_qv_gate_validator.py`)

Use `pytest`'s `tmp_path` fixture as `repo_root`. Each test sets up the minimal filesystem state to trigger one branch of the validator.

Required test cases (all of these MUST be present):

#### Makefile target patterns

```python
def test_makefile_target_present_runnable(tmp_path):
    (tmp_path / "Makefile").write_text("lint:\n\tnoop\n")
    assert validate_qv_gate(tmp_path, "lint", "make lint") is True

def test_makefile_target_missing_phantom(tmp_path):
    (tmp_path / "Makefile").write_text("lint:\n\tnoop\n")
    v = classify_qv_gate(tmp_path, "arch-check", "make arch-check")
    assert v.runnable is False
    assert v.reason == "missing_makefile_target"

def test_makefile_file_missing_phantom(tmp_path):
    # No Makefile at all — make commands must be flagged phantom
    v = classify_qv_gate(tmp_path, "lint", "make lint")
    assert v.runnable is False
    assert v.reason in {"missing_makefile_file", "missing_makefile_target"}

def test_makefile_target_with_dependencies(tmp_path):
    # Targets that have dependencies on the same line still match.
    (tmp_path / "Makefile").write_text("test: test-unit test-integration\n\tnoop\n")
    assert validate_qv_gate(tmp_path, "test", "make test") is True

def test_makefile_target_with_phony(tmp_path):
    # PHONY declarations must not interfere; the actual target line is what counts.
    (tmp_path / "Makefile").write_text(".PHONY: lint\nlint:\n\tnoop\n")
    assert validate_qv_gate(tmp_path, "lint", "make lint") is True
```

#### `cd <dir>` patterns

```python
def test_cd_dir_present_runnable(tmp_path):
    (tmp_path / "frontend").mkdir()
    assert validate_qv_gate(tmp_path, "frontend-tsc",
                            "cd frontend && npx tsc --noEmit") is True

def test_cd_dir_missing_phantom(tmp_path):
    v = classify_qv_gate(tmp_path, "frontend-tsc",
                         "cd frontend && npx tsc --noEmit")
    assert v.runnable is False
    assert v.reason == "missing_directory"

def test_cd_dir_is_a_file_phantom(tmp_path):
    # If 'frontend' exists but is a regular file, that's still phantom.
    (tmp_path / "frontend").write_text("not a directory")
    v = classify_qv_gate(tmp_path, "frontend-tsc",
                         "cd frontend && npx tsc --noEmit")
    assert v.runnable is False
    assert v.reason == "missing_directory"
```

#### Bare-executable patterns

```python
def test_bare_exec_on_path_runnable(tmp_path):
    # 'sh' is on PATH on every Linux box; safe baseline.
    assert validate_qv_gate(tmp_path, "shell-check", "sh -c 'echo ok'") is True

def test_bare_exec_off_path_phantom(tmp_path):
    v = classify_qv_gate(tmp_path, "deno-fmt", "deno-this-binary-does-not-exist --check")
    assert v.runnable is False
    assert v.reason == "missing_executable"
```

#### Conservative-default cases (MUST be runnable)

```python
def test_unknown_shape_returns_runnable(tmp_path):
    # A complex pipeline we can't confidently classify must NOT be flagged.
    assert validate_qv_gate(tmp_path, "weird", "foo | bar | baz > out.txt") is True

def test_make_with_no_target_returns_runnable(tmp_path):
    # 'make' alone (default goal) is conservative — runnable.
    (tmp_path / "Makefile").write_text("all:\n\tnoop\n")
    assert validate_qv_gate(tmp_path, "default", "make") is True

def test_command_with_envvars_returns_runnable(tmp_path):
    # We don't try to expand $VAR — be conservative.
    assert validate_qv_gate(tmp_path, "x", "FOO=1 some-command") is True
```

Verify every `reason` string is one of the documented values: `"missing_makefile_target"`, `"missing_makefile_file"`, `"missing_directory"`, `"missing_executable"`. If S01 introduced a new reason, ASK the orchestrator to update the design doc — do NOT silently accept new reason strings.

### 2. Integration tests (`tests/integration/test_phantom_gate_auto_skip.py`)

Use existing testcontainer fixtures from `tests/conftest.py`. Each test:

1. Registers a project with `repo_root = tmp_path` (or uses an existing fixture that creates a temp project root).
2. Writes a real `Makefile` in that root with whatever targets the test needs.
3. Registers a `WorkItem` in `draft` status with a set of `WorkflowStep` rows (mix of phantom and real `quality_validation` rows).
4. Invokes the CLI command using Click's `CliRunner` (this is the existing pattern in `tests/integration/`).
5. Asserts the resulting DB state — `WorkflowStep.status` per row, and that `DaemonEvent` rows were created with the right metadata.

#### Required test cases

```python
def test_iw_approve_auto_skips_phantom_makefile_gate(testcontainer_session, cli_runner, tmp_project_with_makefile):
    """AC1: iw approve auto-skips a make-target phantom gate."""
    # Setup: Makefile has 'lint' but not 'arch-check'
    # Item I-99001 with steps S01-impl, S02-qv-gate(lint), S03-qv-gate(arch-check)
    # ...
    result = cli_runner.invoke(cli, ["approve", "I-99001"], obj={"json": True, ...})
    assert result.exit_code == 0

    out = json.loads(result.output)
    skipped = out["auto_skipped_steps"]
    assert {"step_id": "S03", "gate": "arch-check", "reason": "missing_makefile_target"} in skipped
    # Real gate untouched
    assert all(s["step_id"] != "S02" for s in skipped)

    # DB state
    s02 = session.query(WorkflowStep).filter_by(work_item_id="I-99001", step_id="S02").one()
    s03 = session.query(WorkflowStep).filter_by(work_item_id="I-99001", step_id="S03").one()
    assert s02.status == StepStatus.pending  # real gate stays pending
    assert s03.status == StepStatus.skipped  # phantom gate skipped
    assert s03.completed_at is not None

    # Audit event
    ev = session.query(DaemonEvent).filter(
        DaemonEvent.event_type == "step_auto_skipped_phantom_gate",
        DaemonEvent.entity_id == "I-99001/S03",
    ).one()
    assert ev.event_metadata["gate"] == "arch-check"
    assert ev.event_metadata["reason"] == "missing_makefile_target"
    assert ev.event_metadata["trigger"] == "approve"

def test_iw_approve_auto_skips_phantom_cd_gate(testcontainer_session, cli_runner, tmp_project_with_makefile):
    """AC2: iw approve auto-skips a 'cd <dir>' phantom gate."""
    # Makefile fine; no frontend/ dir
    # Item with qv-gate command 'cd frontend && npx tsc --noEmit'
    # ...
    # Assert step.status == skipped, event.metadata["reason"] == "missing_directory"

def test_iw_approve_does_not_skip_real_gates(testcontainer_session, cli_runner, tmp_project_with_makefile):
    """AC3: real gates are NOT auto-skipped."""
    # Makefile has lint, format-check, type-check, test-unit
    # Item with all four qv-gates pointing at those targets
    # ...
    out = json.loads(result.output)
    assert out["auto_skipped_steps"] == []
    assert session.query(DaemonEvent).filter(
        DaemonEvent.event_type == "step_auto_skipped_phantom_gate"
    ).count() == 0

def test_iw_batch_approve_runs_safety_net(testcontainer_session, cli_runner, tmp_project_with_makefile):
    """AC4: iw batch-approve auto-skips phantom gates that became phantom after item approval."""
    # 1. Create item, write Makefile WITH 'security-sast' target, approve item — no skip.
    # 2. Remove the 'security-sast' target from Makefile (simulates main-branch drift).
    # 3. Create batch including the item, approve batch.
    # 4. Assert the previously-runnable step is now skipped with trigger="batch_approve".

def test_iw_batch_approve_handles_multiple_items(testcontainer_session, cli_runner, tmp_project_with_makefile):
    """Batch with several items, each with mixed phantom/real gates — every phantom skipped."""
```

The test names above are illustrative; choose conventional names that match `tests/integration/`'s style (`grep "^def test_" tests/integration/*.py | head -20` to see patterns).

### 3. Reproducing-test contract (TDD RED)

The integration test `test_iw_approve_auto_skips_phantom_makefile_gate` is the explicit reproducing test. It MUST:

1. **FAIL on `main` before S01's changes** — commit your test, run `git stash`/`git checkout main` for `orch/qv_gate_validator.py` and the two CLI files, run the test, confirm it fails because `s03.status` is still `StepStatus.pending` (no auto-skip). Then restore.
2. **PASS on the post-S01 codebase** — full suite passes.

Document this red-green check briefly in your report.

### 4. Real-fixture honesty

- DO NOT mock `validate_qv_gate` or `auto_skip_phantom_qv_gates` in the integration tests. They MUST run for real against the testcontainer DB. Mocking defeats the purpose.
- DO NOT mock the database. `tests/CLAUDE.md` is explicit: testcontainers only, no in-memory or sqlite substitutes.

## Project Conventions

Read `tests/CLAUDE.md` and `orch/CLAUDE.md`. Key constraints:

- Replace `psycopg2` URLs with `psycopg`: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` after testcontainer URL retrieval.
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` — your fixture should already do this; if not, copy the pattern from existing integration tests.
- Use `monkeypatch.delenv()` for clearing env, NEVER `importlib.reload(orch.config)`.
- `DaemonEvent.metadata` is `event_metadata` in Python.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting drift; re-stage the diff if anything changed.
2. `make type-check` — zero errors involving your new test files.
3. `make lint` — zero errors.

Populate the `preflight` object in your result contract.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` — your unit tests are part of this and must all pass.
2. `make test-integration` — your integration tests are part of this and must all pass.
3. Do NOT report `tests_passed: true` unless BOTH suites pass cleanly.
4. If any test is flaky (passes/fails non-deterministically), STOP and fix the flakiness — do not paper over it with retries or `pytest.mark.flaky`.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_qv_gate_validator.py",
    "tests/integration/test_phantom_gate_auto_skip.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Confirm RED-GREEN check on the reproducing test."
}
```
