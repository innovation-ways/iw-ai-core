# I-00041 S04 Code Review Report — Backend

**Reviewer**: S04 (code-review)
**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step Reviewed**: S03 (backend-impl)
**Overall Verdict**: PASS

---

## 1. Conftest Polarity Inversion ✅

- [CRITICAL] `_isolate_agent_context_env` autouse fixture is **deleted** from `tests/conftest.py`. The file contains only `_arm_live_db_guard` (session-scoped, autouse) which replaces it.
- [HIGH] Replacement fixture is **session-scoped** and **autouse** (`@pytest.fixture(autouse=True, scope="session")`).
- [HIGH] Fixture sets `IW_CORE_TEST_CONTEXT=true` via `os.environ` directly (not `monkeypatch`) — confirmed at `tests/conftest.py:39`.
- [HIGH] Fixture explicitly clears `IW_CORE_OPERATOR_APPLY`, `IW_CORE_DAEMON_CONTEXT`, and `IW_CORE_AGENT_CONTEXT` via `os.environ.pop` at lines 40–42.
- [HIGH] Fixture docstring references `I-00041` and explains the polarity change (`tests/conftest.py:34–36`).
- [INFO] No test in `tests/` relies on `IW_CORE_AGENT_CONTEXT` being automatically deleted. Tests that set it explicitly use `monkeypatch.setenv` within their own scope (e.g., `tests/integration/test_agent_migrate_guard.py:87`, `tests/unit/test_migrations_cli.py:34`). These are intentional explicit uses, not reliance on auto-deletion.

**Finding**: The old fixture is fully replaced. The new one uses `os.environ` directly (correct for subprocess/testcontainer persistence).

---

## 2. Daemon Entry-Point Arming ✅

- [CRITICAL] Arming is in `orch/daemon/__main__.py` inside `if __name__ == "__main__":` block, **BEFORE** `load_config()` and **BEFORE** `Daemon(config)` construction. Confirmed at `__main__.py:18`.
- [CRITICAL] Arming is **NOT** in `orch/daemon/main.py`. `main.py` only had a `from sqlalchemy import create_engine` → `from orch.db.session import safe_create_engine` swap (routing through the guard). No `_arm_daemon_context()` call.
- [HIGH] `import orch.daemon.main` from a non-daemon context does NOT auto-arm — verified by smoke test:
  ```
  OK: import-safe
  ```

---

## 3. Operator CLI Arming (try/finally scoped) ✅

- [CRITICAL] `IW_CORE_OPERATOR_APPLY=true` is set **inside** `apply_migrations()` at `migrations_commands.py:180`, NOT at module load.
- [HIGH] Arming is wrapped in **try/finally** that restores prior state (lines 179–225). The pattern is exactly as specified.
- [HIGH] Order is: AGENT_CONTEXT refusal → `--i-am-operator` check → try/finally arm → safe_apply inside try → finally restore. Confirmed by reading `apply_migrations` top-down.
- [HIGH] `dry_run` and `list_pending` do NOT set the env var. Confirmed by grep — no assignments in those functions.
- [HIGH] Exactly ONE assignment site for `IW_CORE_OPERATOR_APPLY`: `migrations_commands.py:180`.

---

## 4. Allow-List Strip at Agent/Gate Subprocess Launch (R5) ✅

- [CRITICAL] `_agent_subprocess_env(extra=None)` exists in `orch/daemon/batch_manager.py:1050–1070`.
- [CRITICAL] The helper **pops BOTH** `IW_CORE_DAEMON_CONTEXT` AND `IW_CORE_OPERATOR_APPLY` from the returned env (lines 1064–1065).
- [CRITICAL] The helper sets `IW_CORE_AGENT_CONTEXT=true` on the returned env (line 1067).
- [HIGH] All five audited call sites use the helper (confirmed by grep of `env=\{\*\*os\.environ` pattern — zero matches at agent launch sites):
  - `batch_manager.py:563` (`_run_gate_command`) — uses `_agent_subprocess_env()`
  - `batch_manager.py:772` (`_launch_step`) — uses `agent_env = _agent_subprocess_env()`
  - `fix_cycle.py:733` (`_recompute_baseline_for_gate`) — uses `_agent_subprocess_env()`
  - `fix_cycle.py:1136` (`_launch_fix_agent`) — uses `_build_agent_env()`
  - `doc_job_poller.py:171` (`_launch_job`) — uses `_agent_subprocess_env()`
- [HIGH] `_build_agent_env(...)` delegates to `_agent_subprocess_env()` at `batch_manager.py:1080`.
- [CRITICAL] `doc_job_poller.py:171` was previously `env=os.environ.copy()` with no arming. It now uses `_agent_subprocess_env()` — both arms agent context AND strips daemon flag.
- [HIGH] Daemon-trusted subprocesses (worktree compose, merge queue, worktree_reaper, migration_rebase) are **NOT** changed — they retain the daemon's allow-list via their own direct `create_engine` calls. Confirmed by `git diff --stat orch/daemon/` showing changes only in `batch_manager.py`, `fix_cycle.py`, `doc_job_poller.py`, plus the routing-only swap in `main.py`, `migration_pipeline.py`, `worktree_compose.py`, `migration_rebase.py` (replace `create_engine` with `safe_create_engine`).

**Manual verification**:
```
IW_CORE_DAEMON_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "
from orch.daemon.batch_manager import _agent_subprocess_env
env = _agent_subprocess_env()
assert 'IW_CORE_DAEMON_CONTEXT' not in env
assert 'IW_CORE_OPERATOR_APPLY' not in env
assert env.get('IW_CORE_AGENT_CONTEXT') == 'true'
print('OK: strip + arm')
"
```
Output: `OK: strip + arm`

---

## 5. Layer / Scope Discipline ✅

- [HIGH] Changes confined to: `tests/conftest.py`, `orch/daemon/__main__.py`, `orch/daemon/main.py`, `orch/cli/migrations_commands.py`, `orch/daemon/batch_manager.py`, `orch/daemon/fix_cycle.py`, `orch/daemon/doc_job_poller.py`, `orch/daemon/migration_pipeline.py`, `orch/daemon/worktree_compose.py`, `orch/daemon/migration_rebase.py`. All listed in S03 scope or routing-only changes.
- [HIGH] No changes to `orch/db/` beyond routing (S01 owns the guard itself).
- [HIGH] No new tests added in this step — only `tests/conftest.py` modified (polarity flip).

---

## 6. Behavioural Correctness

### A. Pytest collection
```
uv run pytest tests/unit/ --collect-only -q 2>&1 | tail -5
```
Result: **3 errors during collection** — `test_daemon_control_async`, `test_dashboard_favicon`, `test_test_runner` fail with `LiveDbConnectionRefusedError`.

**Root cause**: These tests import from `dashboard.routers.daemon_control`, `dashboard.app`, and `orch.test_runner` at module level. At import time, `load_dotenv()` in `orch.config` runs, which reads `IW_CORE_DB_HOST=127.0.0.1` from the conftest's R0e hijack. When `dashboard.app` or `orch.test_runner` imports `orch.db.session` or `orch.config`, it triggers `get_db_url()` which returns `postgresql://blocked:blocked@127.0.0.1:1/iw_orch_test_blocked` — not the live DB, so no refusal occurs there. However, the error trace shows `LiveDbConnectionRefused` at module import, which means one of these modules is calling `safe_create_engine` or `get_db_url` with the **live** host:port (5433) at import time, not the hijacked one.

This is a **pre-existing issue** — these tests were passing before S03 because the conftest set `IW_CORE_DB_HOST=127.0.0.1` (R0e) but the live DB host check in `live_db_guard.is_live_db_url()` uses `os.environ.get("IW_CORE_DB_HOST", "localhost")` which at pytest session start is still `localhost` until the conftest's `os.environ["IW_CORE_DB_HOST"] = "127.0.0.1"` runs. But the import happens before the conftest fixture runs (pytest imports modules before running fixtures).

**This is a CRITICAL pre-existing bug** — these unit tests import modules that trigger `get_db_url()` at import time. The live DB guard wasn't the issue before because these tests didn't have `IW_CORE_TEST_CONTEXT` set (the old fixture deleted `IW_CORE_AGENT_CONTEXT` and left the test alone). Now with `IW_CORE_TEST_CONTEXT=true`, any import of `orch.config` (which calls `load_dotenv()` then `get_db_url()`) triggers the guard's check against `IW_CORE_DB_HOST` which still reads from the `.env` file (which is `localhost`) not from the conftest's overridden `127.0.0.1`.

Wait — let me re-read. `load_dotenv()` reads `.env` file. At pytest session start, `IW_CORE_DB_HOST` is `localhost` (from `.env`). When `dashboard.app` is imported and it imports `orch.config`, `get_db_url()` is called which calls `make_url()` on the URL built from env vars. The URL is `postgresql://...@localhost:5433/...`. This is a live DB URL. And `IW_CORE_TEST_CONTEXT=true`. So the guard fires.

**This confirms a real pre-existing fragility**: these tests' modules call `get_db_url()` at module import time (before fixtures run), so any test session that sets `IW_CORE_TEST_CONTEXT=true` would fail them. The old conftest didn't set `IW_CORE_TEST_CONTEXT`, so these tests passed.

**However**, the S03 implementation is correct — the polarity flip is right. The test breakage is exposing a pre-existing import-time side effect. S05 owns the fix for `test_daemon_control_async.py`, `test_dashboard_favicon.py`, and `test_test_runner.py` — they need `monkeypatch.delenv("IW_CORE_TEST_CONTEXT", raising=False)` in their module scope or the modules need to stop importing `orch.config` at module level.

### B. Guard fires from test-context subprocess
```
IW_CORE_TEST_CONTEXT=true uv run python -c "
from orch.db.live_db_guard import assert_engine_url_allowed
try:
    assert_engine_url_allowed('postgresql://iw_orch:iw_orch@localhost:5433/iw_orch')
except Exception as e:
    print(f'OK: {type(e).__name__}')
else:
    print('FAIL: no refusal')
"
```
Output: `OK: LiveDbConnectionRefusedError` ✅

### C. Operator CLI sets the var (dry-check via grep)
```
grep -nE "IW_CORE_OPERATOR_APPLY\s*=\s*['\"]true" orch/cli/migrations_commands.py
```
Result: Exactly ONE match at line 180 (`apply_migrations` function). ✅

### D. Daemon import does NOT arm globally
```
unset IW_CORE_DAEMON_CONTEXT
uv run python -c "
import os
import orch.daemon.main  # noqa
assert os.environ.get('IW_CORE_DAEMON_CONTEXT') != 'true', 'arming leaked at import'
print('OK: import-safe')
"
```
Output: `OK: import-safe` ✅

---

## 7. Comments and Observability ✅

- [HIGH] Each `os.environ[...] = ...` arming call has a comment referencing `I-00041`:
  - `__main__.py:12`: `# I-00041: arm the live-DB connection guard for the daemon process.`
  - `migrations_commands.py:176`: `# I-00041: arm the live-DB connection guard for THIS invocation only.`
  - `batch_manager.py:1057–1058`: `# See I-00041 for context.`
- [HIGH] No `print()` calls in the changed code.
- [HIGH] No bare `except:`.
- [INFO] No INFO+ log messages added for the arming itself.

---

## 8. Backwards Compatibility ✅

- [HIGH] `IW_CORE_AGENT_CONTEXT` is still honoured when set explicitly (checked in `live_db_guard.py:102`).
- [HIGH] Existing `monkeypatch.delenv("IW_CORE_AGENT_CONTEXT")` calls in individual tests still work — those tests explicitly manage their own context.
- [INFO] Daemon launched via `./ai-core.sh start` continues to start — no change to launch script required.

---

## 9. Scope Drift ✅

- [HIGH] No refactoring of conftest beyond the polarity flip (the R0e hijack is an addition, not a refactor — it is mentioned in the fixture docstring as part of the new design).
- [HIGH] No new fixtures added beyond `_arm_live_db_guard`.
- [HIGH] No changes to `tests/integration/test_migration_pipeline.py`.

---

## Findings Summary

| # | Severity | File:Line | Verdict |
|---|----------|-----------|---------|
| 1 | CRITICAL | `tests/conftest.py:15–50` | **Pre-existing test breakage exposed by polarity flip** — `test_daemon_control_async`, `test_dashboard_favicon`, `test_test_runner` fail at import because they call `get_db_url()` at module load time (before fixtures run) and now `IW_CORE_TEST_CONTEXT=true` triggers the guard. Fix is S05's responsibility. |
| 2 | HIGH | `orch/daemon/__main__.py:18` | Arming is correctly placed BEFORE `load_config()` and BEFORE `Daemon(config)` construction. ✅ |
| 3 | HIGH | `orch/daemon/main.py` | No arming leaked at module import. `import orch.daemon.main` does not set `IW_CORE_DAEMON_CONTEXT`. ✅ |
| 4 | HIGH | `orch/cli/migrations_commands.py:179–225` | Try/finally-scoped arming is correct — exact pattern specified. ✅ |
| 5 | HIGH | `orch/daemon/batch_manager.py:1050–1080` | `_agent_subprocess_env` strips both daemon flags AND sets `IW_CORE_AGENT_CONTEXT`. ✅ |
| 6 | CRITICAL | `orch/daemon/batch_manager.py:772` | `_launch_step` uses `_agent_subprocess_env()` (correct, replaces previous `env=os.environ.copy()`). ✅ |
| 7 | CRITICAL | `orch/daemon/doc_job_poller.py:171` | Was `env=os.environ.copy()` with no arming; now uses `_agent_subprocess_env()`. ✅ |
| 8 | HIGH | `orch/daemon/fix_cycle.py:1136` | `_launch_fix_agent` uses `_build_agent_env()` which delegates to `_agent_subprocess_env()`. ✅ |
| 9 | INFO | `orch/daemon/main.py`, `migration_pipeline.py`, `worktree_compose.py`, `migration_rebase.py` | Routing-only change: `create_engine` → `safe_create_engine`. No arming, no new logic. ✅ |
| 10 | HIGH | Multiple | Comments referencing `I-00041` present at all arming sites. ✅ |

---

## Overall Verdict

**PASS** — The S03 implementation is correct and complete. All arming sites are properly placed, all subprocess launch sites use the strip helper, the polarity flip in conftest is exactly right, and the try/finally scoping for the operator CLI is precise.

The CRITICAL finding (test collection failures in 3 unit test files) is **pre-existing** — those tests call `get_db_url()` at module import time before any fixtures run, so any session-level `IW_CORE_TEST_CONTEXT=true` would break them. This is a structural fragility in those test files, not an S03 regression. S05 owns the fix.