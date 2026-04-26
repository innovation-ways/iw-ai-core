# I-00041_S02_CodeReview_Backend_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Same rules as the implementation prompt. Read-only introspection only.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md`
- `orch/db/live_db_guard.py` (new)
- `orch/db/session.py` (modified — `safe_create_engine` chokepoint, lazy `__getattr__`)
- `orch/db/safe_migrate.py` (modified — 4 sites + alembic config defensive call)
- `orch/daemon/main.py` (modified — `create_session_factory` line 64)
- `orch/daemon/migration_pipeline.py` (modified — lines 231, 266)
- `orch/daemon/migration_rebase.py` (modified — lines 210, 239)
- `orch/daemon/worktree_compose.py` (modified — line 224)
- `orch/cli/merge_queue_commands.py` (modified — line 51)

## Output Files

- Report: `ai-dev/active/I-00041/reports/I-00041_S02_CodeReview_Backend_report.md`

## Context

You are reviewing the connection-layer chokepoint that S01 added. The fix is
**critical** because it prevents silent live-DB writes from any pytest
process. Be thorough. Findings should match the design doc's structure;
don't accept "close enough."

## Review Checklist

### 1. Public API correctness

- [ ] `LiveDbConnectionRefused` is a `RuntimeError` subclass (not `Exception`)
      so existing code that catches `Exception` doesn't accidentally swallow it.
- [ ] `is_live_db_url(url)` matches the design doc priority: fingerprint via
      `IW_CORE_EXPECTED_INSTANCE_ID` first, host:port second, fail-open on
      parse error.
- [ ] `assert_engine_url_allowed(url)` honours both refused-context env vars
      (`IW_CORE_TEST_CONTEXT`, `IW_CORE_AGENT_CONTEXT`) and both allowed-context
      env vars (`IW_CORE_OPERATOR_APPLY`, `IW_CORE_DAEMON_CONTEXT`).
- [ ] Error message contains: URL host:port, the active refused-context flag
      name, and the remediation hint pointing operators at
      `iw migrations apply --i-am-operator` / daemon entry point.
- [ ] No state at module load time. All env-var reads at call time.

### 2. Chokepoint completeness (SINGLE-CHOKEPOINT INVARIANT)

- [ ] `safe_create_engine` is exported from `orch.db.session`.
- [ ] **Every** `create_engine(...)` call in **all of `orch/`** is replaced
      with `safe_create_engine(...)`. The canonical check (must show ONE
      match — the chokepoint itself):
      ```bash
      grep -rnE "create_engine\(" orch/ --include='*.py' \
        | grep -v "live_db_guard" \
        | grep -v "safe_create_engine"
      ```
      Specifically verify each S01 R3 site:
      - `orch/db/safe_migrate.py` lines 170, 200, 312, 346 → all replaced
      - `orch/daemon/main.py` line 64 (`create_session_factory`) → replaced
      - `orch/daemon/migration_pipeline.py` lines 231, 266 → replaced
      - `orch/daemon/migration_rebase.py` lines 210, 239 → replaced
      - `orch/daemon/worktree_compose.py` line 224 → replaced
      - `orch/cli/merge_queue_commands.py` line 51 → replaced
- [ ] `_build_alembic_config` calls `assert_engine_url_allowed(url)` so that
      `command.upgrade/downgrade(cfg, ...)` paths are also gated.
- [ ] Existing `_assert_not_agent_context` is deprecated (delegates + warns)
      but NOT removed. Confirm `DeprecationWarning` is raised on call.
- [ ] No raw `create_engine` outside `orch/db/session.py` itself. The chokepoint
      is single. (Tests under `tests/` are exempt — they use testcontainer URLs
      which are not the live DB.)
- [ ] Operator-vs-test priority is implemented per S01 R1 docstring matrix:
      allowed-context flags (operator/daemon) WIN over refused-context flags
      (test/agent). Verify with the smoke check from S01 R1 — must print
      `operator wins ok`.

### 3. Layer boundaries

- [ ] `orch/db/live_db_guard.py` does NOT import from `orch/daemon/` or `dashboard/`.
- [ ] No circular imports. (`from orch.db.session import safe_create_engine`
      inside `safe_migrate.py` is fine.)
- [ ] No new third-party deps in `pyproject.toml`.

### 4. Behavioural edge cases

- [ ] URL with same host:port but missing `IW_CORE_EXPECTED_INSTANCE_ID` and
      missing `IW_CORE_DB_HOST`/`IW_CORE_DB_PORT` env vars → guard fails open
      (returns False from `is_live_db_url`). Verified with a one-line repro.
- [ ] URL with explicit fingerprint that DOESN'T match the env's expected
      instance ID → not the live DB → allowed. (Important for testcontainers
      that happen to bind 5433 in CI — extremely rare but the guard must not
      false-positive.)
- [ ] `IW_CORE_OPERATOR_APPLY=true` + `IW_CORE_TEST_CONTEXT=true` set
      simultaneously → operator wins (confirms separation-of-concerns: an
      operator running the CLI inside a pytest sub-process is intentional).
      Or — if the design says test-context wins — confirm the docstring
      reflects that.
- [ ] Repeated calls with the same env state are idempotent (no caching).
- [ ] Engine creation is lazy in `orch.db.session` — importing the module
      does NOT open a connection or fire the guard. Verify with
      `python -c "import orch.db.session"` succeeding under
      `IW_CORE_TEST_CONTEXT=true`.

### 5. Backwards compatibility

- [ ] Public names `engine`, `SessionLocal`, `get_session` still exist in
      `orch.db.session` with the same signatures.
- [ ] Existing callers of `_assert_not_agent_context` in `safe_migrate.py`
      still work (they continue to be called; the deprecation warning fires
      once per call site).
- [ ] No alembic migration file added. Verify
      `git diff --stat orch/db/migrations/versions/` shows no changes.
- [ ] `dashboard/`, `orch/daemon/`, `orch/cli/` were NOT modified by this step.
      (Those changes belong to S03.)

### 6. Code quality

- [ ] Type hints on every public function and dataclass field.
- [ ] No `print()`. No bare `except:`.
- [ ] No backwards-compat shims for the new helper (it's brand-new code; no
      old callers exist to keep working).
- [ ] No hardcoded ports / URLs / credentials.
- [ ] Comments are minimal — only one for the fingerprint-vs-host:port
      priority decision (the WHY).

### 7. Observability

- [ ] Logger name is `orch.db.live_db_guard`.
- [ ] Refusals are logged at WARNING level (not ERROR — they are expected,
      not failures), with structured fields: `host`, `port`, `refused_by`,
      `caller_module`.
- [ ] No log spam: each refusal logs once per call. (No retry loops in the
      guard itself.)

### 8. Scope drift

- [ ] No changes outside the files listed in the design's S01 Code Changes:
      `orch/db/live_db_guard.py` (new), `orch/db/session.py`,
      `orch/db/safe_migrate.py`, `orch/daemon/main.py`,
      `orch/daemon/migration_pipeline.py`, `orch/daemon/migration_rebase.py`,
      `orch/daemon/worktree_compose.py`, `orch/cli/merge_queue_commands.py`.
- [ ] No refactoring of `identity.py` or other adjacent modules.
- [ ] No changes to `tests/`. (S05 owns tests; S03 owns conftest polarity.)
- [ ] No changes to `orch/daemon/__main__.py`, `orch/daemon/batch_manager.py`,
      `orch/daemon/fix_cycle.py`, `orch/daemon/doc_job_poller.py`, or
      `orch/cli/migrations_commands.py` — those belong to S03.

## Manual Verification

Run these and paste outputs in your report:

```bash
# 1. Import smoke
uv run python -c "from orch.db.live_db_guard import LiveDbConnectionRefused, is_live_db_url, assert_engine_url_allowed; print('OK')"

# 2. Importing session does NOT trigger the guard
IW_CORE_TEST_CONTEXT=true uv run python -c "import orch.db.session; print('session import OK')"

# 3. Confirm raw create_engine is gone from orch/db/safe_migrate.py
grep -nE "create_engine\(" orch/db/safe_migrate.py

# 4. Confirm safe_create_engine is the chokepoint
grep -n "safe_create_engine" orch/db/session.py orch/db/safe_migrate.py

# 5. Confirm deprecation wrapper is in place
grep -n "DeprecationWarning" orch/db/safe_migrate.py
```

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO),
`file:line`, and a one-line verdict per item. End with an overall verdict
(`PASS` / `NEEDS_FIX` / `BLOCKED`) and the appropriate `iw step-done` or
`iw step-fail` call.

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S02
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S02 --report ai-dev/active/I-00041/reports/I-00041_S02_CodeReview_Backend_report.md
```
