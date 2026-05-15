# F-00083 S01 — Backend Report

**Step**: S01 (backend-impl)
**Status**: complete

## What was done

Implemented the managed `opencode serve` subprocess manager for the Dashboard
AI Assistant. The lifecycle is owned by a single `OpencodeRuntime` instance:
generate per-startup password, spawn the binary, health-poll
`GET /global/health`, terminate cleanly (SIGTERM → SIGKILL escalation), and
auto-restart on crash with a 3-restarts-per-60-s cap.

The TDD-RED phase produced 7 tests written before any implementation; the
captured RED was `AttributeError: module 'orch.chat.opencode_runtime' has no
attribute 'sys'` (the first patched attribute that the stub class lacked).
Implementation then drove all tests to GREEN.

### Notable design choices

- **`OpencodeRuntime` owns a single persistent `httpx.AsyncClient`** instead of
  creating a fresh client per probe. This makes the test fakes simpler (no
  async context-manager protocol needed on the mock) and reduces per-probe
  overhead. The client is closed on `stop()`.
- **Timing knobs are constructor parameters** (`restart_backoff_seconds`,
  `health_poll_interval_seconds`, `stop_grace_seconds`,
  `health_timeout_seconds`). Originally I patched `asyncio.sleep` globally in
  the tests — that subtly broke the test harness because the test's own
  `await asyncio.sleep(0)` yield points also became no-ops, freezing the
  scheduler from running the watchdog. Replacing the global patch with
  dependency-injected delays produced a deterministic, fast test for the
  crash-cap path.
- **`PR_SET_PDEATHSIG`** is wired via `ctypes.CDLL("libc.so.6").prctl(1, SIGTERM)`
  in a Linux-only `preexec_fn`; non-Linux platforms log INFO and skip silently.
- **Password handling**: generated via `secrets.token_urlsafe(32)`, stored only
  in `self._password`, injected as `OPENCODE_SERVER_PASSWORD` in the child env.
  Log messages cite only the port and a redacted indicator
  (`"auth: <redacted 32B token>"`). `test_password_not_logged` enforces this
  invariant against `caplog`.
- **Auto-restart cap**: a `deque(maxlen=4)` keeps the most-recent timestamps;
  on each crash the watchdog filters to entries within the 60-s window. Once
  `> 3`, it logs CRITICAL with the literal "OpenCode runtime is unstable;
  chat disabled" and flips `_healthy = False` permanently.
- **Password is preserved across auto-restarts** so the persistent client's
  auth header keeps working. (Generating a fresh password per restart would
  invalidate already-open browser sessions even though the agent itself
  recovered.)

## Files changed

- `orch/chat/__init__.py` *(new)* — package marker, exports `OpencodeRuntime`.
- `orch/chat/opencode_runtime.py` *(new)* — subprocess manager (~280 lines).
- `orch/config.py` — added `opencode_port: int = 4096` and
  `opencode_bin: str = "opencode"` fields to `DaemonConfig`; threaded through
  `load_config()` reading `IW_CORE_OPENCODE_PORT` / `IW_CORE_OPENCODE_BIN`.
- `.env.example` — documented the two new env vars under a
  "Dashboard AI Assistant (F-00083)" section.
- `pyproject.toml` — added `httpx>=0.27` and `httpx-sse>=0.4,<0.5` to runtime
  deps. (`httpx` was previously only in the dev group; promoted because
  `orch.chat` imports it at runtime. `httpx-sse` is the S02 client dep but
  declared here per the prompt.)
- `tests/unit/test_chat_runtime.py` *(new)* — 8 tests (7 spec + 1 sanity).

## Preflight gates

| Gate | Result |
|------|--------|
| `make format` | ok — 693 files already formatted |
| `make typecheck` | ok — `Success: no issues found in 244 source files` |
| `make lint` | ok — `All checks passed!` |

## Test results

```
$ uv run pytest tests/unit/test_chat_runtime.py -v --no-cov
============================= test session starts ==============================
collected 8 items

tests/unit/test_chat_runtime.py::test_start_health_stop_happy_path PASSED [ 12%]
tests/unit/test_chat_runtime.py::test_start_health_timeout_raises PASSED [ 25%]
tests/unit/test_chat_runtime.py::test_stop_sigterm_then_sigkill PASSED   [ 37%]
tests/unit/test_chat_runtime.py::test_password_not_logged PASSED         [ 50%]
tests/unit/test_chat_runtime.py::test_missing_binary_clear_error PASSED  [ 62%]
tests/unit/test_chat_runtime.py::test_restart_on_crash_capped_at_3_per_60s PASSED [ 75%]
tests/unit/test_chat_runtime.py::test_pr_set_pdeathsig_set_on_linux PASSED [ 87%]
tests/unit/test_chat_runtime.py::test_python_version_is_compatible PASSED [100%]

============================== 8 passed in 0.17s ===============================
```

### TDD-RED evidence

After writing tests but before implementation, the canonical RED was:

```
tests/unit/test_chat_runtime.py::test_start_health_stop_happy_path FAILED
> AttributeError: module 'orch.chat.opencode_runtime' has no attribute 'sys'
```

This is the valid RED state per the prompt's contract — not an `ImportError`
nor a collection error.

## Issues / observations

- The hardest debugging step was diagnosing why the watchdog appeared to hang
  inside the crash-cap test. Root cause: `patch("...asyncio.sleep", new_callable=AsyncMock)`
  modifies `asyncio.sleep` globally for the duration of the `with` block —
  including the test's own `await asyncio.sleep(0)` calls used to yield to the
  watchdog. Solution: do not patch `asyncio.sleep`; instead inject the relevant
  delays through constructor parameters. This is also a more honest test
  because production `asyncio.sleep` semantics are preserved.
- `httpx-sse 0.4.3` resolved cleanly against the existing `httpx>=0.27` pin
  (it supports httpx 0.27–0.x; future httpx 1.x will need a bump).
- The runtime intentionally does NOT register itself in the FastAPI lifespan
  here — S03 owns the dashboard wiring. S01 ships only the standalone class
  and config plumbing.
- `dashboard/CLAUDE.md` was not modified; S03 will add the chat router and
  document it there.
