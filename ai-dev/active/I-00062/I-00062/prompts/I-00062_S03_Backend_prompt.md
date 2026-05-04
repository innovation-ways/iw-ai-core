# I-00062_S03_Backend_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step**: S03
**Agent**: Backend (`backend-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection (`docker ps`, `docker inspect`, `docker logs`) and
`./ai-core.sh` / `make` targets are allowed. Testcontainer fixtures
spawned by pytest are exempt. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB on port 5433. **This incident is itself about a violation of this rule
via transitive `make` invocation — do not repeat it. Do not run `make`,
`make install`, or any target whose recipe contains `alembic upgrade
head`.** `alembic history/current/show` is read-only and allowed.

`make format`, `make typecheck`, `make lint` are required pre-flight
gates and are safe — they do not invoke alembic.

`make test-unit` and `make test-integration` are required test-verification
gates. They use testcontainers (Ryuk-managed), not the live orch DB —
allowed.

`make` with no target IS the dangerous form (it runs `install` which runs
`alembic upgrade head`). NEVER run bare `make` from a worktree.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document
- `ai-dev/active/I-00062/reports/I-00062_S01_Database_report.md` — S01 report
- `ai-dev/active/I-00062/reports/I-00062_S02_CodeReview_report.md` — S02 review
- `orch/daemon/batch_manager.py` — `_agent_subprocess_env`,
  `_launch_step`, `worktree_info` assembly (around lines 580–680, 1100–1170,
  1430–1470)
- `orch/daemon/worktree_compose.py` — `load_config`, `up`, `UpResult`
  (this is where per-worktree DB host/name/user/password are knowable)
- `orch/config.py` — `get_db_url`, `get_orch_db_url`, `_require`
- `orch/db/models.py` — `BatchItem` (after S01 has the four new columns)
- For runtime step state, prefer `uv run iw item-status I-00062 --json`.

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S03_Backend_report.md` — step report
- `orch/daemon/worktree_compose.py` — modified (expose DB credentials in `UpResult`)
- `orch/daemon/batch_manager.py` — modified (`_launch_step` injection,
  `_agent_subprocess_env` stripping, populate persisted columns at compose-up)
- `orch/config.py` — modified (fail-fast guard)

## Context

You are implementing the structural defense-in-depth for I-00062. Three
independent layers, all must ship together. Read
`I-00062_Issue_Design.md` first — sections "Root Cause Analysis", "Code
Changes", and "Acceptance Criteria" are the source of truth.

Read `orch/CLAUDE.md` for daemon module conventions.

## Requirements

### 1. Expose per-worktree DB credentials in `worktree_compose.UpResult`

`worktree_compose.up()` already returns a `UpResult` with `discovered_ports
: dict[str, str]` (port name → port string). The host/name/user/password
for the per-worktree DB live in the rendered `worktree-env.toml` /
`worktree-compose.template.yml`. Extend `UpResult` with:

```python
discovered_db_credentials: dict[str, str]
```

Populate it inside `worktree_compose.up()` (or its helper `_render_compose`
/ `_run_compose_up`) by reading the resolved values for `IW_CORE_DB_HOST`,
`IW_CORE_DB_NAME`, `IW_CORE_DB_USER`, `IW_CORE_DB_PASSWORD` from the
already-rendered config. Keys are the env var names so the consumer doesn't
have to translate.

If the DB stack is not present (project without `ai-dev/iw-config/`),
return an empty dict — never raise.

Do NOT change `discovered_ports` shape. Add the new field as an additional
attribute so existing call sites are untouched.

### 2. Persist the credentials onto `BatchItem` at compose-up

In `orch/daemon/batch_manager.py`, in the section around line 580–620 that
already does:

```python
up_db_port = up_result.discovered_ports.get("IW_CORE_DB_PORT")
batch_item.worktree_db_port = (
    int(up_db_port) if up_db_port is not None else None
)
```

Extend it to also set:

```python
creds = up_result.discovered_db_credentials or {}
batch_item.worktree_db_host = creds.get("IW_CORE_DB_HOST")
batch_item.worktree_db_name = creds.get("IW_CORE_DB_NAME")
batch_item.worktree_db_user = creds.get("IW_CORE_DB_USER")
batch_item.worktree_db_password = creds.get("IW_CORE_DB_PASSWORD")
```

In the failure / no-compose branches, set all four to `None` (mirror the
existing `worktree_db_port = None` pattern).

In the `worktree_info` assembly around line 660–670, also pass these
through so `_launch_step` can read them without hitting the DB twice:

```python
if batch_item.worktree_compose_path is not None:
    worktree_info["worktree_compose_path"] = batch_item.worktree_compose_path
    worktree_info["worktree_db_port"] = str(batch_item.worktree_db_port)
    worktree_info["worktree_app_port"] = str(batch_item.worktree_app_port)
    worktree_info["worktree_db_host"] = batch_item.worktree_db_host or ""
    worktree_info["worktree_db_name"] = batch_item.worktree_db_name or ""
    worktree_info["worktree_db_user"] = batch_item.worktree_db_user or ""
    worktree_info["worktree_db_password"] = batch_item.worktree_db_password or ""
    worktree_info["batch_item_id"] = str(batch_item.id)
    worktree_info["project_name"] = batch_item.project_id
```

### 3. Snapshot orch creds, then strip `IW_CORE_DB_*` in `_agent_subprocess_env` (baseline path)

In `orch/daemon/batch_manager.py:_agent_subprocess_env` (around line
1432), extend the existing strip block. After:

```python
env.pop("IW_CORE_DAEMON_CONTEXT", None)
env.pop("IW_CORE_OPERATOR_APPLY", None)
env.pop("VIRTUAL_ENV", None)
```

add (in this exact order — snapshot first, strip second):

```python
# I-00062: BEFORE stripping IW_CORE_DB_*, snapshot the daemon's orch DB
# values into IW_CORE_ORCH_DB_*. This generalises the snapshot that
# orch.daemon.browser_env._build_env already does for browser-
# verification steps to ALL agent launches, so the fail-fast guard in
# orch/config.py (Layer 3) always has a known orch reference to compare
# IW_CORE_DB_PORT against — including for legacy (no-compose-stack)
# worktrees whose .env still carries IW_CORE_DB_PORT=5433.
for src, dst in (
    ("IW_CORE_DB_HOST", "IW_CORE_ORCH_DB_HOST"),
    ("IW_CORE_DB_PORT", "IW_CORE_ORCH_DB_PORT"),
    ("IW_CORE_DB_NAME", "IW_CORE_ORCH_DB_NAME"),
    ("IW_CORE_DB_USER", "IW_CORE_ORCH_DB_USER"),
    ("IW_CORE_DB_PASSWORD", "IW_CORE_ORCH_DB_PASSWORD"),
):
    val = env.get(src)
    # setdefault: if a caller (or browser_env) has already injected
    # IW_CORE_ORCH_DB_*, do NOT overwrite it.
    if val:
        env.setdefault(dst, val)

# I-00062: strip IW_CORE_DB_* so agents cannot inherit credentials for
# the daemon's source-of-truth DB. Per-worktree DB env is injected
# explicitly in _launch_step when the worktree has a compose stack;
# otherwise the agent sources values from its worktree's .env via
# load_dotenv (and the Layer 3 guard catches a legacy mirror of
# IW_CORE_DB_PORT=5433 because of the snapshot above).
for key in (
    "IW_CORE_DB_HOST",
    "IW_CORE_DB_PORT",
    "IW_CORE_DB_NAME",
    "IW_CORE_DB_USER",
    "IW_CORE_DB_PASSWORD",
):
    env.pop(key, None)
```

The snapshot+strip happens BEFORE `IW_CORE_AGENT_CONTEXT=true` is armed,
and BEFORE the `extra` merge — so callers that pass per-worktree DB vars
in `extra={...}` (browser-verification path, the new injection in step
4) still win for IW_CORE_DB_*. The `setdefault` in the snapshot ensures
that if `extra` (or the existing browser_env path) has already populated
`IW_CORE_ORCH_DB_*`, we do not clobber it.

Do NOT remove or rename `IW_CORE_ORCH_DB_*` keys here — they are the
explicit operator path for `step-done` / `step-fail` / `step-start` and
must reach the orch DB. The snapshot only ADDs them when missing.

### 4. Inject per-worktree DB env in `_launch_step` (compose path)

In `orch/daemon/batch_manager.py:_launch_step` around line 1125–1130,
the existing block reads:

```python
agent_env = _agent_subprocess_env()
if bv_env is not None:
    agent_env = {**agent_env, **bv_env}
if worktree_info.get("worktree_compose_path") is not None:
    agent_env["IW_CORE_PER_WORKTREE_DB"] = "true"
```

Extend the compose-path branch so it explicitly injects all five DB env
vars from `worktree_info`:

```python
if worktree_info.get("worktree_compose_path") is not None:
    agent_env["IW_CORE_PER_WORKTREE_DB"] = "true"
    db_port = worktree_info.get("worktree_db_port")
    db_host = worktree_info.get("worktree_db_host") or ""
    db_name = worktree_info.get("worktree_db_name") or ""
    db_user = worktree_info.get("worktree_db_user") or ""
    db_password = worktree_info.get("worktree_db_password") or ""
    if db_port and db_host and db_name and db_user and db_password:
        agent_env["IW_CORE_DB_HOST"] = db_host
        agent_env["IW_CORE_DB_PORT"] = str(db_port)
        agent_env["IW_CORE_DB_NAME"] = db_name
        agent_env["IW_CORE_DB_USER"] = db_user
        agent_env["IW_CORE_DB_PASSWORD"] = db_password
    else:
        # Defensive: refuse to launch with incomplete per-worktree DB
        # credentials. Crash loudly rather than fall back to inherited
        # daemon env (which the strip in _agent_subprocess_env already
        # cleaned, but this is belt-and-suspenders).
        raise RuntimeError(
            f"I-00062: per-worktree DB compose stack is up for "
            f"{worktree_info.get('batch_item_id')} but credentials are "
            f"incomplete (host={bool(db_host)}, port={bool(db_port)}, "
            f"name={bool(db_name)}, user={bool(db_user)}, "
            f"password={bool(db_password)}). Refusing to launch."
        )
```

The `bv_env` (browser-verification env) merge already runs BEFORE this
block, so browser-verification's injected DB env wins for steps that use
it. Confirm this ordering visually before reporting complete — AC6
depends on it.

### 5. Fail-fast guard in `orch/config.py`

Add a private helper and call it from `get_db_url()` only (NOT from
`get_orch_db_url()`):

```python
_AGENT_LEAK_RUNBOOK = (
    "I-00062: agent subprocess resolved IW_CORE_DB_PORT to the "
    "operator's orch DB port. This indicates the agent inherited "
    "the daemon's orch DB credentials. See "
    "ai-dev/done/I-00062/I-00062_Issue_Design.md for the runbook."
)


def _check_agent_context_does_not_resolve_to_orch_port(port: str) -> None:
    """Refuse to return a DB URL when an agent process resolves to
    the operator's orch port — indicates env-leak from the daemon."""
    import os  # noqa: PLC0415

    if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() != "true":
        return
    operator_orch_port = os.environ.get("IW_CORE_ORCH_DB_PORT")
    if operator_orch_port is None:
        return
    if str(port) == str(operator_orch_port):
        raise RuntimeError(_AGENT_LEAK_RUNBOOK)
```

Call sites:

```python
def get_db_url() -> str:
    ...
    port = _require("IW_CORE_DB_PORT")
    _check_agent_context_does_not_resolve_to_orch_port(port)
    ...

def get_orch_db_url() -> str:
    ...
    port = _prefer("IW_CORE_ORCH_DB_PORT", "IW_CORE_DB_PORT")
    # Do NOT call the guard here — get_orch_db_url() is the legitimate
    # path that DOES want to reach 5433 (step-done / step-fail / step-start).
    ...
```

The guard is on `get_db_url()` only (the app-runtime path), not on
`get_orch_db_url()`. The orch-URL path is the legitimate operator
channel agents use for `iw step-done` etc.

The runbook string is exact — do not paraphrase. Tests will assert it.

### 6. Operator-context bypass

The operator's `make db-migrate` and `./ai-core.sh start` paths run with
`IW_CORE_AGENT_CONTEXT` unset (or empty). The guard short-circuits in that
case — no impact on operator workflows. Do NOT add a new bypass env var.

## TDD Requirement

The Tests step (S05) writes the permanent regression suite. For your own
GREEN cycle, you may write a quick scratch test under
`tests/_scratch/test_i_00062_smoke.py` that you delete before committing.
Do NOT leave scratch tests in the tree.

The reproducing tests are listed in `I-00062_Issue_Design.md` under "Test
to Reproduce" and "TDD Approach". Run them through your changes mentally
or with `pytest -k` and confirm they would pass after S03 lands.

## Project Conventions

Read `orch/CLAUDE.md` for daemon conventions:
- Sync SQLAlchemy 2.0 — daemon is single-threaded
- All operational state in PostgreSQL — no markdown, no in-memory
- `_agent_subprocess_env` is the canonical helper — do NOT bypass it

Read `CLAUDE.md` for the docker / migration rules.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run and fix:

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — must report zero errors involving the files you
   touched.
3. **`make lint`** — must report zero errors.

If a tool isn't available, STOP and raise a blocker. **Do NOT run bare
`make`.**

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass (uses testcontainers, safe).
3. Do **NOT** report `tests_passed: true` unless both pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "I-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/worktree_compose.py",
    "orch/daemon/batch_manager.py",
    "orch/config.py"
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
