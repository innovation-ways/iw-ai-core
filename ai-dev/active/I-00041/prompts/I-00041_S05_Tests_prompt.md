# I-00041_S05_Tests_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step**: S05
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live
orchestration DB (port 5433) from an agent context. All migrations in this
test suite run against testcontainers only.

## CRITICAL: Semantic Correctness Over Shape Checking (I-00003 Lesson)

I-00002's tests checked API response SHAPE (key exists, is a list, is
non-empty) and passed — but the bug was NOT fixed. **Tests must verify
SPECIFIC VALUES**:

- BAD: `assert "permissions" in data` (shape only)
- BAD: `assert len(refused_msg) > 0` (non-empty only)
- GOOD: `assert "LiveDbConnectionRefused" in refused_msg` (specific class name)
- GOOD: `assert "5433" in refused_msg` (specific port the operator should see)
- GOOD: `assert "iw migrations apply --i-am-operator" in refused_msg` (specific
  remediation hint)

Every assertion in this prompt's tests MUST verify a specific expected value,
not just truthy / non-empty / has-key.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S01_Backend_report.md`
- `ai-dev/active/I-00041/reports/I-00041_S03_Backend_report.md`
- `orch/db/live_db_guard.py` (added by S01)
- `orch/db/session.py` (modified by S01)
- `orch/db/safe_migrate.py` (modified by S01)
- `tests/conftest.py` (modified by S03)
- `orch/daemon/batch_manager.py` (modified by S03 — `_agent_subprocess_env`)
- `orch/daemon/fix_cycle.py` (modified by S03)
- `orch/daemon/doc_job_poller.py` (modified by S03)
- `tests/integration/test_migration_pipeline.py` (the offending file)
- `tests/CLAUDE.md`

## Output Files

- New: `tests/unit/test_live_db_guard.py`
- New: `tests/unit/test_agent_subprocess_env.py` (covers S03 R5 strip helper)
- New: `tests/integration/test_live_db_guard_reproduction.py`
- Modified: `tests/integration/test_migration_pipeline.py` (unique batch_id, expanded mocks)
- Report: `ai-dev/active/I-00041/reports/I-00041_S05_Tests_report.md`

## Context

You are writing the **reproduction test** that demonstrates the bug, the
**regression suite** that locks in the fix, and the **cleanup** for the
specific test file that was responsible for the live-DB writes.

Read the design doc first, especially the Test to Reproduce, Acceptance
Criteria, and TDD Approach sections. Read `tests/CLAUDE.md` for the
project's testcontainer fixture conventions.

## Requirements

### R1 — Unit tests: `tests/unit/test_live_db_guard.py`

Use `monkeypatch` to control env vars and `make_url` to construct test
URLs. Do NOT use a real DB connection in unit tests.

Test cases (each with specific-value assertions):

1. `test_is_live_db_url_matches_by_host_port_when_no_fingerprint` — set
   `IW_CORE_DB_HOST=localhost`, `IW_CORE_DB_PORT=5433`; assert
   `is_live_db_url("postgresql://x:y@localhost:5433/iw_orch") is True`.
2. `test_is_live_db_url_rejects_different_port` — same env; assert
   `is_live_db_url("postgresql://x:y@localhost:55432/iw_orch") is False`.
3. `test_is_live_db_url_rejects_different_host` — same env; assert
   `is_live_db_url("postgresql://x:y@otherhost:5433/iw_orch") is False`.
4. `test_is_live_db_url_fails_open_on_parse_error` — assert
   `is_live_db_url("not-a-url") is False` (does NOT raise).
5. `test_is_live_db_url_fails_open_when_env_unset` — clear all
   IW_CORE_DB_* vars; assert any URL returns False (cannot prove it's
   live without env to compare against).
6. `test_assert_allowed_refuses_under_test_context` — set
   `IW_CORE_TEST_CONTEXT=true`, env points at 5433; assert
   `pytest.raises(LiveDbConnectionRefused)` matches when calling
   `assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")`.
   Verify the exception message contains all three: `"5433"`,
   `"IW_CORE_TEST_CONTEXT"`, and `"iw migrations apply --i-am-operator"`.
7. `test_assert_allowed_refuses_under_agent_context_deprecated` — same
   as R1.6 but with `IW_CORE_AGENT_CONTEXT=true` (deprecated alias).
   Verify it still raises and the message references `IW_CORE_AGENT_CONTEXT`.
8. `test_assert_allowed_passes_under_operator_context` — set
   `IW_CORE_OPERATOR_APPLY=true` (no test/agent flag); assert
   `assert_engine_url_allowed(...)` returns None for the same live URL.
9. `test_assert_allowed_passes_under_daemon_context` — set
   `IW_CORE_DAEMON_CONTEXT=true`; assert allowed.
10. `test_assert_allowed_passes_for_non_live_url_under_test_context` — set
    `IW_CORE_TEST_CONTEXT=true` AND env pointing at 5433; assert that
    `assert_engine_url_allowed("postgresql://x:y@localhost:55432/test")`
    returns None (testcontainer URLs are always allowed regardless of
    test-context flag).
11. `test_assert_allowed_default_allow_when_no_flag_set` — clear ALL
    IW_CORE_* context flags; assert
    `assert_engine_url_allowed("postgresql://x:y@localhost:5433/iw_orch")`
    returns None (preserves backwards compatibility for ad-hoc scripts).
12. `test_operator_flag_wins_over_test_context` — set BOTH
    `IW_CORE_OPERATOR_APPLY=true` AND `IW_CORE_TEST_CONTEXT=true`;
    assert allowed (operator opt-in wins; this matches the design's
    note about an operator running daemon code locally).
13. `test_safe_create_engine_calls_guard_before_creating_engine` — patch
    `assert_engine_url_allowed` to raise; call
    `orch.db.session.safe_create_engine("postgresql://...")`; assert
    the patch was called and `create_engine` was NOT called (mock the
    sqlalchemy `create_engine` to detect).

For each refusal-message assertion, write the assertion as:
`assert "5433" in str(exc_info.value), f"missing port: {exc_info.value!r}"`
so failures print the actual message. Don't use bare `assert "x" in str(e)`.

### R1.5 — Executor strip unit tests: `tests/unit/test_agent_subprocess_env.py`

The `_agent_subprocess_env(...)` helper in `orch/daemon/batch_manager.py`
is the single chokepoint that prevents the daemon's allow-list flags from
leaking into agent and QV-gate subprocesses. A regression here re-opens
the bug.

Test cases (each with specific-value assertions, all unit-scope, no DB):

1. `test_strips_daemon_context_when_set` — `monkeypatch.setenv(
   "IW_CORE_DAEMON_CONTEXT", "true")`; assert
   `"IW_CORE_DAEMON_CONTEXT" not in _agent_subprocess_env()`.
2. `test_strips_operator_apply_when_set` — same pattern with
   `IW_CORE_OPERATOR_APPLY`.
3. `test_strips_both_when_both_set` — set both; assert both absent.
4. `test_arms_agent_context` — clear `IW_CORE_AGENT_CONTEXT`; assert
   `_agent_subprocess_env()["IW_CORE_AGENT_CONTEXT"] == "true"`.
5. `test_overrides_inherited_agent_context_with_true` — set
   `IW_CORE_AGENT_CONTEXT=false`; assert returned env has it set to
   `"true"` (the helper enforces, not just defaults).
6. `test_extra_dict_is_merged_after_strip_and_arm` — pass
   `extra={"IW_CORE_PER_WORKTREE_DB": "true", "FOO": "bar"}`; assert both
   keys present with the expected values, and that strip + arm were not
   undone.
7. `test_extra_can_override_agent_context_for_test_paths` — pass
   `extra={"IW_CORE_AGENT_CONTEXT": "false"}`; document via the assertion
   whether the helper's contract allows extras to override (your call —
   match whatever S03 implemented; this test locks the contract in either
   direction).
8. `test_does_not_mutate_real_environment` — call the helper twice; assert
   `os.environ` is unchanged between calls and that two returned dicts are
   independent (mutating one must not affect the other).
9. `test_preserves_unrelated_env_vars` — set `PATH`, `HOME`,
   `IW_CORE_DB_HOST`; assert all three are in the returned env (the helper
   strips ONLY allow-list flags, nothing else).
10. `test_build_agent_env_delegates_to_helper` — call `_build_agent_env(...)`
    with `IW_CORE_DAEMON_CONTEXT=true` set; assert the returned dict has
    no `IW_CORE_DAEMON_CONTEXT` key (proves the public delegator was
    correctly rewired by S03).

Use `monkeypatch.setenv` / `monkeypatch.delenv` for env control. Do not
touch `os.environ` directly in unit tests.

### R2 — Reproduction test: `tests/integration/test_live_db_guard_reproduction.py`

The canonical reproduction. Spawn a fresh subprocess with the
post-fix conftest's defaults (`IW_CORE_TEST_CONTEXT=true`) and have it
attempt to connect to the live orch DB. Assert the subprocess fails with
a non-zero exit code and the expected error.

```python
@pytest.mark.integration
def test_subprocess_in_test_context_cannot_connect_to_live_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces I-00041: a test process must NOT be able to connect to 5433."""
    # The live URL — use the operator's actual env (the conftest deletes
    # opt-in flags so this is the URL tests are FORBIDDEN to reach).
    live_host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    live_port = os.environ.get("IW_CORE_DB_PORT", "5433")
    live_url = f"postgresql://iw_orch:iw_orch@{live_host}:{live_port}/iw_orch"

    code = textwrap.dedent(f"""
        import os
        os.environ['IW_CORE_TEST_CONTEXT'] = 'true'
        os.environ.pop('IW_CORE_OPERATOR_APPLY', None)
        os.environ.pop('IW_CORE_DAEMON_CONTEXT', None)
        os.environ['IW_CORE_DB_HOST'] = {live_host!r}
        os.environ['IW_CORE_DB_PORT'] = {live_port!r}
        from orch.db.session import safe_create_engine
        e = safe_create_engine({live_url!r})
        c = e.connect()
        c.close()
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, (
        f"GUARD FAILED — subprocess connected to live DB.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "LiveDbConnectionRefused" in result.stderr, (
        f"Wrong refusal type: stderr={result.stderr!r}"
    )
    assert live_port in result.stderr, (
        f"Missing port in refusal: stderr={result.stderr!r}"
    )
```

Plus a positive-control sibling test:

```python
@pytest.mark.integration
def test_subprocess_with_operator_flag_can_connect_to_testcontainer(
    pg_container: PostgresContainer,
) -> None:
    """Confirms the guard does not over-block: an operator-context process
    against a testcontainer URL still works."""
    # ... uses pg_container fixture from tests/integration/conftest.py
```

Plus the **canonical "daemon-launches-agent" reproduction** — this is the
attack path the bug actually took (a daemon process spawned a QV gate
subprocess that ran pytest, and that subprocess wrote to the live DB):

```python
@pytest.mark.integration
def test_daemon_armed_subprocess_via_agent_env_helper_cannot_connect_to_live_db() -> None:
    """Reproduces the daemon → agent leak path I-00041 closes.

    Simulates: parent process has IW_CORE_DAEMON_CONTEXT=true (as the
    daemon would). It spawns a child using _agent_subprocess_env(), which
    must strip DAEMON_CONTEXT and arm AGENT_CONTEXT. The child then
    attempts a live-DB connect and MUST be refused.
    """
    live_host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    live_port = os.environ.get("IW_CORE_DB_PORT", "5433")
    live_url = f"postgresql://iw_orch:iw_orch@{live_host}:{live_port}/iw_orch"

    parent_env = {
        **os.environ,
        "IW_CORE_DAEMON_CONTEXT": "true",  # parent is "the daemon".
    }
    parent_env.pop("IW_CORE_AGENT_CONTEXT", None)
    parent_env.pop("IW_CORE_TEST_CONTEXT", None)

    code = textwrap.dedent(f"""
        import sys
        from orch.daemon.batch_manager import _agent_subprocess_env
        child_env = _agent_subprocess_env()
        # Apply the helper's env to this child's view of the world.
        import os
        for k in ('IW_CORE_DAEMON_CONTEXT', 'IW_CORE_OPERATOR_APPLY'):
            if k in os.environ and k not in child_env:
                os.environ.pop(k, None)
        for k, v in child_env.items():
            os.environ[k] = v
        from orch.db.session import safe_create_engine
        e = safe_create_engine({live_url!r})
        e.connect()
    """)
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=parent_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, (
        f"GUARD FAILED — daemon-armed agent subprocess connected to live DB.\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "LiveDbConnectionRefused" in result.stderr, (
        f"Wrong refusal type: stderr={result.stderr!r}"
    )
    assert live_port in result.stderr, (
        f"Missing port in refusal: stderr={result.stderr!r}"
    )
```

### R3 — Cleanup: `tests/integration/test_migration_pipeline.py`

The 5 hardcoded `batch_id = 42` lines (29, 70, 95, 150, 190) are the
proximate cause of the 152 stale rows in `pending_migration_log`.

Replace each with a fixture-derived unique value:

```python
@pytest.fixture
def unique_batch_id(request: pytest.FixtureRequest) -> int:
    """Per-test unique negative batch_id.

    Negatives never collide with real batch IDs (which are positive
    auto-incrementing). The hash of the test name + xdist worker ID
    keeps it stable across reruns of the same test on the same worker
    but unique across tests.
    """
    import hashlib
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    name = f"{worker}:{request.node.nodeid}"
    h = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
    return -(h % 1_000_000) - 1  # range: [-1_000_001, -1]
```

Update each test to take the `unique_batch_id` fixture and use it:

```python
def test_pipeline_happy_path(unique_batch_id: int) -> None:
    batch_id = unique_batch_id  # was: batch_id = 42
    ...
```

Then audit the test file for **any code path that reaches
`_write_migration_log`** while NOT mocked. Specifically:

- The `with patch("orch.daemon.migration_pipeline.safe_apply") as mock_apply`
  block patches the migration_pipeline import. But `_write_migration_log`
  inside the real `safe_migrate.apply` (which is what's behind the patch
  before it's replaced) calls `get_db_url()` directly. With the patch
  active, the real `safe_apply` is NOT called, so `_write_migration_log`
  is NOT invoked. Confirm this is true by reading each test top-down.
- If any test path DOES reach the real `_write_migration_log`, add an
  explicit mock at `orch.db.safe_migrate._write_migration_log` for that
  test scope. The connection-layer guard (S01) is the primary defense
  but defense-in-depth is cheap.

Document in the test docstrings: "I-00041: this test must not write
to live DB. The connection-layer guard in
`orch/db/live_db_guard.py` enforces this; the mocks here are
defense-in-depth."

### R4 — Mock-coverage smoke test

Calling pytest test functions directly (e.g. `test_pipeline_happy_path(...)`)
is fragile because pytest fixture resolution does not run; the function's
parameter list and any `monkeypatch`/fixture deps would silently break.
Instead, refactor the body of `test_pipeline_happy_path` into a plain
helper, and have both the pytest test and the smoke test call the helper.

Step 4a — extract a helper inside `tests/integration/test_migration_pipeline.py`:

```python
def _run_pipeline_happy_path(batch_id: int) -> None:
    """Plain function with the body of test_pipeline_happy_path.

    Extracted so the I-00041 mock-coverage smoke test can invoke it
    without going through pytest collection (and thus without needing
    fixture resolution beyond the explicit batch_id argument).
    """
    # ... (the exact body that was inside test_pipeline_happy_path)
```

Then update `test_pipeline_happy_path` to be a one-liner:

```python
def test_pipeline_happy_path(unique_batch_id: int) -> None:
    _run_pipeline_happy_path(unique_batch_id)
```

Step 4b — add the operator-only smoke test that uses the helper:

```python
@pytest.mark.integration
def test_no_pending_migration_log_writes_to_live_db_under_test_context(
    unique_batch_id: int,
) -> None:
    """I-00041 regression: running the migration pipeline tests under
    test-context must NOT write any row to live pending_migration_log.

    Snapshot the live DB row count before, run a representative pipeline
    test in-process (under mocks), snapshot after, assert equal. This is
    the truth oracle that the connection-layer guard + mock coverage
    together close the bypass.
    """
    from sqlalchemy import create_engine, text  # noqa: PLC0415

    live_host = os.environ.get("IW_CORE_DB_HOST", "localhost")
    live_port = os.environ.get("IW_CORE_DB_PORT", "5433")

    # We can ONLY snapshot live if the operator has set the read-only
    # opt-in. Skip cleanly otherwise.
    if os.environ.get("IW_CORE_OPERATOR_APPLY") != "true":
        pytest.skip(
            "Operator-only smoke test — set IW_CORE_OPERATOR_APPLY=true to run"
        )

    url = f"postgresql://iw_orch:iw_orch@{live_host}:{live_port}/iw_orch"
    engine = create_engine(url)
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT count(*) FROM pending_migration_log")
        ).scalar()

    _run_pipeline_happy_path(unique_batch_id)

    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT count(*) FROM pending_migration_log")
        ).scalar()

    assert after == before, (
        f"I-00041 regression: pipeline test wrote {after - before} row(s) "
        f"to live pending_migration_log. The mocks are not covering "
        f"_write_migration_log."
    )
```

This test is **operator-only** (skipped in normal CI) — it deliberately
opts into the live DB read to verify writes haven't happened. It is the
"truth oracle" for the regression. It MUST be marked `@pytest.mark.integration`
and skip cleanly when no opt-in is set.

### R5 — Constraints

1. NO mocks of the database in integration tests beyond what's needed for
   isolation. Real testcontainer where possible.
2. NO connections to live DB on port 5433 except in:
   (a) the operator-only smoke test in R4 (skipped otherwise),
   (b) the subprocess in R2 (which is expected to fail).
3. Every assertion verifies a SPECIFIC VALUE, not just truthy/non-empty.
4. Tests are deterministic. No `time.sleep` polling without timeout +
   assertion.
5. Test names start with `test_` and clearly describe the scenario.
6. Use `pytest.mark.integration` on integration tests; `pytest.mark.unit`
   on unit tests if the project uses it (check `pyproject.toml`).
7. The new tests MUST work both under pytest-xdist (parallel) and
   single-worker.

## Project Conventions

Read `tests/CLAUDE.md` for:
- Testcontainer URL replacement (`postgresql+psycopg2://` → `postgresql+psycopg://`)
- FTS trigger installation after `Base.metadata.create_all()`
- The autouse fixtures and what they do (note: in this branch S03 changed them)

## Test Verification (NON-NEGOTIABLE)

After writing tests:

1. `make lint` — passes.
2. `make typecheck` — passes.
3. `uv run pytest tests/unit/test_live_db_guard.py -v` — all 13 tests pass.
4. `uv run pytest tests/unit/test_agent_subprocess_env.py -v` — all 10
   strip-helper tests pass.
5. `uv run pytest tests/integration/test_live_db_guard_reproduction.py
   -v -k "not operator"` — all tests pass (skipping the operator-only one),
   including the canonical daemon→agent reproduction.
6. `uv run pytest tests/integration/test_migration_pipeline.py -v` —
   all existing tests still pass with the unique-batch-id refactor and
   the helper extraction.
7. `grep -nE "batch_id\s*=\s*42" tests/integration/test_migration_pipeline.py`
   — must return zero matches (no hardcoded 42 left).

Report: `tests_passed: true` only if all seven pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "I-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_live_db_guard.py",
    "tests/unit/test_agent_subprocess_env.py",
    "tests/integration/test_live_db_guard_reproduction.py",
    "tests/integration/test_migration_pipeline.py"
  ],
  "tests_passed": true,
  "test_summary": "13 guard unit tests, 10 strip-helper unit tests, 2 reproduction integration tests (test-context + daemon-armed-agent), all migration_pipeline tests pass after helper extraction",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S05
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S05 --report ai-dev/active/I-00041/reports/I-00041_S05_Tests_report.md
```
