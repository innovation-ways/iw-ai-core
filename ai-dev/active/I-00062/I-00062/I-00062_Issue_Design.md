# I-00062: Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433

**Type**: Issue
**Severity**: High
**Created**: 2026-05-03
**Reported By**: Operator (post-incident triage of F-00077 BATCH-00074)
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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

This incident is *itself* about a violation of this rule that happened
through `make`-driven transitive alembic invocation. Do not repeat it.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

When a Feature with new migrations is in flight in a worktree that has its
own per-worktree DB stack (`ai-dev/iw-config/`), an agent that runs `make`
(or any task that transitively invokes `alembic upgrade head`) silently
applies the migration to the **orch DB on port 5433** instead of the
per-worktree DB. This bypasses the daemon's merge-time migration pipeline,
breaks isolation between in-flight features and the orch source of truth,
and leaves the dashboard's alembic guard in a "schema mismatch — write
actions disabled" state until the operator manually reconciles both DBs.

Concrete trigger this run: F-00077 S21 fix-cycle agent ran `make`, which
applied migration `e53ce8e86a3c` to the orch DB on 5433 instead of the
per-worktree DB on port 36216.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Particularly relevant for this incident:

- `CLAUDE.md` (root) — per-worktree DB contract: `IW_CORE_DB_*` points at the
  per-worktree DB; `IW_CORE_ORCH_DB_*` always points at the global orch DB on 5433.
- `orch/CLAUDE.md` — `_agent_subprocess_env()` design (I-00041 context, the
  2026-04-26 dashboard outage that this guard was meant to prevent).
- `docs/IW_AI_Core_Agent_Constraints.md` — R1/R2 (Docker / Migrations off-limits
  for agents). This incident is a structural failure of R2 enforcement.
- `docs/IW_AI_Core_Worktree_Isolation.md` — F-00062 per-worktree compose stack
  design.

## Steps to Reproduce

1. Have the daemon running (started from the main repo, with main's `.env` →
   `IW_CORE_DB_PORT=5433`).
2. Approve a Feature whose project has `ai-dev/iw-config/` (per-worktree DB
   compose stack) and that introduces a new alembic migration.
3. Let the daemon launch the worktree. The compose stack comes up on a random
   high port (e.g. 36216).
4. During any agent step (or fix-cycle), have the agent run `make` (no target),
   `make install`, or any target that transitively calls `uv run alembic upgrade
   head`.

**Expected**:
- The migration is applied to the per-worktree DB on the random high port (36216).
- The orch DB on 5433 stays at main's current head until F-00077 squash-merges
  and `migration_pipeline.run_post_merge_apply` runs.
- The dashboard's alembic guard reports "DB at head" the entire time.

**Actual**:
- The migration is applied to the orch DB on 5433.
- The per-worktree DB on 36216 stays at the prior head, so the agent's runtime
  app is now schema-out-of-sync with its own runtime DB.
- The dashboard's alembic guard reports "schema mismatch — current_rev=
  &lt;unmerged-revision&gt; head_rev=&lt;main-head&gt;" and disables write actions
  until operator intervention.
- The next time `_run_alembic_upgrade` is called from anywhere reading main's
  migration tree, alembic raises `Can't locate revision identified by
  '&lt;unmerged-revision&gt;'`.

## Root Cause Analysis

The agent subprocess inherits the daemon's environment, which has
`IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD` pointing at the orch DB on 5433.
The per-worktree DB credentials exist only in the worktree's `.env` file.
When the agent's Python alembic invocation imports `orch.config`,
`load_dotenv` runs with `override=False` (the default), so the inherited
5433 values win over the worktree's `.env`.

Specifics, with file:line references:

1. **`orch/daemon/batch_manager.py:1432` `_agent_subprocess_env()`** copies
   the daemon's environment via `os.environ.copy()`. This carries
   `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD` (= 5433 connection) verbatim
   into every agent subprocess. The function strips a couple of allow-list
   flags (`IW_CORE_DAEMON_CONTEXT`, `IW_CORE_OPERATOR_APPLY`, `VIRTUAL_ENV`)
   and arms `IW_CORE_AGENT_CONTEXT=true`, but it does NOT strip the orch DB
   connection vars.

2. **`orch/daemon/batch_manager.py:1128` `_launch_step`** sets the marker
   `agent_env["IW_CORE_PER_WORKTREE_DB"] = "true"` when the worktree has a
   compose stack, but does NOT overwrite `IW_CORE_DB_HOST/PORT/NAME/USER/
   PASSWORD` to the per-worktree values. The compose stack's discovered DB
   port is already on `BatchItem.worktree_db_port` (set at `batch_manager.py:
   593-595`), but the host/name/user/password are not persisted.

3. **`orch/config.py:20` `load_dotenv(_ENV_FILE)`** uses python-dotenv's
   default `override=False`. Because the agent's env already has
   `IW_CORE_DB_PORT=5433` (inherited from daemon), the worktree's `.env`
   value of `IW_CORE_DB_PORT=36216` is silently ignored.

4. **The Makefile's default target chain** runs `uv run alembic upgrade
   head`. The Python alembic invocation imports `orch.config`, which (per
   step 3) connects to 5433 with the daemon's credentials and writes the
   new migration there.

Evidence: `.worktrees/F-00077/ai-dev/logs/F-00077_S21_fix2.log:25` shows
the exact `make` → `uv run alembic upgrade head` → `Running upgrade
4876b3246ff2 -> e53ce8e86a3c, F-00077 chat conversations memory`. The
per-worktree DB on port 36216 was at `4876b3246ff2` (no chat tables); the
orch DB on 5433 ended up at `e53ce8e86a3c` (with chat tables it should not
have had until merge).

The current prompt-only mitigation ("You MUST NOT run alembic upgrade/
downgrade/stamp against the live orch DB", in
`prompts/F-00077_S01_Database_prompt.md:34` and similar) is unenforceable
— running `make` is sufficient to violate it without any explicit alembic
invocation.

### Legacy worktrees (no per-worktree compose stack)

Even if the strip in (1) is added, agents launched in worktrees that do
NOT opt into `ai-dev/iw-config/` still inherit the orch DB indirectly
via `load_dotenv(_ENV_FILE)`: the worktree's `.env` is a copy of main's
`.env` (populated by `executor/worktree_setup.sh`), which contains
`IW_CORE_DB_PORT=5433`. The Makefile's `make install` chain therefore
still ends up applying alembic to 5433 — the bug class is the same,
just sourced from `.env` rather than from the inherited shell env.

The Layer 3 fail-fast guard in `orch/config.py` (see "Code Changes")
catches this case, BUT only if `IW_CORE_ORCH_DB_PORT` is set in the
agent env. Today `IW_CORE_ORCH_DB_PORT` is set ONLY by
`orch/daemon/browser_env.py:235-244` for browser-verification steps —
not by the daemon for ordinary agent launches. Therefore the fix must
also generalise that snapshot to ALL agent launches via
`_agent_subprocess_env`. Without that snapshot, Layer 3 is vacuous for
both compose-stack regressions and legacy regressions.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/batch_manager.py:_agent_subprocess_env` | Leaks daemon's orch DB connection env to every agent subprocess |
| `orch/daemon/batch_manager.py:_launch_step` (compose path) | Sets `IW_CORE_PER_WORKTREE_DB=true` but doesn't inject actual per-worktree DB connection vars |
| `orch/daemon/worktree_compose.py` | Discovers per-worktree DB port at compose-up but does not persist host/name/user/password for later injection |
| `orch/db/models.py:BatchItem` | Stores `worktree_db_port` and `worktree_app_port`, missing host/name/user/password columns |
| `orch/config.py:get_db_url` | Has no fail-fast guard: silently returns 5433 when imported in agent context with leaked env |
| Dashboard alembic guard | Misreports "schema mismatch" / "behind head" because the orch DB has out-of-tree revisions from in-flight features |
| Operator | Forced to manually downgrade orch DB and upgrade per-worktree DB after every leak |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `worktree_db_host`, `worktree_db_name`, `worktree_db_user`, `worktree_db_password` columns to `batch_items`; ORM model update; alembic migration file | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | backend-impl | Populate new columns from `worktree_compose.up()`; inject all per-worktree `IW_CORE_DB_*` vars in `_launch_step`; strip orch DB vars from `_agent_subprocess_env`; add fail-fast in `orch/config.py` | — |
| S04 | code-review-impl | Per-agent review of S03 | — |
| S05 | tests-impl | Unit + integration tests: env injection, env stripping, fail-fast guard, regression covering the F-00077 scenario | — |
| S06 | code-review-impl | Per-agent review of S05 — semantic correctness gate | — |
| S07 | code-review-final-impl | Cross-agent global review covering ACs | — |
| S08..S14 | QV gates | lint, format-check, type-check, arch-check, security-sast, test-unit, test-integration | — |

Agent slugs: `database-impl`, `backend-impl`, `tests-impl`, `code-review-impl`,
`code-review-final-impl`, `qv-gate`.

### Database Changes

- **New tables**: None
- **Modified tables**: `batch_items` — four new nullable columns:
  `worktree_db_host TEXT`, `worktree_db_name TEXT`, `worktree_db_user TEXT`,
  `worktree_db_password TEXT`. All nullable because items without
  `ai-dev/iw-config/` (no per-worktree compose stack) leave them NULL.
- **Migration notes**:
  - Single forward migration that adds the four columns. Reversible.
  - No backfill required — existing in-flight items will continue to operate
    with the legacy code path; the new injection only kicks in when all four
    columns are non-NULL on `_launch_step`.
  - The migration will be applied to the orch DB by the daemon's
    `migration_pipeline.run_post_merge_apply` only after I-00062 squash-merges,
    per the standard pipeline. Agents must NOT apply it manually.

### Code Changes

- **Files to modify**:
  - `orch/db/models.py` — add four columns to `BatchItem`
  - `orch/db/migrations/versions/&lt;new&gt;_i_00062_add_worktree_db_credentials.py` — alembic migration
  - `orch/daemon/worktree_compose.py` — expose host/name/user/password from `worktree-env.toml` in `UpResult.discovered_*`
  - `orch/daemon/batch_manager.py` — populate new BatchItem columns at compose-up; inject all per-worktree DB env vars in `_launch_step`; strip orch DB vars in `_agent_subprocess_env`
  - `orch/config.py` — add fail-fast: refuse to import if `IW_CORE_AGENT_CONTEXT=true` AND the resolved `IW_CORE_DB_PORT` matches the daemon's known orch port
- **Nature of change**: Defense-in-depth. Three independent layers each prevent
  the leak:
  1. **Snapshot + Strip** in `_agent_subprocess_env`: BEFORE stripping
     `IW_CORE_DB_*`, snapshot the daemon's values into the
     `IW_CORE_ORCH_DB_*` namespace (mirroring what `browser_env._build_env`
     already does for browser-verification steps, but for ALL agent launches).
     This gives Layer 3's guard a known reference to compare against.
     Then strip `IW_CORE_DB_*` so agents never see the daemon's primary
     creds by default.
  2. **Inject** per-worktree DB vars from persisted columns in `_launch_step`
     when the worktree has a compose stack.
  3. **Fail-fast** in `orch/config.py` when an agent process resolves to the
     daemon's orch port — so any future call site that bypasses the above
     two layers crashes loudly instead of writing silently. Because Layer 1
     always snapshots `IW_CORE_ORCH_DB_PORT` into the agent env, this guard
     fires for **both** compose-stack agents (where Layers 1+2 already
     handle the leak) AND legacy agents whose worktree `.env` still mirrors
     main's `IW_CORE_DB_PORT=5433`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00062_Issue_Design.md` | Design | This document |
| `I-00062_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00062_S01_Database_prompt.md` | Prompt | S01 — DB columns + ORM + migration |
| `prompts/I-00062_S02_CodeReview_Database_prompt.md` | Prompt | S02 — review S01 |
| `prompts/I-00062_S03_Backend_prompt.md` | Prompt | S03 — env injection/stripping + fail-fast |
| `prompts/I-00062_S04_CodeReview_Backend_prompt.md` | Prompt | S04 — review S03 |
| `prompts/I-00062_S05_Tests_prompt.md` | Prompt | S05 — reproduction + regression tests |
| `prompts/I-00062_S06_CodeReview_Tests_prompt.md` | Prompt | S06 — review tests |
| `prompts/I-00062_S07_CodeReview_Final_prompt.md` | Prompt | S07 — global review |

## Test to Reproduce

Pre-fix RED test (will FAIL on current main, PASS after S01–S03):

```python
# tests/integration/daemon/test_launch_step_env_isolation.py

def test_agent_subprocess_env_does_not_leak_orch_db_vars(
    monkeypatch, tmp_path
):
    """Reproduces I-00062: the agent subprocess env must NOT contain the
    daemon's orch DB connection vars, regardless of compose-stack state.

    Pre-fix: this test FAILS because os.environ.copy() leaks 5433 creds.
    Post-fix: passes because _agent_subprocess_env strips IW_CORE_DB_*.
    """
    from orch.daemon.batch_manager import _agent_subprocess_env

    # Simulate the daemon's env (orch DB on 5433)
    monkeypatch.setenv("IW_CORE_DB_HOST", "localhost")
    monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
    monkeypatch.setenv("IW_CORE_DB_NAME", "iw_orch")
    monkeypatch.setenv("IW_CORE_DB_USER", "iw_orch")
    monkeypatch.setenv("IW_CORE_DB_PASSWORD", "iw_orch_dev")

    env = _agent_subprocess_env()

    # The five connection vars must be absent unless explicitly injected
    assert "IW_CORE_DB_HOST" not in env
    assert "IW_CORE_DB_PORT" not in env
    assert "IW_CORE_DB_NAME" not in env
    assert "IW_CORE_DB_USER" not in env
    assert "IW_CORE_DB_PASSWORD" not in env
    # Agent context flag is still armed
    assert env["IW_CORE_AGENT_CONTEXT"] == "true"
```

A second integration test exercises the full `_launch_step` path with a fake
`BatchItem` that has all four `worktree_db_*` columns populated, and asserts
the spawned subprocess sees `IW_CORE_DB_PORT=&lt;worktree-port&gt;` (not 5433).

## Acceptance Criteria

### AC1: Bug is fixed — env injection on per-worktree compose path

```
Given a BatchItem whose worktree has a compose stack with a per-worktree DB
  on a random high port (e.g. 36216), and the daemon's process env has
  IW_CORE_DB_PORT=5433
When the daemon calls _launch_step to spawn an agent subprocess
Then the spawned subprocess's env has IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD
  set to the per-worktree DB values, NOT the daemon's 5433 values
And the spawned subprocess's IW_CORE_PER_WORKTREE_DB is "true"
```

### AC2: Bug is fixed — env snapshot + strip on baseline path

```
Given any agent-launch path
When _agent_subprocess_env() is called
Then BEFORE the strip, IW_CORE_ORCH_DB_HOST/PORT/NAME/USER/PASSWORD are
  snapshotted from the daemon's IW_CORE_DB_* values
And the returned dict does NOT contain IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD
  inherited from the parent process (only ORCH_DB_* remain)
And on a legacy worktree whose .env still mirrors main (IW_CORE_DB_PORT=5433),
  the agent's orch.config.get_db_url() raises RuntimeError via Layer 3 (AC3)
  rather than silently connecting to the daemon's orch DB
```

### AC3: Bug is fixed — fail-fast in orch.config

```
Given a Python process where IW_CORE_AGENT_CONTEXT=true AND IW_CORE_ORCH_DB_PORT
  is set (always set by _agent_subprocess_env's snapshot, per AC2) AND the
  resolved IW_CORE_DB_PORT equals IW_CORE_ORCH_DB_PORT
When orch.config.get_db_url() is called
Then it raises a RuntimeError with a clear message naming the leak
And the message references this incident (I-00062) for the operator runbook
And get_orch_db_url() does NOT raise (it is the legitimate operator path
  that must reach the orch DB regardless of agent context)
```

### AC4: Reproduction test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/daemon/test_launch_step_env_isolation.py
  test_agent_subprocess_env_does_not_leak_orch_db_vars passes
And the analogous test_launch_step_injects_worktree_db_env passes
And the analogous test_orch_config_fails_fast_in_agent_context passes
```

### AC5: Persistence schema in place

```
Given a BatchItem row in the orch DB
When the worktree compose stack comes up
Then BatchItem.worktree_db_host, worktree_db_name, worktree_db_user,
  worktree_db_password are populated alongside worktree_db_port
And the alembic migration is reversible (downgrade drops all four columns)
```

### AC6: No regression in existing browser-verification env injection

```
Given a step whose browser-verification env injection currently works
  (e.g. F-00077 S19 BrowserVerification)
When that step is launched after I-00062 fix
Then the browser-verification env still wins (uses extra={...} merge),
  and IW_CORE_DB_PORT/HOST/NAME/USER/PASSWORD point at the e2e
  testcontainer, not at the daemon's orch DB
```

## Regression Prevention

Three structural changes are introduced specifically to prevent recurrence:

1. **Strip-by-default in `_agent_subprocess_env`**: removes the temptation
   for any future call site to rely on inherited daemon DB credentials.
2. **Persisted per-worktree DB credentials**: makes injection a single read
   from the DB, not a multi-source assembly. No way for partial state to
   silently fall back to inherited env.
3. **Fail-fast guard in `orch/config.py`**: catches any future regression
   where some new code path inherits the orch DB env in agent context.
   Crashes loudly with a referenced runbook (this incident) instead of
   writing silently to the wrong DB.

Additional process improvement (out of scope, suggested for follow-up):
mark the agent prompt boilerplate's "MUST NOT run alembic upgrade" rule as
**redundant guidance** rather than primary defense — the structural fixes
make the rule machine-enforced.

## Dependencies

- **Depends on**: None
- **Blocks**: F-00077 (currently paused at S21 needs_fix; cannot resume safely
  until I-00062 ships, otherwise the next fix-cycle agent that runs `make`
  will re-apply the leak).

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/batch_manager.py`
- `orch/daemon/worktree_compose.py`
- `orch/config.py`
- `tests/unit/daemon/test_agent_subprocess_env.py`
- `tests/integration/daemon/test_launch_step_env_isolation.py`
- `tests/unit/orch_config/test_agent_context_failfast.py`

## TDD Approach

- **Reproducing tests** (RED before S03):
  - `test_agent_subprocess_env_does_not_leak_orch_db_vars` — fails on main
  - `test_launch_step_injects_worktree_db_env` — fails on main (env not injected)
  - `test_orch_config_fails_fast_in_agent_context` — fails on main (no guard)
- **Unit tests**:
  - `_agent_subprocess_env`: strips `IW_CORE_DB_*`; preserves other env;
    `extra={...}` still wins.
  - `orch.config.get_db_url`: in agent context, raises when resolved port ==
    operator's known orch port; raises with clear I-00062 reference.
- **Integration tests**:
  - `_launch_step` with a fake `BatchItem` (all four `worktree_db_*` columns
    set): spawned subprocess sees per-worktree DB env, not 5433.
  - Migration round-trip: upgrade adds columns, downgrade drops them, both
    against a testcontainer.

## Notes

- **Deployment runbook**: any `BatchItem` with
  `worktree_compose_path IS NOT NULL` and `worktree_db_host IS NULL` after
  this fix lands must be paused and re-set-up so a fresh `worktree_compose
  .up()` populates the four new columns. The S03 `_launch_step` injection
  block raises `RuntimeError` if a compose-stack item is launched with
  incomplete creds — by design (refuse to launch is safer than silent
  fallback). F-00077 (currently paused at S21 needs_fix) is the only
  known item in this state at write time and is expected to be
  re-launched fresh post-merge.
- This incident was identified during operator triage of F-00077 BATCH-00074
  on 2026-05-03. The orch DB had been written to with revision
  `e53ce8e86a3c` (F-00077's own migration) although F-00077 had not merged.
  Cleanup performed before this incident was written: orch DB downgraded to
  `4876b3246ff2`, per-worktree DB on container `iwcore-141-db-1` upgraded to
  `e53ce8e86a3c`, BATCH-00074 paused. F-00077 cannot resume safely until
  I-00062 ships.
- The bug exists in main today and would have produced the same outcome on
  any prior Feature with a per-worktree DB and a migration. F-00077 is the
  first observed instance because it is the first such Feature in the
  current batch.
- Do **NOT** attempt to fix this by changing `orch/config.py` to
  `load_dotenv(..., override=True)` globally — that would also affect the
  daemon and dashboard processes and could reboot them onto the wrong DB if
  any local `.env` ever drifts from production. The fix is at the agent-env
  boundary, not at the dotenv boundary.
- The reserved ID I-00061 is in use by an unrelated approved item; this
  incident received the next free ID (I-00062) via a normal `iw next-id`
  call.
