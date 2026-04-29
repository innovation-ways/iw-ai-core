# I-00052: E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-29
**Reported By**: iw-item-analyze (post-execution analysis of F-00067, finding [5])
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

No database schema changes required for this fix.

## Description

When a browser-verification step's E2E dashboard container exits with code 1 during bring-up, the daemon records `StepRun.error_message = "browser env setup failed: <compose event stream>"`. The compose event stream shows container lifecycle events (Starting → Started → Waiting → Error dependency failed) but not the container's own application stderr. The root cause of the crash (an `ImportError`, a failed Alembic migration, a misconfigured env var) is only visible in `docker logs <container_name>` — which the daemon never captures. Fix-cycle agents are completely blind to the cause and cannot fix it.

In F-00067 S17, runs 2, 3, 4, and 6 all failed with the same opaque "browser env setup failed: … e2e-dashboard-1 exited (1)" message. Four runs of fix-cycle budget were consumed with zero actionable signal.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The fix is in `orch/daemon/browser_env.py` (new helper) and `orch/daemon/batch_manager.py` (call site). No DB schema changes.

The `docker logs` command is **read-only introspection** and is explicitly in the allowed-exceptions list. Using `subprocess.run(["docker", "logs", ...])` in daemon code is permitted for this purpose.

## Steps to Reproduce

1. Run a browser-verification step against a worktree whose dashboard image fails to start (e.g., the worktree has a Python import error introduced by a fix-cycle agent).
2. The daemon calls `run_env_up_hook` → `docker compose up` exits non-zero.
3. `batch_manager.py:892` reads the last 20 lines of the compose log and sets `error_msg = f"browser env setup failed: {log_tail}"`.
4. The compose log contains only: `"Container … Error dependency e2e-dashboard failed to start\ndependency failed to start: container … exited (1)"`.
5. The fix-cycle agent receives an `error_message` with no traceback, no `ImportError`, no exception — only the compose lifecycle events.

**Expected**: `StepRun.error_message` includes a "Container crash log" section with the last 50 lines of `docker logs <crashed_container>` appended after the compose output.

**Actual**: `StepRun.error_message` contains only the compose event stream. The container's application stderr is never captured.

## Root Cause Analysis

`orch/daemon/batch_manager.py:884–892`:

```python
if not success:
    log_tail = ""
    if log_path and log_path.exists():
        lines = log_path.read_text(errors="replace").splitlines()
        log_tail = "\n".join(lines[-20:])
    error_msg = f"browser env setup failed: {log_tail}"
```

`log_path` is the compose command's stdout/stderr (written by `run_env_up_hook`). This log contains Docker Compose's orchestration output — not container application logs. After a container crashes, compose emits `"dependency failed to start: container <name> exited (1)"`. The application's own traceback is only retrievable via `docker logs <name>`, which is never called.

The fix adds:
1. A helper `_capture_crashed_container_logs(compose_log: str) -> str` in `orch/daemon/browser_env.py` that:
   - Parses the compose output for lines matching `"exited (1)"` to extract container names
   - Runs `docker logs <name> --tail 50` (read-only; non-blocking; ignores failures)
   - Returns the combined crash logs as a formatted string
2. A call to this helper in `batch_manager.py:892`, appending its output to `error_msg`

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Compose failure handler | `orch/daemon/batch_manager.py:884–897` | Builds `error_msg` without container logs |
| Browser env module | `orch/daemon/browser_env.py` | Missing `_capture_crashed_container_logs` helper |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Add `_capture_crashed_container_logs` to `browser_env.py`; call it in `batch_manager.py` | — |
| S02 | CodeReview_Backend | Review S01 | — |
| S03 | Tests | Unit tests for `_capture_crashed_container_logs` | — |
| S04 | CodeReview_Tests | Review S03 | — |
| S05 | CodeReview_Final | Global review | — |
| S06 | QvGate lint | `make lint` | — |
| S07 | QvGate format | `make format-check` | — |
| S08 | QvGate typecheck | `make typecheck` | — |
| S09 | QvGate unit-tests | `make test-unit` | — |
| S10 | QvGate integration-tests | `make allure-integration` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None — `StepRun.error_message` is an existing `Text` column, no schema change needed

### Code Changes

**`orch/daemon/browser_env.py`** — add helper after `run_env_up_hook`:

```python
def _capture_crashed_container_logs(compose_log: str, tail: int = 50) -> str:
    """Parse compose output for exited containers and capture their docker logs.

    Returns a formatted string ready to append to StepRun.error_message.
    Never raises — all failures are silently ignored so a logging failure
    cannot block the step-failure recording path.
    """
    import re
    # Match lines like:
    #   "dependency failed to start: container <name> exited (1)"
    pattern = re.compile(r"container\s+([\w\-]+)\s+exited\s+\(\d+\)", re.IGNORECASE)
    container_names = list(dict.fromkeys(pattern.findall(compose_log)))  # deduplicate, preserve order
    if not container_names:
        return ""

    parts: list[str] = []
    for name in container_names:
        try:
            result = subprocess.run(  # noqa: S603
                ["docker", "logs", name, "--tail", str(tail)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            combined = (result.stdout + result.stderr).strip()
            if combined:
                parts.append(f"### docker logs {name} (last {tail} lines)\n\n{combined}")
        except Exception:  # noqa: BLE001
            parts.append(f"### docker logs {name}\n\n(unavailable — docker logs failed)")
    if not parts:
        return ""
    return "\n\n## Container Crash Logs\n\n" + "\n\n".join(parts)
```

**`orch/daemon/batch_manager.py:887–892`** — append crash logs to `error_msg`:

```python
log_tail = ""
container_crash_logs = ""
if log_path and log_path.exists():
    compose_output = log_path.read_text(errors="replace")
    lines = compose_output.splitlines()
    log_tail = "\n".join(lines[-20:])
    container_crash_logs = browser_env._capture_crashed_container_logs(compose_output)
error_msg = f"browser env setup failed: {log_tail}{container_crash_logs}"
```

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00052_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00052_S01_Backend_prompt.md` | Prompt | Implement the fix |
| `prompts/I-00052_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00052_S03_Tests_prompt.md` | Prompt | Unit tests |
| `prompts/I-00052_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00052_S05_CodeReview_Final_prompt.md` | Prompt | Global review |

## Test to Reproduce

```python
def test_i00052_capture_crashed_container_logs_extracts_names():
    """_capture_crashed_container_logs must parse container names from compose output.

    This test should FAIL before the fix (function does not exist)
    and PASS after the fix.
    """
    from orch.daemon.browser_env import _capture_crashed_container_logs

    compose_log = (
        "Container iw-ai-core-e2e-f00067-e2e-dashboard-1 Started\n"
        "Container iw-ai-core-e2e-f00067-e2e-dashboard-1 Waiting\n"
        "dependency failed to start: container "
        "iw-ai-core-e2e-f00067-e2e-dashboard-1 exited (1)\n"
    )

    # Mock docker logs to return a fake traceback
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout="ImportError: cannot import name 'foo' from 'bar'\n",
            stderr="",
            returncode=0,
        )
        result = _capture_crashed_container_logs(compose_log)

    # Assert: container name extracted, docker logs called, output in result
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "iw-ai-core-e2e-f00067-e2e-dashboard-1" in call_args
    assert "docker" in call_args
    assert "logs" in call_args

    # Semantic: the crash log content appears in the result
    assert "ImportError" in result
    assert "Container Crash Logs" in result
```

## Acceptance Criteria

### AC1: Container crash logs appear in error_message

```
Given a browser-verification step where the E2E dashboard container exits (1)
When run_env_up_hook returns False and batch_manager records the StepRun
Then StepRun.error_message contains a "Container Crash Logs" section
 AND that section includes output from `docker logs <crashed_container> --tail 50`
```

### AC2: Safe fallback when docker logs unavailable

```
Given _capture_crashed_container_logs is called
AND docker is not available or docker logs times out
When the function runs
Then it returns an "(unavailable — docker logs failed)" note
 AND does NOT raise an exception
 AND the StepRun is still recorded normally
```

### AC3: No-op when no container name in compose output

```
Given compose output that contains no "exited (N)" lines
When _capture_crashed_container_logs is called
Then it returns an empty string
 AND no subprocess is spawned
```

## Regression Prevention

- `_capture_crashed_container_logs` is written to never raise — all `subprocess` calls are wrapped in `except Exception`. This ensures that a failure to capture docker logs cannot block the step-failure recording path.
- Unit tests cover the parse logic independently of a live Docker daemon (using `unittest.mock.patch`).
- The helper is pure in its parse step: extraction and subprocess call are separate so the regex can be tested in isolation.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Reproducing test**: Unit test calling `_capture_crashed_container_logs` with a sample compose log containing `"exited (1)"`. Before the fix, the function does not exist → `ImportError` (FAIL). After: parses name, calls `docker logs`, returns formatted string (PASS).
- **Unit tests**: Parse logic (no subprocess mock), subprocess mock for docker logs success, subprocess mock for docker logs failure (timeout/exception → safe fallback), empty input → empty output.
- **Integration tests**: Not applicable — `docker logs` requires a live container; the unit test with mocks is sufficient.

## Notes

- `subprocess.run(["docker", "logs", ...])` is **read-only introspection** explicitly allowed by the CLAUDE.md constraints. `docker logs` does not change container/volume/network state.
- `tail=50` is chosen to balance context vs. `error_message` column size. The `Text` column has no length limit in PostgreSQL.
- The helper uses `noqa: S603` because the command list is constructed from parsed compose output, not user input. The compose output is daemon-controlled (comes from `docker compose up` stdout).
- Deduplication in `_capture_crashed_container_logs` uses `dict.fromkeys()` to preserve order while removing duplicate container names (compose may log the same container multiple times).
