# I-00040: Alembic-version guard at daemon/dashboard/launch boundaries

**Type**: Issue
**Severity**: High
**Created**: 2026-04-26
**Reported By**: Operator (sergio) — observed live during CR-00022 execution
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

Allowed exceptions: testcontainers spun up by pytest fixtures, read-only
introspection (`docker ps`, `docker inspect`, `docker logs`), and
invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. Your job in any
Database step is to WRITE the migration FILE; the daemon applies it.
This issue ADDS NO new migration — it only adds runtime guards.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Description

The orchestration daemon and the FastAPI dashboard have no startup-time check
that the live orchestration DB's `alembic_version` matches the head of the
`orch/db/migrations/versions/` script directory. When a migration is merged
to `main` but never applied to the live DB on port 5433, both processes start
cleanly, then fail silently for hours: SQLAlchemy raises `UndefinedColumn`
on every poll cycle, the dashboard 500s on any page that touches new columns,
and downstream side-effects (per-worktree compose stacks, batch state
transitions) corrupt in subtle ways. Today this caused CR-00022's per-worktree
compose stack to be lost, and the agent ran for hours against a half-broken
environment.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Most relevantly:
- `orch/db/safe_migrate.py` already has `list_pending_revisions(db_url)` and
  `_current_revision_from_db(db_url)` — the comparison helpers we need.
- `orch/db/identity.py` is the canonical pattern for a "fail-fast at boot"
  DB precondition (CR-00014). The new alembic guard should mirror that style.
- The daemon entry point is `orch/daemon/main.py`. The dashboard factory is
  `dashboard/app.py::create_app`. Item launch happens in
  `orch/daemon/batch_manager.py::_launch_item` (or its `process_*` helpers
  around line 300).

## Steps to Reproduce

1. Add a new migration to `orch/db/migrations/versions/` (e.g. one that adds
   columns to `batch_items`).
2. Merge the migration to `main` but DO NOT run `make db-migrate` against the
   live orch DB on port 5433.
3. Start the daemon (`./ai-core.sh daemon start`) and the dashboard
   (`./ai-core.sh dashboard start`).
4. Approve a batch and let the daemon launch it.

**Expected**:
- Daemon refuses to start. STDERR contains a CRITICAL message naming the
  current DB revision and the head, and the remediation command
  (`make db-migrate`). Exit code is non-zero.
- Dashboard refuses to serve any UI write action and renders a global red
  banner on every page describing the mismatch and the fix command.
- If somehow a daemon already started successfully (e.g. mismatch occurred
  mid-run after a hot-deploy), `_launch_item` re-checks the DB before creating
  a worktree and marks the BatchItem `setup_failed` with a clear notes string
  including the two revisions and the fix command.

**Actual**:
- Daemon starts. Dashboard starts. Both look healthy in `./ai-core.sh status`.
- Daemon's poll cycle errors with `psycopg.errors.UndefinedColumn` every 60s
  (logged as "Error processing batch BATCH-XXXXX") for hours.
- Dashboard pages that touch the missing column return HTTP 500 with no
  user-visible explanation.
- `_launch_item` proceeds, creates the worktree, runs `worktree_compose.up()`
  successfully, then silently fails the UPDATE that persists
  `worktree_db_port`/`worktree_app_port`/`worktree_compose_path`. The
  re-attach loop in `orch/daemon/main.py:403` filters by
  `worktree_compose_path IS NOT NULL`, so the in-flight item is invisible to
  the daemon's tracking and its compose stack eventually gets torn down.
- The agent runs for hours against a half-broken environment.

## Browser Evidence

**Pre-fix**: Not captured. Reproducing the bug end-to-end in a browser
requires intentionally downgrading the live orchestration DB, which is
destructive and out of scope for evidence gathering.

**Post-fix verification**: Performed in the QV browser step (S13), which:
1. Runs inside the per-worktree compose stack (NOT against the live orch
   DB on port 5433).
2. Downgrades the per-worktree DB by one revision.
3. Loads the dashboard and asserts the red banner appears with the
   expected revisions and remediation copy, write-action buttons are
   disabled, and a state-mutating endpoint returns HTTP 503.
4. Restores the per-worktree DB and asserts the banner clears.

This is safe because the per-worktree compose stack uses an ephemeral
DB destroyed when the worktree is reaped.

## Root Cause Analysis

There is no point in the codebase that compares
`orch/db/migrations/versions/`'s ScriptDirectory head to the live DB's
`alembic_version.version_num`. Specifically:

- `orch/daemon/main.py` startup sequence calls `verify_instance_identity`
  but no alembic-head check.
- `dashboard/app.py::create_app` configures DB session/engine but no
  alembic-head check.
- `orch/daemon/batch_manager.py:325-336` does:

  ```python
  batch_item.worktree_db_port = up_db_port
  batch_item.worktree_app_port = up_app_port
  batch_item.worktree_compose_path = str(cfg.rendered_compose_path)
  ```

  These attribute assignments are silent SQLAlchemy attribute writes; the
  `UndefinedColumn` only surfaces on the next `db.commit()`, which is wrapped
  in a broader `try/except` in `_poll_cycle`. The exception is swallowed,
  the transaction is rolled back, and the daemon retries the same poll cycle
  next interval — so the failure is structural and recurring rather than
  loud.

- `orch/daemon/main.py:403`'s re-attach query:

  ```python
  q.filter(BatchItem.worktree_compose_path.isnot(None), ...)
  ```

  silently excludes items whose compose stack was set up successfully but
  whose DB persistence failed — exactly the items that need recovery the
  most.

The helpers needed for the guard already exist in
`orch/db/safe_migrate.py`:

- `list_pending_revisions(db_url) -> list[Revision]` — returns non-empty
  iff the DB is behind any head, raises `MultipleHeadsError` if the
  graph has >1 head.
- `_current_revision_from_db(db_url) -> str | None` — reads
  `alembic_version.version_num`.
- `current_revision(db_url)` (line 577) — the public form of the above.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/main.py` (startup) | No alembic-head check → starts on stale DB |
| `dashboard/app.py::create_app` | No alembic-head check → serves 500s on stale DB |
| `orch/daemon/batch_manager.py::_launch_item` | Silent UPDATE failure on stale DB → corrupt BatchItem state |
| `orch/db/migrations/` (new helper) | None today; will gain a new module `orch/db/alembic_guard.py` |
| Dashboard base template | Today renders nothing on mismatch; will gain a global red banner controlled by a request-state flag |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | New `orch/db/alembic_guard.py` (`assert_db_at_head`, `check_db_at_head` returning a status object). Wire into `orch/daemon/main.py` startup (abort + non-zero exit on mismatch), `dashboard/app.py::create_app` (attach status to app state + register middleware that sets a request flag), and `orch/daemon/batch_manager.py::_launch_item` (re-check before worktree creation; mark `setup_failed` with notes including `current_rev`, `head_rev`, `make db-migrate`). | — |
| S02 | code-review-impl | Review S01: helper API, exception types, log severity, exit code, batch_item state transitions, no `alembic upgrade` performed (operator-only). | — |
| S03 | frontend-impl | Add the global stale-DB banner to `dashboard/templates/base.html` (red bar above nav, dismissible only via fixing the DB) reading the request-state flag set by the S01 middleware. Disable batch-approval and item-launch buttons when the flag is set. | — |
| S04 | code-review-impl | Review S03: banner copy, accessibility (role="alert"), no emoji, button-disabled states, htmx swap targets unaffected. | — |
| S05 | tests-impl | Reproduction test (creates a testcontainer, applies all migrations, then `alembic downgrade -1`, then asserts: `assert_db_at_head` raises with both revisions in the message; `_launch_item` marks `setup_failed`; dashboard `TestClient` GET `/` contains the banner markup). Regression tests for: matching state passes silently; `MultipleHeadsError` mapped to a clear actionable message. | — |
| S06 | code-review-impl | Review S05 tests for semantic correctness (assert specific revision strings appear, not just "banner exists"). | — |
| S07 | code-review-final-impl | Global review across S01/S03/S05. | — |
| S08 | qv-gate | `make lint` | — |
| S09 | qv-gate | `make format` | — |
| S10 | qv-gate | `make typecheck` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make allure-integration` | — |
| S13 | qv-browser | Inside the per-worktree compose stack, downgrade the worktree DB one revision; assert dashboard banner appears with both revisions and the `make db-migrate` remediation copy; assert batch-approval / item-launch buttons are disabled. | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: This issue adds NO migration. It strictly adds runtime guards over existing schema. The fix MUST be safe to deploy against a fully migrated DB without any operator action.

### Code Changes

- **Files to create**:
  - `orch/db/alembic_guard.py` (new helper)
  - `tests/unit/test_alembic_guard.py` (unit tests)
  - `tests/integration/test_alembic_guard_integration.py` (mismatch reproduction in testcontainer)
- **Files to modify**:
  - `orch/daemon/main.py` (startup hook)
  - `dashboard/app.py` (create_app hook + middleware)
  - `orch/daemon/batch_manager.py` (re-check before worktree creation)
  - `dashboard/templates/base.html` (banner)
  - Possibly a small `dashboard/middlewares/alembic_guard.py` if a separate file is cleaner.
- **Nature of change**: Add precondition checks at three boundaries. Fail loud, not silent. Use existing helpers in `orch/db/safe_migrate.py`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/I-00040/I-00040_Issue_Design.md` | Design | This document |
| `ai-dev/active/I-00040/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/I-00040/prompts/I-00040_S01_Backend_prompt.md` | Prompt | S01 fix instructions |
| `ai-dev/active/I-00040/prompts/I-00040_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review |
| `ai-dev/active/I-00040/prompts/I-00040_S03_Frontend_prompt.md` | Prompt | S03 fix instructions |
| `ai-dev/active/I-00040/prompts/I-00040_S04_CodeReview_Frontend_prompt.md` | Prompt | S04 review |
| `ai-dev/active/I-00040/prompts/I-00040_S05_Tests_prompt.md` | Prompt | S05 tests |
| `ai-dev/active/I-00040/prompts/I-00040_S06_CodeReview_Tests_prompt.md` | Prompt | S06 review |
| `ai-dev/active/I-00040/prompts/I-00040_S07_CodeReview_Final_prompt.md` | Prompt | S07 global review |
| `ai-dev/active/I-00040/prompts/I-00040_S13_BrowserVerification_prompt.md` | Prompt | S13 browser verification |

Reports created during execution in `ai-dev/active/I-00040/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

```python
def test_i00040_reproduces_silent_mismatch_failure(testdb_url):
    """Pre-fix: daemon and dashboard start cleanly even when DB is behind head.

    Post-fix: assert_db_at_head raises a DBBehindHeadError with both
    revisions in the message.
    """
    # Arrange: testcontainer at head, then downgrade by one
    _run_alembic("upgrade", "head", testdb_url)
    head_rev = _current_head()
    _run_alembic("downgrade", "-1", testdb_url)
    current_rev = _current_revision_from_db(testdb_url)
    assert current_rev != head_rev

    # Act + Assert (post-fix expectation)
    from orch.db.alembic_guard import DBBehindHeadError, assert_db_at_head
    with pytest.raises(DBBehindHeadError) as exc:
        assert_db_at_head(testdb_url)
    assert head_rev in str(exc.value)
    assert current_rev in str(exc.value)
    assert "make db-migrate" in str(exc.value)
```

## Browser Verification Test

Run inside the worktree's compose stack via `playwright-cli`:

```bash
# Provided by the daemon at QV time:
# $IW_BROWSER_BASE_URL, $IW_BROWSER_E2E_USER, $IW_BROWSER_E2E_PASSWORD,
# $IW_ITEM_ID, $IW_STEP_ID

playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
# Pre-condition: the worktree DB has been downgraded one revision by the
# step's setup script (NOT this prompt). The banner must already be present.
playwright-cli snapshot                 # capture banner
playwright-cli screenshot ai-dev/active/I-00040/reports/banner-visible.png

# Banner is rendered with role="alert" and contains both revisions and copy
playwright-cli text "[role='alert']"

# Item-launch / batch-approve buttons must be disabled
playwright-cli attribute "button[data-action='batch-approve']" disabled

# Navigate to /project/iw-ai-core/batches and assert no 500 (banner shown,
# rest of page degraded gracefully)
playwright-cli open "$IW_BROWSER_BASE_URL/project/iw-ai-core/batches"
```

## Acceptance Criteria

### AC1: Daemon refuses to start on mismatch

```
Given a live DB whose alembic_version is behind the script-directory head
When the daemon starts
Then it logs a CRITICAL message naming current_rev, head_rev, and "make db-migrate"
And exits with a non-zero exit code
```

### AC2: Dashboard renders a stale-DB banner on every page

```
Given a live DB whose alembic_version is behind the script-directory head
When any HTTP request hits the dashboard
Then the response renders a global red banner with role="alert"
And the banner contains both revisions and the remediation command
And batch-approval / item-launch buttons are disabled
```

### AC3: Item launch fails fast with a clear note

```
Given the daemon is somehow already running on a stale DB
When batch_manager._launch_item is called for a queued BatchItem
Then the BatchItem is set to status=setup_failed before any worktree is created
And BatchItem.notes contains current_rev, head_rev, and "make db-migrate"
And no .worktrees/<id> directory is created on disk
```

### AC4: Regression tests exist and verify semantic correctness

```
Given the fix is applied
When the test suite runs
Then test_alembic_guard.py asserts SPECIFIC revision strings (not "is non-empty")
And test_alembic_guard_integration.py reproduces the mismatch in a testcontainer
And both tests fail against the pre-fix code and pass against the post-fix code
```

## Regression Prevention

- **Structural**: The guard runs at three explicit entry points (daemon
  startup, dashboard create_app, item launch). New entry points (e.g. CLI
  subcommands that mutate orch state) should add a `@require_db_at_head`
  decorator or a `_check_or_die()` call.
- **Validation**: The helper raises a typed exception (`DBBehindHeadError`,
  `MultipleHeadsError`) that the caller cannot easily ignore — silent
  `try/except Exception` will be flagged in code review.
- **Observability**: A `daemon_events` row of type `db_schema_mismatch` is
  emitted on every detection, so operators can see the problem in the
  dashboard event log even if they miss the stderr line.
- **Test coverage**: Both unit (helper) and integration (testcontainer
  reproduction) coverage. The integration test is the canonical "did the
  guard actually wire up correctly" test.

## Dependencies

- **Depends on**: None. Helpers in `orch/db/safe_migrate.py` already exist.
- **Blocks**: None — this issue improves operational safety; it does not
  unblock any feature work.
- **Note**: This issue MAY merge before or after CR-00022. There is no
  conflict between them.

## TDD Approach

- **Reproducing test**: `tests/integration/test_alembic_guard_integration.py`
  — spins up a testcontainer, upgrades to head, downgrades by one, asserts
  `assert_db_at_head()` raises with both revisions in the message.
- **Unit tests**: `tests/unit/test_alembic_guard.py` — verifies the
  exception types, message format, daemon-event payload, and the `setup_failed`
  notes string format. Mocks the DB-revision read.
- **Integration tests**:
  - Daemon startup mismatch: build the daemon CLI with a mismatched
    testcontainer and assert non-zero exit.
  - Dashboard create_app mismatch: instantiate `create_app()` against a
    mismatched testcontainer and assert a `TestClient.get("/")` returns a
    page containing the banner markup.
  - `_launch_item` mismatch: feed a queued BatchItem to the launcher and
    assert it transitions to `setup_failed` with the expected notes.

## Notes

- The dashboard guard MUST NOT refuse to serve at all — operators need read
  access to history pages to diagnose. The banner + disabled write actions
  is the right balance.
- The daemon guard MUST refuse to start at all (exit non-zero). A daemon
  running on a stale DB is unsafe: it will keep launching agents into a
  half-broken environment.
- This is the second issue in a short window where a "merge but don't apply"
  migration caused operational damage. Worth treating as a class fix, not
  just a one-off.
- Out of scope: auto-running migrations from the daemon. That remains an
  explicit operator action (`make db-migrate` or `./ai-core.sh db migrate`).
