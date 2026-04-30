# I-00052_S03_Tests_prompt

**Work Item**: I-00052 — E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Testcontainers (via pytest fixtures) are the ONLY allowed Docker usage. Never run
`docker compose` or raw `docker` commands from test code. Full policy: docs/IW_AI_Core_Agent_Constraints.md

**Note**: The function under test calls `docker logs` via `subprocess.run`. Tests MUST mock
`subprocess.run` — do NOT rely on a live Docker daemon.

## Input Files

- `ai-dev/active/I-00052/I-00052_Issue_Design.md` — bug description, "Test to Reproduce" section, acceptance criteria
- `ai-dev/active/I-00052/reports/I-00052_S01_Backend_report.md` — what was changed
- `orch/daemon/browser_env.py` — `_capture_crashed_container_logs` implementation
- `tests/unit/test_browser_env.py` — existing unit tests for browser_env (add here)
- `tests/CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/I-00052/reports/I-00052_S03_Tests_report.md` — step report

## Context

Write unit tests for `_capture_crashed_container_logs` in `orch/daemon/browser_env`. All tests mock `subprocess.run` — no live Docker daemon required.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

Tests must verify SPECIFIC VALUES, not just presence:

- BAD: `assert result != ""` (only proves non-empty)
- BAD: `assert "docker" in result` (doesn't prove the right content is there)
- GOOD: `assert "ImportError: cannot import name" in result` (specific crash log content)
- GOOD: `assert "Container Crash Logs" in result` (proves the section header is present)
- GOOD: `assert result == ""` for the no-op case (proves exact empty output)
- GOOD: `mock_run.assert_called_once_with(["docker", "logs", "iw-ai-core-e2e-f00067-e2e-dashboard-1", "--tail", "50"], ...)` (proves correct container name and args)

## Requirements

Add all tests to `tests/unit/test_browser_env.py`.

### 1. Reproduction test — happy path (AC1)

`test_i00052_capture_crashed_container_logs_happy_path`:

- Input compose log containing:
  ```
  "dependency failed to start: container iw-ai-core-e2e-f00067-e2e-dashboard-1 exited (1)\n"
  ```
- Mock `subprocess.run` to return `MagicMock(stdout="ImportError: cannot import name 'foo'\n", stderr="", returncode=0)`
- Assert:
  - `mock_run` called with `["docker", "logs", "iw-ai-core-e2e-f00067-e2e-dashboard-1", "--tail", "50"]` (verify exact args)
  - `"ImportError: cannot import name 'foo'"` in result
  - `"Container Crash Logs"` in result
  - `"iw-ai-core-e2e-f00067-e2e-dashboard-1"` in result

### 2. Safe fallback — docker logs raises (AC2)

`test_i00052_capture_crashed_container_logs_docker_unavailable`:

- Input compose log with `"exited (1)"` line
- Mock `subprocess.run` to raise `FileNotFoundError("docker not found")`
- Assert:
  - Function does NOT raise
  - Result is a non-empty string containing `"unavailable"` (the fallback note)

### 3. Safe fallback — docker logs times out (AC2)

`test_i00052_capture_crashed_container_logs_docker_timeout`:

- Mock `subprocess.run` to raise `subprocess.TimeoutExpired(cmd="docker", timeout=10)`
- Assert function does not raise; result contains `"unavailable"`

### 4. No-op — empty compose log (AC3)

`test_i00052_capture_crashed_container_logs_empty_input`:

- Input: `""`
- Assert: result is exactly `""` (empty string)
- Assert: `mock_run` NOT called (use `mock_run.assert_not_called()`)

### 5. No-op — compose log with no "exited" lines (AC3)

`test_i00052_capture_crashed_container_logs_no_crashed_containers`:

- Input: compose log with container start/stop events but no `"exited (1)"` line
- Assert: result is exactly `""`
- Assert: `mock_run` NOT called

### 6. Deduplication — same container mentioned twice

`test_i00052_capture_crashed_container_logs_deduplicates`:

- Input: compose log with `"container foo-dashboard-1 exited (1)"` appearing twice
- Mock `subprocess.run` to return a success result
- Assert: `mock_run` called exactly ONCE (not twice)

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order:

1. `uv run ruff format .` — auto-fixes formatting drift; re-stage if files change
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (ARG001, F811, etc.)

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` after writing tests. All must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00052",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_browser_env.py"
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

Then call:
```bash
uv run iw step-done I-00052 --step S03 \
  --report ai-dev/active/I-00052/reports/I-00052_S03_Tests_report.md
```
