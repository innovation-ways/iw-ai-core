# I-00052_S01_Backend_prompt

**Work Item**: I-00052 — E2E dashboard container crash logs not captured — fix-cycle agents blind to startup failures
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

**EXCEPTION**: `docker logs <name>` is **read-only introspection** and is explicitly
allowed by CLAUDE.md. You WILL call it via `subprocess.run(["docker", "logs", ...])`.
This does not change container state and is the specific fix required by this incident.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00052/I-00052_Issue_Design.md` — full bug description, root cause, exact code to add
- `orch/daemon/browser_env.py` — add `_capture_crashed_container_logs` helper here
- `orch/daemon/batch_manager.py:884–897` — call site to update

## Output Files

- `ai-dev/active/I-00052/reports/I-00052_S01_Backend_report.md` — step report

## Context

When a browser-verification E2E dashboard container exits with code 1, the daemon records a `StepRun.error_message` containing only Docker Compose's lifecycle event stream. The container's own application stderr (the `ImportError`, `alembic` failure, or misconfigured env var that caused the crash) is never captured. Fix-cycle agents are blind to the root cause.

The fix adds a `_capture_crashed_container_logs` helper that parses the compose output for crashed container names and runs `docker logs <name> --tail 50` to retrieve their application stderr. The helper must never raise — it is called on the failure-recording path.

## Requirements

### 1. Add `_capture_crashed_container_logs` to `orch/daemon/browser_env.py`

Add the function after `run_env_up_hook`. The exact implementation is specified in the design document's "Code Changes" section. Key constraints:

- Parse compose output with regex: `r"container\s+([\w\-]+)\s+exited\s+\(\d+\)"` (case-insensitive)
- Deduplicate container names (preserve order)
- For each name: `subprocess.run(["docker", "logs", name, "--tail", "50"], capture_output=True, text=True, timeout=10)`
- Combine stdout + stderr from `docker logs`
- Wrap each container's call in `except Exception` — never raise
- Return empty string when no containers are found or all docker-logs calls fail
- Return a formatted string starting with `"\n\n## Container Crash Logs\n\n"` when logs are found

The `subprocess` module is already imported in `browser_env.py`. Do not add new imports beyond what is already present.

### 2. Update `orch/daemon/batch_manager.py:887–892`

Replace the current `log_tail` / `error_msg` block with:

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

`browser_env` is already imported in `batch_manager.py` — verify with `grep "import browser_env\|from.*browser_env" orch/daemon/batch_manager.py` before adding any import.

### 3. No other changes

Do not modify `run_env_up_hook`, `run_env_down_hook`, or any other function. Scope is strictly the two files listed above.

## TDD Requirement

1. **RED**: Write a unit test in `tests/unit/daemon/` (or `tests/unit/`) that imports `_capture_crashed_container_logs` from `orch.daemon.browser_env`. Before the fix, this raises `ImportError` — the test fails. After the fix, the import succeeds and the test logic runs.
2. **GREEN**: Add the helper. The test must pass.
3. **REFACTOR**: Verify the no-op case (empty compose log → empty string, no subprocess call) also passes.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion, run in order:

1. `uv run ruff format .` — auto-fixes formatting drift; re-stage if files change
2. `make typecheck` — zero errors on files you touched
3. `make lint` — zero errors (pay attention to `S603`, `BLE001` — add `# noqa` as specified in design)

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` after implementation. All tests must pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00052",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/browser_env.py",
    "orch/daemon/batch_manager.py"
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
uv run iw step-done I-00052 --step S01 \
  --report ai-dev/active/I-00052/reports/I-00052_S01_Backend_report.md
```
