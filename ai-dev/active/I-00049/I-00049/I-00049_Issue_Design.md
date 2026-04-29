# I-00049: Daemon blocked by synchronous QV baseline gate command pipe deadlock

**Type**: Issue
**Severity**: High
**Created**: 2026-04-29
**Reported By**: operator (observed during F-00065 worktree setup)
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database schema changes are required for this fix.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

`_compute_qv_baselines` in `orch/daemon/batch_manager.py` runs quality-gate
commands (e.g. `make test-integration`) synchronously on the daemon's single
main thread using `subprocess.run(..., capture_output=True, timeout=300)`.
When a gate command spawns long-lived grandchild processes that inherit the
stdout/stderr pipe file descriptors, killing the shell on timeout does not
close those FDs — Python's `communicate()` then blocks indefinitely waiting
for all pipe readers to close, freezing the daemon completely. Additionally,
`integration-tests` is registered in `GATE_PARSERS` as a valid baseline gate,
allowing `make test-integration` (which starts testcontainers) to be
scheduled as a baseline check — an operation far too slow for daemon setup.

## Project Context

Read `CLAUDE.md` for architecture, conventions, and hard rules. Key points:
- The daemon is a single-threaded polling loop (`orch/daemon/main.py`)
- `orch/daemon/batch_manager.py` contains the worktree setup and QV baseline logic
- `orch/daemon/qv_baseline.py` defines `GATE_PARSERS` (gate name → fingerprint parser)
- Unit tests live in `tests/unit/`; use `make test-unit` to run them
- NEVER connect tests to the live DB; testcontainers only for integration tests

## Steps to Reproduce

1. Register a work item that has a `quality_validation` step with gate `integration-tests`
2. Approve the work item and create a batch
3. Daemon begins worktree setup → calls `_compute_qv_baselines`
4. `_run_gate_command` spawns `make test-integration` (starts testcontainers, subprocesses)
5. After 300 s the timeout fires; Python kills `/bin/sh -c make test-integration`
6. Testcontainer grandchildren keep the pipe FDs open; `communicate()` blocks forever
7. Daemon thread is frozen — no poll cycles, no step launches, no heartbeats

**Expected**: Gate command times out cleanly in ≤ 300 s; daemon continues normally.

**Actual**: Daemon blocks indefinitely (observed: 5+ minutes) until an operator
manually kills the subprocess tree. All other projects and batches stall silently.

## Root Cause Analysis

### Bug 1 — Pipe deadlock on timeout (`orch/daemon/batch_manager.py:724`)

```python
result = subprocess.run(
    command,
    shell=True,
    cwd=worktree_path,
    capture_output=True,   # ← opens pipes; grandchildren inherit them
    text=True,
    timeout=300,
    env=_agent_subprocess_env(),
)
```

`subprocess.run` with `capture_output=True` creates stdout/stderr pipes and
calls `proc.communicate()` to drain them. With `shell=True`, the direct child
is `/bin/sh`; `make`, testcontainers, and their subprocesses are grandchildren
that inherit the open pipe FDs. When the 300 s timeout fires, `subprocess.run`
calls `proc.kill()` (SIGKILL) on the shell only — grandchildren survive with
the pipe FDs still open. The subsequent `proc.communicate()` (pipe drain) then
blocks until every reader closes those FDs, which never happens.

**Fix**: Replace `subprocess.run` with `subprocess.Popen` using
`start_new_session=True` (puts the shell in a new process group). On
`TimeoutExpired`, kill the entire process group with `os.killpg` before
draining, guaranteeing all grandchildren receive SIGKILL and the pipes close.

### Bug 2 — `integration-tests` in `GATE_PARSERS` (`orch/daemon/qv_baseline.py:228`)

```python
GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "integration-tests": parse_pytest,   # ← should not run at worktree setup time
    "frontend-tests": parse_pytest,
}
```

Integration tests spin up testcontainers and can take minutes. Running them
during every worktree baseline setup is impractical and is what triggered
Bug 1 in the first place.

**Fix**: Remove `"integration-tests"` from `GATE_PARSERS`. The existing
"Unknown gate" code path in `_compute_qv_baselines` will log a debug-level
notice and skip that gate safely.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Daemon gate runner | `orch/daemon/batch_manager.py:722-733` | Pipe deadlock on timeout; daemon frozen |
| QV baseline gate registry | `orch/daemon/qv_baseline.py:224-230` | `integration-tests` scheduled as baseline gate |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Fix `_run_gate_command` (process-group kill) + remove `integration-tests` from `GATE_PARSERS` | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `tests-impl` | Reproduction test + regression tests | — |
| S04 | `code-review-impl` | Review S03 | — |
| S05 | `code-review-final-impl` | Global cross-agent review | — |
| S06 | `qv-gate` | lint — `make lint` | — |
| S07 | `qv-gate` | format — `make format` | — |
| S08 | `qv-gate` | typecheck — `make typecheck` | — |
| S09 | `qv-gate` | unit-tests — `make test-unit` | — |
| S10 | `qv-gate` | integration-tests — `make allure-integration` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**:
  - `orch/daemon/batch_manager.py` — replace `subprocess.run` in `_run_gate_command` with `Popen` + process-group kill
  - `orch/daemon/qv_baseline.py` — remove `"integration-tests"` entry from `GATE_PARSERS`
- **Nature of change**: Bug fix — no new public API, no schema changes

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00049/I-00049_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00049/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/I-00049/prompts/I-00049_S01_Backend_prompt.md` | Prompt | Fix implementation |
| `ai-dev/active/I-00049/prompts/I-00049_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `ai-dev/active/I-00049/prompts/I-00049_S03_Tests_prompt.md` | Prompt | Tests |
| `ai-dev/active/I-00049/prompts/I-00049_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `ai-dev/active/I-00049/prompts/I-00049_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Test to Reproduce

```python
def test_i00049_run_gate_command_does_not_block_after_timeout():
    """
    Regression: _run_gate_command must not block indefinitely when a
    subprocess spawns grandchildren that inherit pipe FDs.
    Should FAIL against the old subprocess.run implementation and
    PASS after the Popen + process-group kill fix.
    """
    import time
    from unittest.mock import MagicMock, patch

    from orch.daemon.batch_manager import BatchManager

    # Build a minimal BatchManager instance (no real DB needed)
    config = MagicMock()
    config.baseline_qv_enabled = True
    manager = BatchManager.__new__(BatchManager)
    manager.config = config
    manager.project_id = "test-proj"
    manager.project_config = MagicMock()

    # Command that spawns a grandchild holding the pipe open:
    # sleep keeps the child FD open beyond the parent shell's lifetime
    command = "bash -c 'sleep 600 &' && exit 0"

    start = time.monotonic()
    # With a short timeout the call must return promptly (≤ 5 s)
    try:
        manager._run_gate_command(command, "/tmp", "unit-tests")
    except Exception:
        pass
    elapsed = time.monotonic() - start

    assert elapsed < 5, (
        f"_run_gate_command blocked for {elapsed:.1f}s — "
        "pipe deadlock: grandchild process kept pipe FDs open after timeout"
    )
```

## Acceptance Criteria

### AC1: Bug is fixed — `_run_gate_command` returns promptly on timeout

```
Given a gate command that spawns grandchild processes holding the stdout pipe open
When the command exceeds the configured timeout
Then _run_gate_command returns within 2 s of the timeout expiring
And the daemon main thread is never blocked
```

### AC2: Integration tests excluded from baseline computation

```
Given a work item with a quality_validation step whose gate is "integration-tests"
When _compute_qv_baselines runs
Then the integration-tests gate is skipped (not executed)
And a debug/warning log entry is emitted explaining the skip
```

### AC3: Regression test exists

```
Given the fix is applied
When the unit test suite runs
Then the reproduction test passes
And all existing merge_queue and qv_baseline tests continue to pass
```

## Regression Prevention

1. `_run_gate_command` uses `start_new_session=True` + `os.killpg` — no
   future gate command can leave orphan FD holders that block the daemon.
2. `integration-tests` removed from `GATE_PARSERS` — cannot be accidentally
   re-added without being noticed in code review.
3. Unit test `test_i00049_run_gate_command_does_not_block_after_timeout`
   verifies the non-blocking contract with a real subprocess that spawns a
   grandchild — this test would have caught the original bug.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: `test_i00049_run_gate_command_does_not_block_after_timeout` —
  spawns a command with a background grandchild holding the pipe open; asserts
  the call returns within a tight wall-clock bound.
- **Unit tests**:
  - Process-group kill: verify `os.killpg` is called on `TimeoutExpired`
  - Normal completion: verify output is returned correctly when command exits 0
  - Non-zero exit: verify output is still returned (no exception raised)
  - `integration-tests` exclusion: verify gate is not in `GATE_PARSERS`
- **Integration tests**: Not required — the fix is self-contained in two functions
  with no DB or network interaction.

## Notes

- The `start_new_session=True` approach (setsid) is preferred over
  `os.setpgrp` as `preexec_fn` because it also detaches the process from the
  daemon's controlling terminal, preventing SIGINT propagation on Ctrl-C.
- After `os.killpg(pgid, SIGKILL)`, call `proc.communicate()` (without
  timeout) to drain any remaining buffered output and avoid `ResourceWarning`.
- The "Unknown gate" warning in `_compute_qv_baselines` (line 661) uses
  `logger.warning` — change to `logger.debug` for the `integration-tests`
  case if a separate `BASELINE_EXCLUDED_GATES` set is added, but do not
  over-engineer; removing from `GATE_PARSERS` is sufficient.
