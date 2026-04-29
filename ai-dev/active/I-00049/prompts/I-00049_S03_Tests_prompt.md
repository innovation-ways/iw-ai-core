# I-00049_S03_Tests_prompt

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database changes in this work item.

---

## Input Files

- `ai-dev/active/I-00049/I-00049_Issue_Design.md` — Design document (read first)
- `ai-dev/active/I-00049/reports/I-00049_S01_Backend_report.md` — S01 implementation report
- `orch/daemon/batch_manager.py` — fixed `_run_gate_command`
- `orch/daemon/qv_baseline.py` — fixed `GATE_PARSERS`
- `tests/unit/test_merge_queue.py` — existing tests (do not break these)
- `tests/CLAUDE.md` — test conventions

## Output Files

- `tests/unit/test_i00049_gate_command.py` — New test file
- `ai-dev/active/I-00049/reports/I-00049_S03_Tests_report.md` — Step report

---

## Context

You are writing tests that prove the I-00049 bug is fixed and cannot silently
recur.

**The bug**: `_run_gate_command` used `subprocess.run(capture_output=True)`
which blocks indefinitely when grandchild processes keep pipe FDs open after
the parent shell is killed on timeout.

**The fix**: `Popen(start_new_session=True)` + `os.killpg` on timeout.

**The second fix**: `"integration-tests"` removed from `GATE_PARSERS`.

---

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify **specific, semantic behavior** — not just that a function
ran or returned something truthy.

- BAD: `assert result is not None`
- BAD: `assert elapsed < 99999`  (vacuously true)
- GOOD: `assert elapsed < 5.0, f"blocked for {elapsed:.1f}s — pipe deadlock suspected"`
- GOOD: `assert "integration-tests" not in GATE_PARSERS`

---

## Requirements

### 1. Reproduction test — wall-clock non-blocking contract

Write a test that **would fail** against the old `subprocess.run` code and
**passes** against the fixed `Popen` + `killpg` code.

Strategy: spawn a command that backgrounds a long-running grandchild keeping
the pipe open, then assert `_run_gate_command` returns well within the timeout.
Use a short timeout (e.g. 2 s) so the test completes quickly.

```python
def test_i00049_run_gate_command_does_not_block_after_timeout():
    """
    Regression test for I-00049.
    _run_gate_command must return promptly even when a grandchild process
    keeps the stdout pipe open after the parent shell exits.
    With the old subprocess.run implementation this test would hang.
    """
    import time
    from unittest.mock import MagicMock, patch

    from orch.daemon.batch_manager import BatchManager

    manager = BatchManager.__new__(BatchManager)
    manager.config = MagicMock()
    manager.project_id = "test"
    manager.project_config = MagicMock()

    # Command: parent shell exits immediately, grandchild (sleep 600) stays alive
    # and holds the inherited pipe FDs open.
    command = "bash -c 'sleep 600 &'"

    start = time.monotonic()
    # Patch timeout to 2 s so the test finishes quickly
    with patch.object(
        BatchManager,
        "_run_gate_command",
        wraps=lambda self, cmd, cwd, gate: _run_with_short_timeout(self, cmd, cwd, gate),
    ):
        pass  # see note below

    # Direct approach — monkeypatch the constant
    ...
```

**Important**: Do NOT use the above skeleton verbatim. Instead:
- Monkeypatch the timeout value (e.g. patch `subprocess` or use a helper
  that calls `_run_gate_command` with an injected short timeout), OR
- Subclass/monkey-patch `_run_gate_command` to use `timeout=2` for the test.

The simplest correct approach: patch `subprocess.Popen` with a real Popen
but intercept `communicate(timeout=...)` to use `timeout=2`. Or directly
call the real `_run_gate_command` with a real command and a patched timeout.

Verify: `elapsed < 5.0` with a helpful failure message naming the bug.

### 2. Normal completion returns output

```python
def test_run_gate_command_returns_stdout_on_success():
    """Gate command that exits 0 returns its combined stdout+stderr."""
    ...
    result = manager._run_gate_command("echo hello", "/tmp", "lint")
    assert "hello" in result
```

### 3. Non-zero exit still returns output (no exception)

```python
def test_run_gate_command_returns_output_on_nonzero_exit():
    """Gate command that exits non-zero must return output, not raise."""
    ...
    result = manager._run_gate_command("echo err >&2; exit 1", "/tmp", "lint")
    assert "err" in result
```

### 4. `integration-tests` excluded from GATE_PARSERS

```python
def test_integration_tests_not_in_gate_parsers():
    """integration-tests must not be a registered baseline gate (I-00049)."""
    from orch.daemon.qv_baseline import GATE_PARSERS
    assert "integration-tests" not in GATE_PARSERS, (
        "integration-tests must not run at worktree setup time — "
        "it starts testcontainers and blocks the daemon (I-00049)"
    )
```

### 5. Fast gates still registered

```python
def test_fast_gates_remain_in_gate_parsers():
    """lint, typecheck, unit-tests, frontend-tests must still be registered."""
    from orch.daemon.qv_baseline import GATE_PARSERS
    for gate in ("lint", "typecheck", "unit-tests", "frontend-tests"):
        assert gate in GATE_PARSERS, f"Expected gate '{gate}' to remain in GATE_PARSERS"
```

### 6. Process-group kill is called on timeout (mock-based)

```python
def test_run_gate_command_kills_process_group_on_timeout():
    """On TimeoutExpired, os.killpg must be called with the process group ID."""
    import os
    import signal
    from unittest.mock import MagicMock, patch, call

    # Mock Popen to raise TimeoutExpired on communicate(timeout=...)
    ...
    # Assert os.killpg was called with (pgid, signal.SIGKILL)
```

---

## Test File Location

Place all tests in `tests/unit/test_i00049_gate_command.py`.

Use `pytest` + `unittest.mock`. Do NOT connect to the live DB.
Check `tests/CLAUDE.md` for all conventions.

---

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make test-unit    # all tests must pass
make lint
make typecheck
```

---

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_i00049_gate_command.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
