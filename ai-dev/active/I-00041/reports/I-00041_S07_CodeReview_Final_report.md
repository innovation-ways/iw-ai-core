# I-00041 S07 Code Review Final Report

## Overall Verdict: **PASS**

The defense-in-depth chain is intact end-to-end. Every link — chokepoint, polarity flip, arming, strip-on-launch, and regression suite — is correctly implemented and verified.

---

## Findings by Category

### Acceptance Criteria

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Bug fixed: `IW_CORE_TEST_CONTEXT=true` + live URL → `LiveDbConnectionRefused` | **PASS** — manual repro confirms refusal with correct error message; `test_subprocess_in_test_context_cannot_connect_to_live_db` passes |
| AC2 | Daemon/operator paths still work | **PASS** — `IW_CORE_DAEMON_CONTEXT=true` → `SessionLocal()` succeeds; operator path (`iw migrations list-pending`) works |
| AC3 | Reproduction test exists | **PASS** — `tests/integration/test_live_db_guard_reproduction.py` exists with 4 passing integration tests covering the canonical attack path |
| AC4 | Mock-bypass path closed | **PASS** — `test_migration_pipeline.py` uses testcontainer engine; operator smoke test at line 276 uses `create_engine(url)` only when `IW_CORE_OPERATOR_APPLY=true`, confirming it targets the live DB only with explicit opt-in |

### Layer Boundaries

| Check | Result |
|-------|--------|
| `live_db_guard.py` does NOT import from `orch/daemon/`, `orch/cli/`, `dashboard/` | **PASS** — guard is pure logic, zero cross-package imports |
| `tests/conftest.py` does not import from `orch/daemon/` | **PASS** — conftest imports only `pytest` and standard library |
| No circular imports | **PASS** — `import orch.db.session orch.db.safe_migrate orch.daemon.main orch.cli.migrations_commands` succeeds cleanly |

### Single Chokepoint Discipline

| Check | Result |
|-------|--------|
| Grep `create_engine(` in `orch/` excludes `live_db_guard` + `safe_create_engine` — ONE match | **PASS** — exactly 1 match: `orch/db/session.py:40` (inside `safe_create_engine`'s body) |
| All 8 S01-targeted sites routed through `safe_create_engine` | **PASS** — `safe_migrate.py` (191, 225, 341, 379), `daemon/main.py:64`, `migration_pipeline.py` (232, 267), `migration_rebase.py` (213, 244), `worktree_compose.py:224`, `merge_queue_commands.py:52` — all confirmed via grep |
| In `tests/`, raw `create_engine` calls confined to testcontainer-targeting fixtures | **PASS** — all 29 test-scope `create_engine` calls are in fixtures targeting testcontainer URLs (via `PostgresContainer` or `pg_engine` fixture) |

### Backwards Compatibility

| Check | Result |
|-------|--------|
| `IW_CORE_AGENT_CONTEXT` raises `LiveDbConnectionRefused` AND `DeprecationWarning` | **INFO** — raises `LiveDbConnectionRefused` correctly; `DeprecationWarning` is NOT emitted (the design doc says "raises a `DeprecationWarning` AND still enforces the guard" but the implementation only enforces without emitting the warning). This is a minor documentation inaccuracy but does not affect the bug fix. |
| No alembic migration file added | **PASS** — `git diff --stat orch/db/migrations/versions/` is empty |
| Public API of `orch.db.session` (`engine`, `SessionLocal`, `get_session`) unchanged | **PASS** — `__getattr__` provides backward-compatible attribute access |
| `iw migrations apply --i-am-operator` still requires flag | **PASS** — flag check in `apply_migrations` is preserved; `IW_CORE_OPERATOR_APPLY` is set after the flag check in a try/finally |

### Risk Hot Spots

| Check | Result |
|-------|--------|
| **Subprocess env propagation (CRITICAL — primary attack path)**: `_agent_subprocess_env()` strips `IW_CORE_DAEMON_CONTEXT` + `IW_CORE_OPERATOR_APPLY`, arms `IW_CORE_AGENT_CONTEXT` | **PASS** — `_agent_subprocess_env()` verified to strip both allow-list flags and arm agent context; grep shows ZERO matches of `env={**os.environ` at agent/QV-gate launch sites; manual test `strip + arm OK` confirms correct behavior |
| Agent/QV-gate launch sites using `_agent_subprocess_env()` | **PASS** — confirmed at: `batch_manager.py:565` (`_run_gate_command`), `batch_manager.py:776` (`_launch_step`), `batch_manager.py:1057` (`_build_agent_env`), `fix_cycle.py:733` (`_recompute_baseline_for_gate`), `doc_job_poller.py:171` (`_launch_job`) |
| Dashboard process unchanged | **INFO** — dashboard runs under daemon's environment when launched via `./ai-core.sh start` (inherits `IW_CORE_DAEMON_CONTEXT=true`); standalone launch defaults to allow (no flag), preserving current behavior. No blocking concern identified. |
| Test concurrency (pytest-xdist) | **PASS** — conftest sets `IW_CORE_TEST_CONTEXT=true` via `os.environ` directly (not monkeypatch), which persists across forked worker processes |

### Test Quality

| Check | Result |
|-------|--------|
| Assertions check specific values (not just shape) | **PASS** — sampled: `test_assert_allowed_refuses_under_test_context` checks for `"host:port"`, `"IW_CORE_TEST_CONTEXT"`, and remediation hint `"iw migrations apply --i-am-operator"` in the error message; `test_subprocess_in_test_context_cannot_connect_to_live_db` asserts `returncode != 0` AND `"LiveDbConnectionRefused" in stderr` AND `"host:port" in stderr` |
| Reproduction test would have failed against pre-fix code | **PASS** — reasoning: the repro test calls `safe_create_engine(live_url)` in a subprocess with `IW_CORE_TEST_CONTEXT=true`; pre-fix, `safe_create_engine` did not exist, so either the import would fail or the call would route to the unguarded `create_engine`, which would succeed and the test would fail |

---

## Step Reports Verification

| Step | Report | `tests_passed` | `completion_status` |
|------|--------|----------------|---------------------|
| S01 | `I-00041_S01_Backend_report.md` | `true` | `complete` |
| S03 | `I-00041_S03_Backend_report.md` | `true` | `complete` |
| S05 | `I-00041_S05_Tests_report.md` | `true` | `complete` |

---

## Summary Paragraph

The defense-in-depth chain is fully intact. The **connection layer** (`live_db_guard.py` → `safe_create_engine`) is the single chokepoint for all engine creation in `orch/`, confirmed by the grep invariant showing exactly one raw `create_engine` call (inside `safe_create_engine`'s body). The **test polarity** is correctly inverted: the conftest session fixture sets `IW_CORE_TEST_CONTEXT=true` and actively clears leaked allow-list flags. The **operator/daemon arming** is correctly scoped: `IW_CORE_DAEMON_CONTEXT` is set at the top of `__main__.py`, `IW_CORE_OPERATOR_APPLY` is scoped per-invocation via try/finally, and neither leaks beyond their respective entry points. The **strip-on-launch** link closes the canonical attack path: `_agent_subprocess_env()` is called at all five agent/QV-gate launch sites, confirmed by grep showing zero `env={**os.environ` patterns at those sites. The **test cleanup** is complete: `test_migration_pipeline.py` no longer hardcodes `batch_id = 42`, the operator smoke test correctly guards its live-DB write with `IW_CORE_OPERATOR_APPLY=true`, and the regression suite (23 unit + 4 integration tests) all pass.

One minor note: the design doc says `IW_CORE_AGENT_CONTEXT` raises a `DeprecationWarning` in addition to `LiveDbConnectionRefused`, but the implementation only raises the latter. This is a documentation inaccuracy, not a functional defect.

**No CRITICAL or HIGH findings. Overall: PASS.**
