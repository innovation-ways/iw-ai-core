# I-00041_S04_CodeReview_Backend_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Same rules as the implementation prompt. Read-only introspection only.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S03_Backend_report.md`
- `tests/conftest.py` (modified)
- `orch/daemon/__main__.py` (modified — arming BEFORE `Daemon(config)`)
- `orch/daemon/main.py` (NOT expected to be modified by S03 — verify)
- `orch/cli/migrations_commands.py` (modified — try/finally-scoped arming)
- `orch/daemon/batch_manager.py` (modified — new helper + 3 call sites)
- `orch/daemon/fix_cycle.py` (modified — 1 call site)
- `orch/daemon/doc_job_poller.py` (modified — 1 call site)
- `orch/db/live_db_guard.py` (added by S01, for context)

## Output Files

- Report: `ai-dev/active/I-00041/reports/I-00041_S04_CodeReview_Backend_report.md`

## Context

S03 armed the connection-layer guard from S01 by inverting the test conftest
polarity and wiring the daemon/operator opt-in env vars. This review verifies
the polarity flip is complete, the env-var arming happens at the right
moment, and no path was missed.

## Review Checklist

### 1. Conftest polarity inversion

- [ ] The function-scoped `_isolate_agent_context_env` autouse fixture is
      **deleted** (not just commented out, not still present alongside).
- [ ] The replacement fixture is **session-scoped** and **autouse**.
- [ ] The fixture sets `IW_CORE_TEST_CONTEXT=true` via `os.environ` directly
      (not `monkeypatch.setenv`) so it persists across tests, into
      subprocesses, and into testcontainers.
- [ ] The fixture explicitly clears `IW_CORE_OPERATOR_APPLY`,
      `IW_CORE_DAEMON_CONTEXT`, and `IW_CORE_AGENT_CONTEXT` from the
      environment.
- [ ] The fixture's docstring references `I-00041` and explains why the
      polarity changed (so a future test author who tries to "fix" it by
      reverting reads the rationale first).
- [ ] No tests under `tests/` rely on `IW_CORE_AGENT_CONTEXT` being
      automatically deleted (the few that do should `monkeypatch.delenv`
      explicitly in their own scope; verify by `grep -rn IW_CORE_AGENT_CONTEXT
      tests/` and inspect each match).

### 2. Daemon entry-point arming

- [ ] Arming is in `orch/daemon/__main__.py` inside the
      `if __name__ == "__main__":` block, BEFORE `load_config()` and
      BEFORE `Daemon(config)` construction. (`Daemon.__init__` calls
      `create_session_factory` immediately, which after S01 routes
      through `safe_create_engine`. Arming AFTER `Daemon(config)` is a
      bug.)
- [ ] Arming is NOT in `orch/daemon/main.py` (no module-load mutation,
      no `_arm_daemon_context()` helper there). Verify with
      `git diff orch/daemon/main.py` showing no changes from S03.
- [ ] `import orch.daemon.main` from a non-daemon context does NOT
      auto-arm. Confirm with the smoke check below:
      ```bash
      unset IW_CORE_DAEMON_CONTEXT
      uv run python -c "
      import os
      import orch.daemon.main  # noqa
      assert os.environ.get('IW_CORE_DAEMON_CONTEXT') != 'true', \\
        'arming leaked at module import'
      print('OK: import-safe')
      "
      ```
- [ ] Subprocesses launched by the daemon (executor scripts, agent CLI
      runners) inherit the env var by default unless explicitly stripped
      — confirm R5 strip is the ONLY filtering in place (no other
      `env=` wrappers strip the daemon flag for trusted subprocesses).

### 3. Operator CLI arming (try/finally scoped)

- [ ] `IW_CORE_OPERATOR_APPLY=true` is set inside `apply_migrations`
      (NOT at module load, NOT in `dry_run`, NOT in `list_pending`).
- [ ] The arming is wrapped in **try/finally** that restores the prior
      env-var state on exit. This makes the lifetime real for
      programmatic callers (tests, wrappers, loops). The pattern:
      ```python
      prior = os.environ.get("IW_CORE_OPERATOR_APPLY")
      os.environ["IW_CORE_OPERATOR_APPLY"] = "true"
      try:
          safe_apply(...)
      finally:
          if prior is None:
              os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
          else:
              os.environ["IW_CORE_OPERATOR_APPLY"] = prior
      ```
- [ ] Order is: AGENT_CONTEXT refusal → `--i-am-operator` check →
      try/finally arm → safe_apply inside try → finally restore.
      Verify by reading the function top-down.
- [ ] `dry_run` and `list_pending` do NOT set the env var. They rely on
      the guard's "no flag set" default-allow behaviour for the
      read-only / testcontainer paths.
- [ ] No other site sets `IW_CORE_OPERATOR_APPLY`. Verify with
      `grep -rn 'IW_CORE_OPERATOR_APPLY\\s*=\\s*' orch/ --include='*.py'`
      — must show exactly ONE assignment site (in `apply_migrations`).

### 4. Allow-list strip at agent/gate subprocess launch (R5)

This is the most important review category in S04. The daemon arms
`IW_CORE_DAEMON_CONTEXT=true` on itself (R2); R5 ensures that flag does
NOT leak into agent/gate child processes via `os.environ` inheritance.
A miss here re-opens the bug.

- [ ] `_agent_subprocess_env(extra=None)` exists in
      `orch/daemon/batch_manager.py`, alongside `_build_agent_env`.
- [ ] The helper pops BOTH `IW_CORE_DAEMON_CONTEXT` AND
      `IW_CORE_OPERATOR_APPLY` from the returned env. Confirm by reading
      the helper top-down.
- [ ] The helper sets `IW_CORE_AGENT_CONTEXT=true` on the returned env.
- [ ] All five audited call sites use the helper. Verify exactly:
      ```bash
      grep -nE 'env\s*=\s*\{?\*\*\s*os\.environ' \
        orch/daemon/batch_manager.py \
        orch/daemon/fix_cycle.py \
        orch/daemon/doc_job_poller.py
      ```
      Must show ZERO matches at the launch sites listed in S03 R5.2
      (any remaining matches must be in daemon-trusted helpers and
      explicitly justified in the S03 report).
- [ ] `_build_agent_env(...)` (existing helper, used by `fix_cycle.py:1102`)
      delegates to `_agent_subprocess_env()`. Confirm the function still
      has the same signature so external callers do not break.
- [ ] `orch/daemon/doc_job_poller.py:~164` was previously `env=os.environ.copy()`
      with NO arming of `IW_CORE_AGENT_CONTEXT`. Confirm it now uses the
      helper and therefore both arms agent context AND strips daemon flag.
- [ ] Daemon-trusted subprocesses (worktree compose, merge_queue git ops,
      worktree_reaper, migration_rebase, browser_env playwright) are
      **NOT** changed — they need to retain the daemon's allow-list.
      Confirm by `git diff --stat orch/daemon/` showing changes ONLY in
      `batch_manager.py`, `fix_cycle.py`, `doc_job_poller.py`, and
      `main.py`.

Manually verify (paste output):

```bash
# Helper does what it claims, even when both allow-list flags are set.
IW_CORE_DAEMON_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "
from orch.daemon.batch_manager import _agent_subprocess_env
env = _agent_subprocess_env()
assert 'IW_CORE_DAEMON_CONTEXT' not in env
assert 'IW_CORE_OPERATOR_APPLY' not in env
assert env.get('IW_CORE_AGENT_CONTEXT') == 'true'
print('OK: strip + arm')
"
# Expect: OK: strip + arm
```

### 5. Layer / scope discipline

- [ ] No changes outside the files listed in Output Files (conftest, main,
      migrations_commands, batch_manager, fix_cycle, doc_job_poller).
      Verify with `git diff --stat | grep -v reports/`.
- [ ] No changes to `orch/db/`. Those landed in S01.
- [ ] No new tests added in this step (S05 owns tests). Verify by
      `git diff --stat tests/` showing only `tests/conftest.py`.
- [ ] Dashboard untouched. (Acknowledged in design doc as a follow-up if
      needed.)

### 6. Behavioural correctness

Manually verify (paste outputs in your report):

```bash
# A. Pytest collection works under new conftest.
uv run pytest tests/unit/ --collect-only -q 2>&1 | tail -5

# B. Guard fires from a test-context subprocess.
IW_CORE_TEST_CONTEXT=true uv run python -c "
from orch.db.live_db_guard import assert_engine_url_allowed
try:
    assert_engine_url_allowed('postgresql://iw_orch:iw_orch@localhost:5433/iw_orch')
except Exception as e:
    print(f'OK: {type(e).__name__}')
else:
    print('FAIL: no refusal')
"
# Expect: OK: LiveDbConnectionRefused

# C. Operator CLI sets the var (dry-check via grep).
grep -nE "IW_CORE_OPERATOR_APPLY\s*=\s*['\"]true" orch/cli/migrations_commands.py
# Expect: exactly ONE match in apply_migrations.

# D. Daemon import does NOT arm globally (env unchanged after import).
unset IW_CORE_DAEMON_CONTEXT
uv run python -c "
import os
import orch.daemon.main  # noqa
assert os.environ.get('IW_CORE_DAEMON_CONTEXT') != 'true', 'arming leaked at import'
print('OK: import-safe')
"
# Expect: OK: import-safe
```

### 7. Comments and observability

- [ ] Each `os.environ[...] = ...` arming call has a one-line comment
      referencing `I-00041` so future readers understand the polarity
      decision.
- [ ] No `print()` calls. No bare `except:`.
- [ ] No log messages added at INFO+ level for the arming itself
      (it would spam every daemon/CLI startup). The guard itself is
      where logging happens (added in S01).

### 8. Backwards compatibility

- [ ] `IW_CORE_AGENT_CONTEXT` is still honoured when set explicitly
      (deprecated, not removed).
- [ ] Existing `monkeypatch.delenv("IW_CORE_AGENT_CONTEXT")` calls in
      individual tests (if any) still work.
- [ ] Daemon launched via `./ai-core.sh start` continues to start.
      (Smoke-check the launch script if you can do so without affecting
      the running daemon — read-only inspection only.)

### 9. Scope drift

- [ ] No refactoring of conftest beyond the polarity flip.
- [ ] No new fixtures added.
- [ ] No changes to `tests/integration/test_migration_pipeline.py`
      (S05 owns that).

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO),
`file:line`, and a one-line verdict per item. End with overall verdict
(`PASS` / `NEEDS_FIX` / `BLOCKED`).

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S04
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S04 --report ai-dev/active/I-00041/reports/I-00041_S04_CodeReview_Backend_report.md
```
