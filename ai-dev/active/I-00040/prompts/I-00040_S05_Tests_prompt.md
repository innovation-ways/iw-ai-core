# I-00040 S05 — Tests: reproduction + regression coverage for the alembic guard

You are executing step **S05** for work item **I-00040** ("Alembic-version guard at daemon/dashboard/launch boundaries").

## ⛔ Docker / Migrations off-limits

Standard rules. Tests use testcontainers via the project's pytest
fixtures. NEVER connect tests to the live DB on port 5433. NEVER call
`importlib.reload(orch.config)`. See `tests/CLAUDE.md` for the full
list of testing rules.

## Context

S01 added the helper `orch/db/alembic_guard.py` and wired it into the
daemon, dashboard, and `_launch_item`. S03 added the dashboard banner
and write-action disable. Your job is to write tests that prove the
guard works AND that any future regression would fail loudly.

Read:
- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md`
- `ai-dev/active/I-00040/reports/I-00040_S03_Frontend_report.md`

## Project Context

Read `tests/CLAUDE.md` for fixture patterns. Most relevant:

- `pg_container` / `testdb_url` fixtures spin up a PostgreSQL
  testcontainer.
- `Base.metadata.create_all()` does NOT include FTS triggers — use the
  `apply_fts_sql` fixture if you need them. (Probably not needed for
  this issue.)
- `monkeypatch.delenv()` instead of reload.
- For dashboard tests, use `dashboard/CLAUDE.md`'s
  `TestClient(create_app())` pattern.

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is
non-empty) and passed. But the bug was NOT fixed. Tests must verify
SPECIFIC VALUES:

- BAD: `assert "current_rev" in body` (shape only)
- GOOD: `assert "550aecbbd42b" in body or "<head_rev>" in body` (semantic)
- GOOD: `assert "make db-migrate" in body` (semantic — exact remediation copy)
- BAD: `assert status.pending` (truthy only)
- GOOD: `assert status.pending == ["c062b6bf5eb3"]` or
  `assert "c062b6bf5eb3" in status.pending` (semantic)

Every assertion in this step MUST verify a specific expected value,
not merely that something is present or non-empty.

## Requirements

### R1 — Unit tests: `tests/unit/test_alembic_guard.py`

Cover the helper module's public API in isolation. Mock the DB layer
(`safe_migrate.list_pending_revisions`, `current_revision`) — no real
DB connection in unit tests.

Test cases:

1. `test_check_db_at_head_returns_ok_when_aligned` — given current_rev
   == head_rev and zero pending, `GuardStatus.ok is True`.
2. `test_check_db_at_head_returns_not_ok_when_behind` — given a list
   of pending revisions, `GuardStatus.ok is False` and
   `GuardStatus.pending == ["rev_c", "rev_b"]` (head-first order).
3. `test_check_db_at_head_handles_multiple_heads` — given
   `MultipleHeadsError` from `list_pending_revisions`, status reports
   `multiple_heads` and `ok is False`.
4. `test_check_db_at_head_handles_empty_alembic_version` — given
   `current_rev is None`, status's `current_rev` is None and pending
   contains every revision in the script directory.
5. `test_assert_db_at_head_raises_DBBehindHeadError_with_revs_in_msg` —
   the raised exception's message contains `current_rev` value (or the
   string `EMPTY` when None), `head_rev` value, and the literal string
   `make db-migrate`.
6. `test_assert_db_at_head_silent_on_match` — no exception raised.
7. `test_remediation_message_format` — single line, contains
   `current_rev=…`, `head_rev=…`, and `'make db-migrate'`.
8. `test_skip_env_var_honoured_for_operator` — given
   `IW_CORE_SKIP_ALEMBIC_GUARD=true`, `assert_db_at_head` returns
   silently AND a `WARNING` log line is emitted.
9. `test_skip_env_var_refused_in_agent_context` — given
   `IW_CORE_AGENT_CONTEXT=true` and `IW_CORE_SKIP_ALEMBIC_GUARD=true`,
   `assert_db_at_head` STILL raises (skip is operator-only).

### R2 — Integration test: `tests/integration/test_alembic_guard_integration.py`

Use a PostgreSQL testcontainer. This test is the canonical
"reproduction" required by the design.

Test cases:

1. `test_guard_passes_at_head` — apply `alembic upgrade head` to the
   testcontainer; `assert_db_at_head(testdb_url)` does not raise.
2. `test_guard_fails_when_behind_one_revision` — apply
   `alembic upgrade head`; capture `head_rev`; apply
   `alembic downgrade -1`; capture `current_rev`. Assert:
   - `pytest.raises(DBBehindHeadError)` matches.
   - `head_rev` and `current_rev` both appear in the exception
     message.
   - `"make db-migrate"` appears in the exception message.

### R3 — Daemon integration: `tests/integration/test_daemon_alembic_guard.py`

Test that the daemon module exits non-zero on mismatch. Either:
- Call the daemon's `main()` (or whatever startup function exists) in
  a subprocess against a testcontainer that's been downgraded by one
  revision, and assert exit code != 0 and stderr contains the
  expected `CRITICAL: orch DB schema mismatch — ` prefix; OR
- Call the startup function directly in-process, monkeypatching
  `sys.exit` to capture the exit code.

Either is acceptable; pick the one most consistent with existing
daemon tests in `tests/integration/`.

### R4 — Dashboard integration: `tests/dashboard/test_alembic_guard_banner.py`

Use `TestClient(create_app())`. Inside the test:

1. Spin up a testcontainer at head; assert `client.get("/")` body
   does NOT contain the banner markup (specifically, does NOT contain
   `Orch DB schema is behind head`).
2. Downgrade the testcontainer by one revision; force the middleware's
   throttle to expire (`monkeypatch.setattr` the cached timestamp).
   Assert `client.get("/")` body DOES contain:
   - the literal string `Orch DB schema is behind head`
   - the `head_rev` revision identifier
   - the `current_rev` revision identifier (or `EMPTY` if it's None)
   - the literal string `make db-migrate`
   - `role="alert"`
3. Assert that a state-mutating endpoint (e.g.
   `POST /batches/<id>/approve` — pick whichever exists) returns HTTP
   503 with the remediation message in the body.

### R5 — `_launch_item` regression: `tests/integration/test_launch_item_alembic_guard.py`

1. Spin up a testcontainer at head; create a `BatchItem` with
   status=`pending` for some queued work item; downgrade the DB by one
   revision; call `BatchManager._launch_item(batch_item)` (or the
   public path that funnels into it).
2. Assert:
   - `batch_item.status == BatchItemStatus.setup_failed` after the
     call.
   - `batch_item.notes` contains both revisions and `make db-migrate`.
   - No directory was created at `.worktrees/<batch_item_id>/` (use
     `tmp_path` to confirm).
   - A `DaemonEvent` row was emitted with
     `event_metadata["phase"] == "alembic_guard"` and
     `event_metadata["reason"] == "db_behind_head"`.

## Constraints

1. NO mocks of the database in integration tests — real testcontainer.
2. NO connections to the live DB on port 5433.
3. Every assertion verifies a SPECIFIC VALUE (revision string, exact
   copy, exact status enum), not just truthy / non-empty.
4. Tests MUST be deterministic: no `time.sleep`-based polling without
   a clear timeout and assertion.
5. Test names start with `test_` and clearly describe the scenario.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md`
- `ai-dev/active/I-00040/reports/I-00040_S03_Frontend_report.md`
- `orch/db/alembic_guard.py`
- `tests/conftest.py` and `tests/CLAUDE.md`

## Output Files

- `tests/unit/test_alembic_guard.py`
- `tests/integration/test_alembic_guard_integration.py`
- `tests/integration/test_daemon_alembic_guard.py`
- `tests/integration/test_launch_item_alembic_guard.py`
- `tests/dashboard/test_alembic_guard_banner.py`
- `ai-dev/active/I-00040/reports/I-00040_S05_Tests_report.md`

## Lifecycle Commands

```bash
uv run iw step-start I-00040 --step S05
# ... write tests, run them, ensure they pass against current code ...
uv run pytest tests/unit/test_alembic_guard.py -v
uv run pytest tests/integration/test_alembic_guard_integration.py -v
uv run pytest tests/integration/test_daemon_alembic_guard.py -v
uv run pytest tests/integration/test_launch_item_alembic_guard.py -v
uv run pytest tests/dashboard/test_alembic_guard_banner.py -v
# ... write report ...
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S05 --report ai-dev/active/I-00040/reports/I-00040_S05_Tests_report.md
```
