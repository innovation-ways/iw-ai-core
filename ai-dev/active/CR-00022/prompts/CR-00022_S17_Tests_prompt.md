# CR-00022_S17_Tests_prompt

**Work Item**: CR-00022
**Step**: S17
**Agent**: tests-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules. Tests use **testcontainers** spun up by pytest fixtures (allowed exception). Never connect to live DB on port 5433 from tests.

## ⚠️ READ FIRST — Recovery context (2026-04-26)

A previous attempt at this step caused a **multi-hour outage of the live orchestration DB** because tests bypassed `safe_apply` / `safe_rollback` mocks via `orch/db/safe_migrate.py:_write_migration_log` (which calls `get_db_url()` directly) and corrupted `alembic_version` + `pending_migration_log`. Symptoms: dashboard 500s, daemon `UndefinedColumn` errors, `batch_items` columns silently dropped.

This step now begins with a **mandatory worktree-local safety patch (R0 below)** that closes the bypass before any test runs. Without R0, this step will recur the outage. R0 is small (~25 lines across 2 files) and is essentially the I-00041 fix scoped to the helpers we already know are leaking. When CR-00022 merges, the patches go to main; I-00041 then becomes a small follow-up that extends the same guard to other engine-creation paths.

## Input Files

- Design (§ TDD Approach + every AC)
- All implementation reports S01..S15
- `tests/CLAUDE.md` (testcontainer rules, FTS_FUNCTION_SQL/FTS_TRIGGER_SQL after create_all, psycopg URL replacement)
- All current OSS test files (`tests/{unit,integration}/test_oss_*.py`, `test_project_oss_job_migration.py`)

## Output Files

**R0 (safety patch — do this FIRST):**
- Updated: `tests/conftest.py` — invert opt-out → opt-in for the live-DB guard
- Updated: `orch/db/safe_migrate.py` — short-circuit `_write_migration_log`, `_acquire_migration_lock`, `_release_migration_lock` when test context is active
- Updated: `orch/daemon/migration_rebase.py` — short-circuit `_emit_daemon_event` and `_write_rebase_log` when test context is active (R0d — added after the first run leaked one row from `tests/integration/test_parallel_migrations.py`)
- Updated: `tests/conftest.py` — R0e env hijack (in addition to R0a's polarity inversion). Sets IW_CORE_DB_HOST=127.0.0.1, IW_CORE_DB_PORT=1, etc., so any code path that bypasses R0a/b/d and calls `get_db_url()` resolves to an unreachable URL and fails immediately with ConnectionRefusedError. Defense-in-depth.

**R1+ (the original test work — do AFTER R0 lands and is verified):**
- New: `tests/unit/test_oss_catalog_completeness.py`
- New: `tests/unit/test_oss_check_catalog_loader.py`
- New: `tests/unit/test_oss_accepted_yaml.py`
- New: `tests/unit/test_oss_fix_recipes_idempotent.py`
- New: `tests/unit/test_oss_honor_accepted.py`
- New: `tests/unit/test_safe_migrate_test_context.py` — locks in R0 (3 short tests)
- Updated: `tests/integration/test_oss_migration.py`
- Updated: `tests/integration/test_project_oss_job_migration.py`
- Updated: `tests/integration/test_oss_dashboard_routes.py`
- Updated: `tests/integration/test_oss_dashboard_sse.py`
- Updated: `tests/integration/test_oss_cli.py`
- Updated: `tests/integration/test_oss_dashboard_service.py`
- Updated: `tests/integration/test_oss_persistence.py`
- Updated: `tests/integration/test_oss_scanner.py`
- Updated: `tests/integration/test_oss_dashboard_templates_extras.py`
- `ai-dev/active/CR-00022/reports/CR-00022_S17_Tests_report.md`

## Context

Every AC in the design has at least one test. New tests live with the feature; existing tests are updated where S03/S07/S09/S11 broke them.

## Requirements

### 0. Worktree-local safety patch (MANDATORY PREREQUISITE — do this FIRST)

**Why**: tests in this branch can write to the live orchestration DB on port 5433 because (a) `tests/conftest.py:23` autouse-deletes `IW_CORE_AGENT_CONTEXT`, removing the existing guard, (b) `orch/db/safe_migrate.py:_write_migration_log` calls `get_db_url()` directly, bypassing mocks placed at `orch.daemon.migration_pipeline.{safe_apply,safe_rollback}`, and (c) `orch/daemon/migration_rebase.py` has its own session-opening helpers that bypass safe_migrate entirely. The bypasses already corrupted `alembic_version` 4+ times today. This patch closes them for the duration of CR-00022 and ships the fix to main when CR-00022 merges.

**Apply all three edits before doing anything else, then run the verification block at the bottom of R0. Do NOT proceed to R1 if verification fails.**

**NOTE (2026-04-26 19:35)**: R0a/R0b/R0d/R0e were applied to the worktree by earlier partial runs. **Run the verification block FIRST.** If everything passes, **skip the apply steps and proceed directly to R1**. If a step's "old" pattern is no longer found, that step is already applied — verify the new code is in place via the R0c grep checks and move on. R0e is the env-hijack in `tests/conftest.py` — verify with `grep "IW_CORE_DB_PORT.*=.*1" tests/conftest.py` (must match).

#### R0a — `tests/conftest.py`

Locate the existing autouse fixture (currently around line 16):

```python
@pytest.fixture(autouse=True)
def _isolate_agent_context_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IW_CORE_AGENT_CONTEXT", raising=False)
```

**Replace it with**:

```python
@pytest.fixture(autouse=True, scope="session")
def _arm_live_db_guard() -> None:
    """Arm the live-DB write guard for the entire pytest session.

    Sets IW_CORE_TEST_CONTEXT=true and clears any operator/daemon opt-in
    flags that might have leaked from the parent shell. Uses os.environ
    directly (NOT monkeypatch) so the flag persists across tests, into
    pytest-xdist workers, into subprocesses, and into testcontainers.

    See CR-00022 S17 R0 (and incident I-00041) for context. The previous
    opt-out fixture was the proximate cause of a multi-hour dashboard outage.
    """
    import os
    os.environ["IW_CORE_TEST_CONTEXT"] = "true"
    os.environ.pop("IW_CORE_OPERATOR_APPLY", None)
    os.environ.pop("IW_CORE_DAEMON_CONTEXT", None)
    os.environ.pop("IW_CORE_AGENT_CONTEXT", None)
```

The previous fixture is replaced (delete it), not added alongside. Its only purpose was to keep the parent shell's `IW_CORE_AGENT_CONTEXT` from leaking into pytest; the explicit `os.environ.pop(...)` calls above subsume that.

If any individual tests still need `IW_CORE_AGENT_CONTEXT` deleted (search with `grep -rn IW_CORE_AGENT_CONTEXT tests/`), they should keep their own `monkeypatch.delenv(...)` calls — those are unaffected.

#### R0b — `orch/db/safe_migrate.py`

Add a helper near the top of the file (just below the imports):

```python
def _is_test_context_active() -> bool:
    """Return True if pytest is running and no operator/daemon opt-in is set.

    When True, helpers in this module that would write to the live orch DB
    (`_write_migration_log`, `_acquire_migration_lock`, `_release_migration_lock`)
    short-circuit instead of executing. Prevents tests from corrupting
    `alembic_version` / `pending_migration_log` / `migration_locks` via the
    mock-bypass that flows through `get_db_url()`.

    See CR-00022 S17 R0 (and incident I-00041) for context.
    """
    if os.environ.get("IW_CORE_OPERATOR_APPLY") == "true":
        return False
    if os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true":
        return False
    return os.environ.get("IW_CORE_TEST_CONTEXT") == "true" or \
           os.environ.get("IW_CORE_AGENT_CONTEXT") == "true"
```

(`os` is already imported by this file. If not, `import os` at the top.)

Then, at the **first executable line** of each of these three functions, add the short-circuit:

1. `_write_migration_log(...)` — currently around line 187. First line of function body becomes:
   ```python
       if _is_test_context_active():
           return
   ```
2. `_acquire_migration_lock(item: str = "daemon") -> None` — currently around line 313. Same pattern: `if _is_test_context_active(): return`.
3. `_release_migration_lock(item: str = "daemon") -> None` — wherever it's defined. Same pattern.

Do NOT short-circuit `apply()`, `rollback()`, `dry_run()`, `current_revision()`, or `list_pending_revisions()` — those are entry points and the existing `_assert_not_agent_context(live_db_url)` check stays. The point of R0 is that even when those entry points are mocked, the deeper helpers can no longer leak.

#### R0d — `orch/daemon/migration_rebase.py`

This module has its own session-opening helpers that bypass `safe_migrate.py` entirely. They write `DaemonEvent` rows (`_emit_daemon_event`) and `PendingMigrationLog(phase='rebase')` rows (`_write_rebase_log`). One row leaked through R0b in the previous run from `tests/integration/test_parallel_migrations.py`. Close it.

Add the import at the top (just below the existing `from orch.db.models import DaemonEvent, PendingMigrationLog` line):

```python
from orch.db.safe_migrate import _is_test_context_active
```

Then at the **first executable line** of each helper, add the short-circuit:

1. `_emit_daemon_event(event_type, metadata, message)` — currently around line 203:
   ```python
       if _is_test_context_active():
           return
   ```
2. `_write_rebase_log(revision, old_revision, batch_id)` — currently around line 232:
   ```python
       if _is_test_context_active():
           return
   ```

Same shape as R0b. Both helpers become no-ops under test context; production daemon code (which sets `IW_CORE_DAEMON_CONTEXT=true`) is unaffected.

#### R0c — Verification (mandatory before R1)

```bash
# 1. The new fixture is autouse + session-scoped.
grep -A2 "_arm_live_db_guard" tests/conftest.py

# 2. The helper exists in safe_migrate.py.
grep -n "_is_test_context_active" orch/db/safe_migrate.py

# 3. Each of the three helpers short-circuits.
grep -B1 -A3 "_is_test_context_active()" orch/db/safe_migrate.py
# Expect: 3 matches, one inside each helper.

# 4. Manual smoke: under test context, _write_migration_log is a no-op.
IW_CORE_TEST_CONTEXT=true uv run python -c "
from orch.db.safe_migrate import _write_migration_log
_write_migration_log('test', 'upgrade', 'apply', 99999, True, '', '', None)
print('OK: short-circuit fired (no exception, no row written)')
"

# 5. Confirm: with operator opt-in, the helper would NOT short-circuit.
IW_CORE_TEST_CONTEXT=true IW_CORE_OPERATOR_APPLY=true uv run python -c "
from orch.db.safe_migrate import _is_test_context_active
assert not _is_test_context_active(), 'operator opt-in must override test context'
print('OK: operator opt-in works')
"

# 6. R0d — migration_rebase helpers also short-circuit.
grep -B1 -A2 "_is_test_context_active" orch/daemon/migration_rebase.py
# Expect: import line + 2 short-circuit blocks (one in _emit_daemon_event, one in _write_rebase_log).

# 7. Manual smoke for R0d.
IW_CORE_TEST_CONTEXT=true uv run python -c "
from orch.daemon.migration_rebase import _write_rebase_log, _emit_daemon_event
_write_rebase_log('test-rev', 'test-old', -99999)
_emit_daemon_event('test', {}, 'test')
print('OK: rebase helpers short-circuit cleanly')
"
```

Paste the output of each command into your S17 report. **If any of them fail, do not proceed to R1 — fix R0 first, then re-verify.**

### 1. New unit tests

#### `test_oss_catalog_completeness.py`

```python
"""CR-00022 AC4: every check_id has a catalog entry with non-empty mandatory fields."""
import ast
from pathlib import Path
import yaml

CHECKS_DIR = Path(__file__).parents[2] / "skills" / "iw-oss-publish" / "scripts" / "checks"
CATALOG = Path(__file__).parents[2] / "dashboard" / "services" / "oss_check_catalog.yaml"


def _ast_check_ids() -> set[str]:
    ids = set()
    for path in CHECKS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding":
                for kw in node.keywords:
                    if kw.arg == "id" and isinstance(kw.value, ast.Constant):
                        ids.add(kw.value.value)
    return ids


def test_every_check_id_has_catalog_entry():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    missing = sorted(_ast_check_ids() - catalog.keys())
    assert not missing, f"Catalog missing entries for: {missing}"


def test_no_orphan_catalog_entries():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    orphans = sorted(catalog.keys() - _ast_check_ids())
    assert not orphans, f"Catalog has orphan entries (no matching check): {orphans}"


def test_catalog_entries_have_required_fields():
    catalog = yaml.safe_load(CATALOG.read_text()) or {}
    required = {"what_it_checks", "how_it_tests", "risk_if_failing", "how_to_fix"}
    for check_id, entry in catalog.items():
        for field in required:
            assert entry.get(field, "").strip(), \
                f"{check_id}: field '{field}' is missing or empty"
```

#### `test_oss_check_catalog_loader.py`

- `load_catalog()` returns `dict[str, CheckCopy]`
- Pydantic validation rejects YAML with empty mandatory fields
- Production cache: two calls return the same object identity (cached)
- Debug mode: two calls return different object identities (re-loaded) when `IW_CORE_DEBUG=true`
- `get_copy("nonexistent")` returns `None`

Use `monkeypatch` for `IW_CORE_DEBUG` env var. Reset the `@cache` between tests via `_load_catalog_cached.cache_clear()`.

#### `test_oss_accepted_yaml.py`

- `compute_finding_hash` is deterministic across multiple calls with same inputs
- `compute_finding_hash` differs when summary differs by one char
- `compute_finding_hash` differs when evidence dict differs (order shouldn't matter — keys sorted)
- `append_accepted` creates the file on first call
- `append_accepted` is idempotent — second append of the same `(check_id, finding_hash)` is a no-op (file unchanged byte-for-byte)
- `load_accepted` returns empty `AcceptedFile` when file is missing
- `load_accepted` returns parsed entries when file exists
- `is_accepted` matches by `(check_id, finding_hash)` exactly

Use `tmp_path` fixture for repo_root.

#### `test_oss_fix_recipes_idempotent.py`

```python
"""CR-00022 idempotency contract — every recipe applying twice is a no-op."""
import pytest
from orch.oss.fix_recipes import list_recipes


@pytest.mark.parametrize("recipe", list_recipes(), ids=lambda r: r.check_id)
def test_recipe_apply_is_idempotent(recipe, tmp_path):
    # Apply once
    recipe.apply(tmp_path)
    state1 = _snapshot(tmp_path)
    # Apply twice
    recipe.apply(tmp_path)
    state2 = _snapshot(tmp_path)
    assert state1 == state2, f"{recipe.check_id} not idempotent"


def test_preview_does_not_write(recipe, tmp_path):
    state_before = _snapshot(tmp_path)
    recipe.preview(tmp_path)
    state_after = _snapshot(tmp_path)
    assert state_before == state_after, f"{recipe.check_id}.preview() wrote to disk"


def _snapshot(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
```

#### `test_oss_honor_accepted.py`

- Accepted entry downgrades matching SARIF result from `error` to `warning`
- Reason text is appended to message
- Non-matching results are unchanged
- Empty/missing accepted file leaves SARIF unchanged
- Hash-mismatch entries are NOT applied
- `compute_finding_hash` in `honor_accepted.py` matches `dashboard/services/oss_accepted.py:compute_finding_hash` (golden test on a known fixture)

#### `test_safe_migrate_test_context.py` — locks in R0

```python
"""CR-00022 S17 R0: safe_migrate helpers must short-circuit under test context.

Without this guard, tests that mock safe_apply/safe_rollback at the
migration_pipeline boundary still leak into the live DB via
_write_migration_log / _acquire_migration_lock / _release_migration_lock,
which call get_db_url() directly and bypass the mocks.
"""
from __future__ import annotations
import os
import pytest
from orch.db.safe_migrate import _is_test_context_active


def test_test_context_active_when_only_test_flag_set(monkeypatch):
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    assert _is_test_context_active() is True


def test_operator_opt_in_overrides_test_context(monkeypatch):
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_OPERATOR_APPLY", "true")
    assert _is_test_context_active() is False


def test_daemon_opt_in_overrides_test_context(monkeypatch):
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.setenv("IW_CORE_DAEMON_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    assert _is_test_context_active() is False


def test_write_migration_log_is_noop_under_test_context(monkeypatch):
    """The smoking gun: _write_migration_log must not touch live DB under test."""
    from orch.db import safe_migrate
    # If short-circuit fires, no DB connection is opened — calling with
    # nonsense args completes without error. If short-circuit does NOT
    # fire, we'd hit a connection error or actually write.
    monkeypatch.setenv("IW_CORE_TEST_CONTEXT", "true")
    monkeypatch.delenv("IW_CORE_OPERATOR_APPLY", raising=False)
    monkeypatch.delenv("IW_CORE_DAEMON_CONTEXT", raising=False)
    # Call with deliberately invalid args; short-circuit returns before validation.
    safe_migrate._write_migration_log(
        revision="test-revision-noop",
        direction="upgrade",
        phase="apply",
        batch_id=-99999,
        success=True,
        stdout_tail="",
        stderr_tail="",
        error_message=None,
    )
    # No assertion on live DB — that would itself violate the rule. The
    # absence of an exception is the assertion.
```

### 2. Updated integration tests

#### `test_oss_migration.py`

- After migration:
  - `project_oss_job` no longer has `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`
  - `project_oss_job_kind` enum values are exactly `{scan, install, fix}`
  - `ossscan_mode` enum values are exactly `{scan}`
  - `project_oss_job_status` values are exactly `{queued, running, complete, error, cancelled}`
  - `oss_finding.auto_apply_safe` exists, `BOOLEAN NOT NULL DEFAULT false`
- Pre-migration delete: insert a row with `kind='prepare'` (via raw SQL on the previous schema), run migration, verify the row is gone

#### `test_project_oss_job_migration.py`

- Mirror of above — confirm the previously-added `awaiting_review`/`discarded` are gone and the migration is forward-only (downgrade raises `NotImplementedError`)

#### `test_oss_dashboard_routes.py`

- `POST /oss/prepare` → 404
- `POST /oss/publish` → 404
- `POST /oss/fix/{check_id}` with `apply=False` → 200, returns preview JSON
- `POST /oss/fix/{check_id}` with `apply=True` → 200, returns job_id + stream_url
- `POST /oss/recheck/{check_id}` → 200
- `POST /oss/accept/{check_id}` with `{finding_hash, reason}` → 204, file appended in working tree
- `POST /oss/accept` rejects empty reason (422)
- `POST /oss/apply-all-safe/preview` → 200, returns array
- `POST /oss/apply-all-safe` with `{check_ids: [unsafe_id]}` → 422 (server defends against UI bypass)
- `POST /oss/apply-all-safe` with valid IDs → 200, working tree modified, no branch created (assert `git symbolic-ref HEAD` unchanged)

#### `test_oss_dashboard_sse.py`

- `row-update` events emitted during scan
- Event data shape matches design (check_id, domain, severity, status, summary, auto_apply_safe, auto_fix_available, finding_hash)
- `complete` event still emitted at end
- No `progress` regression

#### `test_oss_cli.py`

- `iw oss prepare` and `iw oss publish` not registered
- `iw oss fix OSS-CH-01 --project iw-ai-core` (preview) → exit 0, JSON output validates
- `iw oss fix OSS-CH-01 --project iw-ai-core --apply` → file written
- `iw oss fix OSS-CH-99 --project iw-ai-core` (unknown ID) → exit 2 with helpful message

#### `test_oss_dashboard_service.py`

- `WORKTREE_KINDS`, `_run_worktree`, `discard_job`, `_prep_branch_name` import errors (symbols removed)
- `_run_fix(project, job_id, session_factory, check_id, apply)` exists and writes to `project.repo_root` directly
- No `tempfile.mkdtemp` or `/tmp/oss-*` paths created during any service call

Use a tmp_path fixture or testcontainer-backed `Project.repo_root` to verify writes go to the expected location.

#### `test_oss_persistence.py`

- Drop assertions for `OssScanMode.make_oss` and `.publish`
- Add: `OssFinding.auto_apply_safe` persisted from Finding into the row

#### `test_oss_scanner.py`

- Drop mode parametrisation (only `scan` remains)
- Add: scanner returns Findings carrying `auto_apply_safe` flag
- `run_scan(project, "make_oss")` raises `ValueError`

#### `test_oss_dashboard_templates_extras.py`

- Remove cards-template assertions
- Add: table renders with the new column order (Group | Test | Type | Status | Details)
- Add: modal fragment renders catalog content for a given check
- Add: filter chips present with default = failing/human-required active

### 3. Coverage map

In the report, include a table:

| AC | Tests covering |
|----|----------------|
| AC1 (no branch ever) | test_oss_dashboard_service.py::test_no_worktree_paths, test_oss_dashboard_routes.py::test_apply_all_safe_no_branch_change |
| AC2 (prepare/publish removed) | test_oss_cli.py::test_prepare_not_registered, test_oss_dashboard_routes.py::test_oss_prepare_404 |
| AC3 (table + modal) | test_oss_dashboard_templates_extras.py::test_table_columns, test_modal_renders |
| AC4 (catalog complete) | test_oss_catalog_completeness.py::test_every_check_id_has_catalog_entry |
| AC5 (apply working-tree-only, idempotent) | test_oss_fix_recipes_idempotent.py |
| AC6 (accept honored by CI) | test_oss_honor_accepted.py + manual workflow run |
| AC7 (migration hard) | test_oss_migration.py |
| AC8 (SSE row updates) | test_oss_dashboard_sse.py |
| AC9 (apply-all-safe deselectable) | covered by S27 browser verification |
| AC10 (apply-all-safe never includes unsafe) | test_oss_dashboard_routes.py::test_apply_all_safe_rejects_unsafe |
| AC11 (worktree cleanup) | manual verification in S19 |
| AC12 (e2e browser) | S27 browser verification |

### 4. TDD requirement

Per `tests/CLAUDE.md`:
- Use testcontainers (Postgres + psycopg v3 URL prefix replacement).
- Run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`.
- Never `importlib.reload(orch.config)` — use `monkeypatch.delenv()`.
- Mark slow tests with `@pytest.mark.integration` so `make test-unit` stays fast.

### 5. Verification

**Step 1 — confirm R0 short-circuit is in place** (this is the most important check):

```bash
# A baseline row count on live DB (operator may run this; you, the agent, do not).
# We rely on the short-circuit + the conftest opt-in to keep this stable.

# Confirm the helpers short-circuit:
IW_CORE_TEST_CONTEXT=true uv run python -c "
from orch.db.safe_migrate import _is_test_context_active, _write_migration_log
assert _is_test_context_active(), 'guard not active under test context'
_write_migration_log('verify', 'upgrade', 'apply', -1, True, '', '', None)
print('OK: _write_migration_log short-circuits cleanly')
"
```

**Step 2 — test suite**:

```bash
make test-unit
make test-integration -- tests/integration/test_oss_*
```

Expect everything green. Any failure is a CR-00022 implementation gap to flag.

**Step 3 — defense-in-depth check**: skim `pending_migration_log` row count BEFORE and AFTER you run the integration suite (operator-only — only run if the operator explicitly asks). If the count grew, R0 is incomplete and you must locate the additional leaking helper before reporting `tests_passed: true`.

## Output / Report

Report contains:
- **R0 verification block first** — paste output of all 5 commands from R0c.
- New + updated test file paths with summary of what each covers
- Coverage map (AC → tests)
- Final test counts (unit pass/fail, integration pass/fail)
- Any tests deferred to S27 (browser-only verifications) and why
- **Note for I-00041**: confirm you applied the worktree-local patch and that I-00041's broader connection-layer guard is still warranted as a follow-up (it covers paths beyond the three helpers patched here).

End with `iw step-done` / `iw step-fail`.
