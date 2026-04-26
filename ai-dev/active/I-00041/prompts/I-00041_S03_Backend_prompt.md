# I-00041_S03_Backend_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. This step adds NO
new migration.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S02_CodeReview_Backend_report.md`
- `tests/conftest.py`
- `orch/daemon/__main__.py` (the actual daemon entry — `main.py` has only
  the `Daemon` class; `__main__.py` line 11 is the `if __name__ ==
  "__main__"` block that calls `Daemon(config).run()`)
- `orch/daemon/main.py` (read-only context — `Daemon.__init__` line 142
  immediately calls `create_session_factory(config.db_url)`, so the
  arming MUST happen before this constructor runs)
- `orch/cli/migrations_commands.py`
- `orch/db/live_db_guard.py` (added by S01)

## Output Files

- Modified: `tests/conftest.py`
- Modified: `orch/daemon/__main__.py` (arm `IW_CORE_DAEMON_CONTEXT=true`
  BEFORE constructing `Daemon(config)` — `main.py` has no `def main()` /
  `__name__ == "__main__"` block)
- Modified: `orch/cli/migrations_commands.py` (try/finally-scoped
  `IW_CORE_OPERATOR_APPLY` arming)
- Modified: `orch/daemon/batch_manager.py` (new `_agent_subprocess_env`
  helper + 3 call sites)
- Modified: `orch/daemon/fix_cycle.py` (1 call site)
- Modified: `orch/daemon/doc_job_poller.py` (1 call site)
- Report: `ai-dev/active/I-00041/reports/I-00041_S03_Backend_report.md`

## Context

S01 added the connection-layer chokepoint. This step **arms it** by:

1. Inverting the test conftest from opt-out to opt-in (set the *guard*
   flag, don't delete a *guard removal* flag).
2. Wiring the daemon entry point to set its own opt-in flag
   (`IW_CORE_DAEMON_CONTEXT=true`) before any DB access.
3. Wiring the `iw migrations apply --i-am-operator` command to set
   `IW_CORE_OPERATOR_APPLY=true` only for that one command's lifetime.

The result: tests fail loudly if they touch 5433; the daemon and operator
CLI continue to work; ad-hoc local scripts (no flag set) preserve current
behaviour for backwards compatibility (the guard refuses live DB only
when a refused-context flag is positively set).

## Requirements

### R1 — Invert `tests/conftest.py:23` polarity

The current code:

```python
@pytest.fixture(autouse=True)
def _isolate_agent_context_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
```

Replace with a session-scoped autouse fixture that **sets** the guard:

```python
@pytest.fixture(autouse=True, scope="session")
def _arm_live_db_guard() -> None:
    """Arm the live-DB connection guard for the entire pytest session.

    Sets IW_CORE_TEST_CONTEXT=true and explicitly clears any opt-in vars
    that might have leaked from the parent shell. Using os.environ
    directly (not monkeypatch) so the flag persists across tests, into
    subprocesses, and into testcontainers.

    See I-00041 for context. The previous opt-out fixture was the
    proximate cause of a 4-hour dashboard outage.
    """
    import os
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
    os.environ.pop("IW_CORE_DAEMON_CONTEXT", None)
    os.environ.pop("IW_CORE_AGENT_CONTEXT", None)
    # No yield — env vars persist for the rest of the session, which is
    # the point. monkeypatch would auto-restore.
```

**Critical**: the function-scoped `_isolate_agent_context_env` autouse
fixture is REPLACED, not added alongside. Delete it. Its old purpose
(prevent agent-context leakage from parent shell into pytest) is now
served by the explicit `os.environ.pop` calls above.

If any tests rely on `IW_CORE_AGENT_CONTEXT` being deleted (search with
`grep -rn IW_CORE_AGENT_CONTEXT tests/`), keep their `monkeypatch.delenv`
calls in the individual tests; the session fixture's pop is for default
hygiene, not isolation.

### R2 — Daemon entry point sets `IW_CORE_DAEMON_CONTEXT=true`

**Reality check first.** `orch/daemon/main.py` defines the `Daemon`
*class* but no `def main()` and no `if __name__ == "__main__"` block.
The actual entry path is `orch/daemon/__main__.py` (invoked by
`python -m orch.daemon` or directly):

```python
# orch/daemon/__main__.py — current state
if __name__ == "__main__":
    try:
        config = load_config()
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        logging.basicConfig(...)
        Daemon(config).run()
    ...
```

`Daemon.__init__` (line 142 in `main.py`) immediately calls
`create_session_factory(config.db_url)`, which after S01 routes through
`safe_create_engine`. Therefore the daemon-context flag MUST be set
**before `Daemon(config)` is constructed**, or the very first engine
creation will fire the guard with no allow-list flag set and either
refuse (if a stray refused-context flag is in the parent shell) or
default-allow (which silently bypasses the chokepoint discipline this
incident is establishing).

#### Required change in `orch/daemon/__main__.py`

Insert the arming as the FIRST executable statement inside the
`if __name__ == "__main__":` block, before `load_config()`:

```python
if __name__ == "__main__":
    # I-00041: arm the live-DB connection guard for the daemon process.
    # Must happen BEFORE Daemon(config) construction — the constructor
    # immediately builds an engine via safe_create_engine, which checks
    # this flag.
    import os  # noqa: PLC0415  (already imported at module top, kept for clarity)
    os.environ["IW_CORE_DAEMON_CONTEXT"] = "true"

    try:
        config = load_config()
        ...
        Daemon(config).run()
    ...
```

Use `os.environ[...] = ...` directly (no try/finally) — the daemon
process is the lifetime; flag should persist for the entire run.

#### Do NOT add arming to `main.py`

Do NOT add a `_arm_daemon_context()` helper to `orch/daemon/main.py` or
mutate `os.environ` at import time of `main.py`. That would mean
`import orch.daemon.main` from a non-daemon context (e.g. a test or the
dashboard) would arm the daemon flag — exactly the leakage S04 will
fail on.

#### Subprocess inheritance

**IMPORTANT — subprocesses inherit `IW_CORE_DAEMON_CONTEXT` by default.**
This is the canonical attack path the bug took. R5 below explicitly
strips the flag from any agent or QV-gate subprocess the daemon launches
via `_agent_subprocess_env()`.

Because S01 makes engine creation lazy (module `__getattr__`), importing
`orch.db.session` does NOT fire the guard before the env var is set. Run
the smoke check in this prompt's Test Verification section to confirm.

### R3 — `iw migrations apply` sets `IW_CORE_OPERATOR_APPLY=true` (try/finally scoped)

In `orch/cli/migrations_commands.py`, in `apply_migrations` (line 152),
wrap the migration call in a try/finally that arms the env var **only
for the duration of the `safe_apply` invocation** and restores the prior
state on exit. This makes the lifetime real: even if a future caller
imports `apply_migrations` and calls it programmatically (a test, a
wrapper, a script that loops), the flag does not leak into surrounding
code.

Required structure:

```python
def apply_migrations(ctx: click.Context, json_output: bool, i_am_operator: bool) -> None:
    # 1. Existing AGENT_CONTEXT refusal check.
    if os.environ.get(AGENT_CONTEXT_ENV) == "true":
        ...
        return

    # 2. Existing --i-am-operator flag check.
    if not i_am_operator:
        ...
        return

    # 3. I-00041: arm the live-DB connection guard for THIS invocation only.
    # try/finally so a programmatic caller (test, wrapper, loop) doesn't
    # leak the allow-list flag into surrounding code. The daemon-launched
    # CLI process exits right after, so for the canonical operator path
    # the finally is a no-op — but it's the contract that matters.
    prior = os.environ.get("IW_CORE_OPERATOR_APPLY")
    os.environ["IW_CORE_OPERATOR_APPLY"] = "true"
    try:
        # 4. Existing safe_apply call (and any post-apply reporting).
        result = safe_apply(...)
        ...
    finally:
        if prior is None:
            os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
        else:
            os.environ["IW_CORE_OPERATOR_APPLY"] = prior
```

Important:
- Required order of operations:
  1. AGENT_CONTEXT refusal check (existing) — agent invocation refused
     here, never reaches step 3.
  2. `--i-am-operator` flag check (existing).
  3. try/finally arm `IW_CORE_OPERATOR_APPLY=true` (new).
  4. Call `safe_apply` (existing) inside the try.
  5. Finally restore prior state.
- Do NOT set the env var on `dry_run` or `list_pending`. `dry_run` uses
  a testcontainer URL (not live, guard is a no-op). `list_pending` reads
  alembic_version from the live DB via `_current_revision_from_db`, but
  the operator's shell typically has no refused-context flag set, so
  the guard's "no flag set → allowed" default-allow path keeps it
  working unchanged.
- This is the ONLY place in the codebase that sets
  `IW_CORE_OPERATOR_APPLY`. Verify with
  `grep -rn IW_CORE_OPERATOR_APPLY orch/ --include='*.py'` — must show
  exactly one assignment site (in `apply_migrations`).

### R4 — Sanity: don't leak the env vars across pytest sessions

The fixture in R1 sets `IW_CORE_TEST_CONTEXT=true` for the session via
`os.environ` directly (not monkeypatch). If pytest is invoked nested
(e.g. a test runs another `pytest` subprocess), the env var inherits —
that is correct and desired.

For pytest-xdist workers: confirm that worker processes inherit env from
the parent. They do (xdist uses `subprocess` with `env=os.environ` by
default), but spot-check this is still true.

### R5 — Strip allow-list flags from agent and QV-gate subprocesses

**This is the single most important requirement in S03 (per I-00041
review).** Without it, the daemon's own `IW_CORE_DAEMON_CONTEXT=true`
(set in R2) leaks into every
agent and QV-gate subprocess via `os.environ` inheritance, and the agent
process is *allowed* to write to the live DB — exactly the bug we are
fixing.

#### R5.1 — Add a centralised helper

In `orch/daemon/batch_manager.py`, add (next to the existing
`_build_agent_env` at line ~1054):

```python
def _agent_subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build the env for any subprocess that runs agent or QV-gate code.

    Strips the daemon's allow-list flags so the child cannot bypass the
    live-DB guard, then arms agent context. Any caller that needs more
    vars (e.g. browser env, per-worktree DB ports) merges them via `extra`.

    See I-00041 for context. The leak this prevents was the proximate
    cause of the 4-hour dashboard outage on 2026-04-26.
    """
    import os  # noqa: PLC0415

    env = os.environ.copy()
    # Strip allow-list flags — agents are NEVER trusted to write to live DB.
    env.pop("IW_CORE_DAEMON_CONTEXT", None)
    env.pop("IW_CORE_OPERATOR_APPLY", None)
    # Arm refused-context for the child.
    env["IW_CORE_AGENT_CONTEXT"] = "true"
    if extra:
        env.update(extra)
    return env
```

The helper is the single chokepoint for "build a child env for agent-like
work". Any future subprocess launch that runs untrusted/agent code MUST
use it.

#### R5.2 — Apply at every existing call site

Replace every existing inline env construction at agent/gate launch sites
with a call to `_agent_subprocess_env(...)`. The full list (verify with
`grep -rn 'IW_CORE_AGENT_CONTEXT' orch/ --include='*.py'` plus a sweep of
`subprocess.Popen|run.*env=` in `orch/daemon/`):

| File | Line | Current pattern | Change |
|------|------|-----------------|--------|
| `orch/daemon/batch_manager.py` | ~565 | `env={**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` | `env=_agent_subprocess_env()` |
| `orch/daemon/batch_manager.py` | ~776 | `agent_env = {**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` then optional merges (`bv_env`, `IW_CORE_PER_WORKTREE_DB`) | `agent_env = _agent_subprocess_env(); ` then preserve the existing optional merges (build a `extras` dict and pass once, OR keep the post-construction dict mutations — either is fine as long as the strip happens). |
| `orch/daemon/batch_manager.py` | ~1054 | `_build_agent_env` returns `os.environ.copy()` | Replace its body with `return _agent_subprocess_env()`. The function keeps its name and signature (`fix_cycle.py:1102` imports it). |
| `orch/daemon/fix_cycle.py` | ~733 | `env={**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` | `env=_agent_subprocess_env()` (import the helper from `orch.daemon.batch_manager`). |
| `orch/daemon/doc_job_poller.py` | ~164 | `env=os.environ.copy()` (does NOT currently set `IW_CORE_AGENT_CONTEXT` either — also a bug) | `env=_agent_subprocess_env()` (this fixes both the strip AND the missing arm). |

Do NOT change the `subprocess.run` sites that invoke local infrastructure
commands (e.g. `worktree_compose.py` Docker wrappers, `merge_queue.py` git
operations, `worktree_reaper.py` reaper, `migration_rebase.py` git rebase,
`browser_env.py` playwright). Those are daemon-trusted and need to retain
the daemon's allow-list. The strip only applies to **agent and QV-gate
work**.

If you find a launch site that is borderline (e.g. a daemon-trusted helper
that nevertheless executes user code), document it in the report rather
than changing it.

### R6 — Backwards compatibility

- `IW_CORE_AGENT_CONTEXT` remains honoured (S01 made it a deprecated
  alias). Do NOT delete it from `tests/conftest.py` callers that
  explicitly use it — only the autouse fixture changes polarity.
- The daemon and dashboard processes that rely on `safe_migrate.py`'s
  internal helpers continue to work because S01 routed them all through
  `safe_create_engine`, which respects the new guard's allow-list.
- The dashboard does NOT need an env-var change in this step. It runs
  under the daemon's environment and inherits `IW_CORE_DAEMON_CONTEXT=true`
  if launched from `./ai-core.sh start`. If launched standalone (rare),
  add a brief note in the report — a follow-up incident can address it.

## Project Conventions

- Read `tests/CLAUDE.md` for test fixture conventions.
- Read `orch/CLAUDE.md` for daemon/CLI patterns.
- Setting env vars at module-load time is generally discouraged, but for
  arming a security guard at process start it is the right pattern.
  Document each `os.environ[...] = ...` with a one-line comment pointing
  to this incident's ID.

## TDD Requirement

S05 (Tests) writes the unit/integration suite for this step. For S03,
write a **manual smoke check** in your report:

1. From a clean shell, run:
   ```bash
   IW_CORE_TEST_CONTEXT=true uv run python -c "
   from orch.db.live_db_guard import assert_engine_url_allowed
   try:
       assert_engine_url_allowed('postgresql://iw_orch:iw_orch@localhost:5433/iw_orch')
       print('FAIL: guard did not fire')
   except Exception as e:
       print(f'OK: guard fired with {type(e).__name__}: {e}')
   "
   ```
   Expected: `OK: guard fired with LiveDbConnectionRefused: ...`.
2. Run `uv run pytest tests/unit/ -k "smoke" --collect-only -q 2>&1 | head -5`
   to confirm pytest collection still works under the new conftest.
3. Run `uv run iw migrations list-pending` (operator command, no flag set)
   to confirm read-only operator commands still work.

Paste outputs in the report.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make lint` — must pass.
2. `make typecheck` — must pass.
3. The smoke checks above all produce the expected output.
4. Importing `orch.daemon.main` does not crash AND does not arm the
   daemon flag. Confirm with:
   ```bash
   unset IW_CORE_DAEMON_CONTEXT
   uv run python -c "
   import os
   import orch.daemon.main  # noqa
   assert os.environ.get('IW_CORE_DAEMON_CONTEXT') != 'true', \\
     'arming leaked at module import — must be in __main__.py only'
   print('daemon import ok (no leak)')
   "
   ```
   Must print `daemon import ok (no leak)`.
5. **Allow-list strip smoke**: confirm `_agent_subprocess_env()` strips
   the daemon flag.
   ```bash
   IW_CORE_DAEMON_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "
   from orch.daemon.batch_manager import _agent_subprocess_env
   env = _agent_subprocess_env()
   assert 'IW_CORE_DAEMON_CONTEXT' not in env, env.get('IW_CORE_DAEMON_CONTEXT')
   assert 'IW_CORE_OPERATOR_APPLY' not in env, env.get('IW_CORE_OPERATOR_APPLY')
   assert env.get('IW_CORE_AGENT_CONTEXT') == 'true', env.get('IW_CORE_AGENT_CONTEXT')
   print('strip ok')
   "
   ```
   Must print `strip ok`.
6. Confirm every audited call site now uses the helper:
   ```bash
   grep -nE 'env\s*=\s*\{?\*\*\s*os\.environ' orch/daemon/batch_manager.py orch/daemon/fix_cycle.py orch/daemon/doc_job_poller.py
   ```
   Must show ZERO matches inside the agent/gate launch sites listed in R5.2
   (matches in unrelated daemon-trusted helpers are fine).

Report: `tests_passed: true` only if all six checks pass.

## Subagent Result Contract

When complete, report results in this JSON structure:

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "I-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/conftest.py",
    "orch/daemon/__main__.py",
    "orch/cli/migrations_commands.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "orch/daemon/doc_job_poller.py"
  ],
  "tests_passed": true,
  "test_summary": "lint OK, typecheck OK, manual smoke checks OK",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S03
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S03 --report ai-dev/active/I-00041/reports/I-00041_S03_Backend_report.md
```
