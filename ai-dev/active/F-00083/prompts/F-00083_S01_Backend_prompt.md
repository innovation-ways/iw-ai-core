# F-00083_S01_Backend_prompt

**Work Item**: F-00083 -- Dashboard AI Assistant — OpenCode-backed chat panel (v1)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt. Allowed exceptions: testcontainers, read-only introspection, `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md)

## ⛔ Migrations: agents generate, daemon applies

This step does **NOT** generate or apply migrations. This feature has no DB schema changes.

## Input Files

- `ai-dev/active/F-00083/F-00083_Feature_Design.md` — Design (Sections: Scope, Implementation Plan, Invariants 4, 5, Boundary Behavior rows on subprocess crash / missing binary / config missing)
- `docs/research/R-00074-minimal-v1-dashboard-chat.md` §2 — minimal subprocess-manager sketch (use as the structural reference, not a copy-paste)
- `orch/config.py` — current config loader pattern
- `pyproject.toml` — current deps

## Output Files

- `ai-dev/work/F-00083/reports/F-00083_S01_Backend_report.md`
- `orch/chat/__init__.py` (new package)
- `orch/chat/opencode_runtime.py` (new — subprocess manager)
- `orch/config.py` (modified — add `opencode_port`, `opencode_bin` fields)
- `.env.example` (modified — document the new env vars)
- `pyproject.toml` (modified IFF `httpx-sse` is not already a dependency)
- `tests/unit/test_chat_runtime.py` (new — TDD-RED tests)

## Context

You are implementing the **subprocess manager** for OpenCode. This is the foundation of the Dashboard AI Assistant — every other layer talks to OpenCode through HTTP, but only this module owns the lifecycle (start, stop, health, crash-restart).

Read the design first, then `CLAUDE.md` and `orch/CLAUDE.md`.

## Requirements

### 1. `orch/chat/opencode_runtime.py`

Implement a single class `OpencodeRuntime` with this surface:

```python
class OpencodeRuntime:
    def __init__(self, repo_root: Path, port: int = 4096, bin_path: str = "opencode") -> None: ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def health(self) -> bool: ...
    @property
    def base_url(self) -> str: ...
    @property
    def password(self) -> str: ...
```

Semantics:

- `start()` generates a fresh 32-byte URL-safe password via `secrets.token_urlsafe(32)` and stores it in `self._password` (private attribute). Spawns `opencode serve --hostname 127.0.0.1 --port <port>` with `OPENCODE_SERVER_PASSWORD=<generated>` in the env. Stdout to `DEVNULL`, stderr captured via pipe and logged at WARNING when non-empty.
- On Linux, set `preexec_fn` so the child dies with the parent: `prctl(PR_SET_PDEATHSIG, SIGTERM)`. Use `ctypes` to call the syscall (no extra dep). On non-Linux platforms, skip silently — log INFO that PR_SET_PDEATHSIG is unavailable.
- Health-poll `GET /global/health` (Basic auth: `opencode:<password>`) until 200 or 10 s timeout. Raise `RuntimeError("opencode failed to become healthy within 10s")` on timeout.
- `stop()` sends SIGTERM, awaits up to 5 s, then SIGKILL. Cleans up zombie process if any.
- `health()` is a one-shot probe of `GET /global/health` returning bool.
- **Auto-restart on crash**: a background asyncio task observes `self._proc.wait()`; if it returns non-zero before `stop()` was called, log ERROR, sleep 1 s, call `start()` again. Cap at 3 restarts in 60 s — beyond that, log CRITICAL "OpenCode runtime is unstable; chat disabled" and set `self._healthy = False`. Subsequent `health()` calls return False.
- **The password is NEVER logged, NEVER written to disk, NEVER passed to subprocess stdout/stderr.** Keep it in `self._password` only. Logging the runtime should never include the password — write log messages that name the *port* and a *redacted indicator* like "auth: <redacted 32B token>".

### 2. `orch/config.py` additions

Add two new fields to the config dataclass:

- `opencode_port: int = 4096` — read from `IW_CORE_OPENCODE_PORT` env var.
- `opencode_bin: str = "opencode"` — read from `IW_CORE_OPENCODE_BIN` env var (e.g., `/usr/local/bin/opencode` or just `opencode` for PATH resolution).

Match the existing config style exactly. Update `.env.example` with the two new vars and one-line descriptions.

### 3. `pyproject.toml` — add `httpx-sse` if missing

Grep `pyproject.toml` for `httpx-sse` or `httpx_sse`. If absent, add it under the project's existing httpx pin. The version range that works with httpx 0.x is `httpx-sse>=0.4,<0.5`. **Verify the project's httpx version is compatible before adding.**

### 4. TDD-RED tests (`tests/unit/test_chat_runtime.py`)

Write tests FIRST:

- `test_start_health_stop_happy_path` — fakes `asyncio.create_subprocess_exec` to return a stub process whose stdout-pipe-equivalent returns a 200 for `/global/health`. Asserts `start()` returns within timeout, `health()` returns True, `stop()` cleans up.
- `test_start_health_timeout_raises` — fake never returns 200. Assert `RuntimeError` with the documented message.
- `test_stop_sigterm_then_sigkill` — fake ignores SIGTERM. Assert SIGKILL is called after 5 s (with a shortened timeout in the test via dependency injection or `asyncio.wait_for`).
- `test_password_not_logged` — `caplog` captures everything emitted during start. Assert the password literal does NOT appear in any log record.
- `test_missing_binary_clear_error` — set `bin_path="/does/not/exist/opencode"`. Assert `FileNotFoundError` or a wrapped `RuntimeError` with a clear message.
- `test_restart_on_crash_capped_at_3_per_60s` — drive the subprocess wait to immediately return non-zero. Assert 3 restarts then `health()` returns False and a CRITICAL log is emitted. Use a clock-injection fixture for the 60-s window.
- `test_pr_set_pdeathsig_set_on_linux` — patch `sys.platform` and `ctypes`. Assert `prctl` is called with PR_SET_PDEATHSIG and SIGTERM on linux; skipped on darwin/win32.

**RED phase**: run only the new file (`uv run pytest tests/unit/test_chat_runtime.py -v`), confirm failures are `ImportError` (orch.chat module doesn't exist yet — FIXTURE error, not RED) BEFORE you write the module, then write a skeleton `orch/chat/opencode_runtime.py` with `class OpencodeRuntime: pass` and re-run. **The valid RED state is**: `AttributeError: 'OpencodeRuntime' object has no attribute 'start'` or `AssertionError`. Capture one of those for `tdd_red_evidence`.

## Project Conventions

Read `orch/CLAUDE.md`:
- SQLAlchemy 2.0 sync style elsewhere; this module uses **asyncio** because of subprocess management — that's fine; we don't talk to the DB here.
- Logging via `logging.getLogger(__name__)`; never `print`.
- Type hints required; `from __future__ import annotations` at top.

## TDD Requirement

RED-first per template. `tdd_red_evidence` MUST be `AttributeError`/`AssertionError`/`NotImplementedError`, not `ImportError` or collection error.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

Targeted only: `uv run pytest tests/unit/test_chat_runtime.py -v`. Do NOT run `make test-unit` (S14 QV gate).

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00083",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/chat/__init__.py",
    "orch/chat/opencode_runtime.py",
    "orch/config.py",
    ".env.example",
    "pyproject.toml",
    "tests/unit/test_chat_runtime.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "7 passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_chat_runtime.py::test_start_health_stop_happy_path — AttributeError: 'OpencodeRuntime' object has no attribute 'start' (captured before implementation)",
  "blockers": [],
  "notes": "httpx-sse: {already-present | added vX.Y}. PR_SET_PDEATHSIG verified on Linux test path."
}
```
