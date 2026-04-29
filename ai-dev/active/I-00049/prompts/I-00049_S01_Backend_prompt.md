# I-00049_S01_Backend_prompt

**Work Item**: I-00049 — Daemon blocked by synchronous QV baseline gate command pipe deadlock
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database changes are required for this fix.

---

## Input Files

- `ai-dev/active/I-00049/I-00049_Issue_Design.md` — Design document (read this first)
- `orch/daemon/batch_manager.py` — contains `_run_gate_command` (line ~722)
- `orch/daemon/qv_baseline.py` — contains `GATE_PARSERS` (line ~224)

## Output Files

- `ai-dev/active/I-00049/reports/I-00049_S01_Backend_report.md` — Step report

---

## Context

You are fixing a daemon freeze bug in `_run_gate_command` and removing
`integration-tests` from the QV baseline gate registry.

The daemon is single-threaded. When `_run_gate_command` runs a gate command
that spawns grandchild processes (e.g. `make test-integration` starts
testcontainers), those grandchildren inherit the stdout/stderr pipe FDs that
`subprocess.run(capture_output=True)` opened. Killing the shell on timeout
leaves those FDs open, causing Python's `communicate()` to block indefinitely
— the daemon freezes completely.

Read the full Root Cause Analysis in the design document before implementing.

---

## Requirements

### 1. Fix `_run_gate_command` in `orch/daemon/batch_manager.py`

Replace the current `subprocess.run` call (line ~724) with `subprocess.Popen`
using `start_new_session=True` to put the process in its own session/process
group. Handle timeout by killing the **entire process group** before draining
pipes.

**Exact implementation pattern**:

```python
def _run_gate_command(self, command: str, worktree_path: str, gate: str) -> str:  # noqa: ARG002
    """Run a gate command and return combined stdout+stderr.

    Uses start_new_session=True so the shell and all its descendants share
    a new process group. On TimeoutExpired the entire group is SIGKILL'd
    before draining pipes, preventing the FD-inheritance deadlock that
    blocks the daemon thread indefinitely.
    """
    import os
    import signal

    with subprocess.Popen(  # noqa: S602
        command,
        shell=True,
        cwd=worktree_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=_agent_subprocess_env(),
    ) as proc:
        try:
            stdout, stderr = proc.communicate(timeout=300)
            return stdout.decode(errors="replace") + stderr.decode(errors="replace")
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, stderr = proc.communicate()
            return stdout.decode(errors="replace") + stderr.decode(errors="replace")
```

**Key decisions** (do not deviate without strong justification):
- `start_new_session=True` — creates a new process group; all grandchildren
  join it automatically, so a single `os.killpg` reaches the entire tree.
- `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` — kills the whole group.
  Catch `ProcessLookupError` in case the process already exited.
- After `killpg`, call `proc.communicate()` **without** a timeout to drain
  any buffered output and avoid `ResourceWarning` on the open pipes.
- Do NOT raise on timeout — return whatever output was captured so
  `_compute_qv_baselines` can still log/store a partial result.
- Remove the `# noqa: S603` comment from the old call if present; add
  `# noqa: S602` for the new `Popen(shell=True)`.

### 2. Remove `"integration-tests"` from `GATE_PARSERS` in `orch/daemon/qv_baseline.py`

`integration-tests` runs testcontainers and can take minutes — it must never
be scheduled as a baseline gate during worktree setup.

Change `GATE_PARSERS` from:

```python
GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "integration-tests": parse_pytest,
    "frontend-tests": parse_pytest,
}
```

To:

```python
GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "frontend-tests": parse_pytest,
}
```

No other changes to `qv_baseline.py` are needed. The existing "Unknown gate"
code path in `_compute_qv_baselines` will log a warning and skip the gate.

---

## Project Conventions

Read `CLAUDE.md` for all project conventions. Key rules for this fix:
- No new imports at the top of the function — use `import os` and
  `import signal` inside the function body OR add them to the module-level
  imports at the top of `batch_manager.py` (check if `os` and `signal` are
  already imported).
- Follow existing `subprocess` noqa patterns in the file.
- `subprocess` is already imported at module level in `batch_manager.py`.

---

## TDD Requirement

This is a bug fix. The Tests step (S03) will write the formal reproduction
test. Your job here is to make the implementation correct and verify it
doesn't regress existing unit tests.

**Before reporting complete, run**:
```bash
make test-unit
make lint
make typecheck
```

All must pass with zero errors/failures in the files you touched.

---

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors

---

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00049",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/batch_manager.py",
    "orch/daemon/qv_baseline.py"
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
