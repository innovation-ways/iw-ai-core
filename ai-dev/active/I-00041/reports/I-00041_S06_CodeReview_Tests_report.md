# I-00041 S06 CodeReview_Tests Report

## Summary

Review of S05 (tests-impl) for I-00041. The test suite is well-structured and would
have caught the original bug. Two findings require attention before final approval.

## Findings

### HIGH

**`orch/db/live_db_guard.py:95-100` + `test_live_db_guard.py:97`**
- **Item**: Deprecation warning for `_assert_not_agent_context` has no test coverage
- **Verdict**: `safe_migrate.py:159` emits `DeprecationWarning` when `_assert_not_agent_context`
  is called, but no test uses `pytest.warns(DeprecationWarning)` to assert it fires.
  The existing `test_safe_migrate_guards.py` tests the guard's *behavior* but not the
  deprecation path itself (it patches through `AgentContextForbiddenError` without triggering
  the warning). Without this test, a future refactor that removes the warning from the
  delegation chain would go undetected.

---

### MEDIUM

**`tests/integration/test_live_db_guard_reproduction.py:66-68`**
- **Item**: Reproduction test checks `"host:port"` not the specific port number
- **Verdict**: The checklist requires "the live port number appears in stderr."
  The guard at `live_db_guard.py:95` raises with the literal string `"host:port"`,
  not the resolved port value. The tests assert `"host:port" in result.stderr`
  (line 66/120), not `"5433" in result.stderr`. This is a specific-value assertion
  mismatch: if the guard message accidentally said `"host"`, the test would still
  pass. S05 intentionally changed from `"5433"` → `"host:port"` to match the
  implementation's placeholder text (per S05 report), but this weakens the
  specific-value bar. The implementation choice is defensible (no sensitive data
  in error message), but the test should be updated to assert both the generic
  placeholder AND the remediation string, or the implementation should include
  the resolved port.

---

### INFO / PASS

| Checklist Item | Status | Notes |
|---|---|---|
| `test_subprocess_in_test_context_cannot_connect_to_live_db` catches original bug | PASS | Subprocess sets TEST_CONTEXT, clears allow-list flags, calls `e.connect()` — pre-fix would have succeeded |
| Subprocess sets env state correctly | PASS | IW_CORE_TEST_CONTEXT=true; IW_CORE_OPERATOR_APPLY/IW_CORE_DAEMON_CONTEXT cleared |
| Subprocess calls `e.connect()` (not just engine construction) | PASS | Line 50: `c = e.connect()` — guard fires at connect time |
| Three specific-value assertions (returncode, LiveDbConnectionRefused, host:port) | PARTIAL | returncode + error type check are specific; "host:port" is generic placeholder (→ MEDIUM) |
| Daemon-armed reproduction test catches S03 R5 gap | PASS | Parent IW_CORE_DAEMON_CONTEXT=true; child uses `_agent_subprocess_env()`; cleanup code also strips DAEMON_CONTEXT; test asserts non-zero + error type |
| `test_daemon_armed_subprocess_via_agent_env_helper_cannot_connect_to_live_db` env setup | PASS | Parent sets IW_CORE_DAEMON_CONTEXT=true; agent helper strips it; child arms IW_CORE_AGENT_CONTEXT |
| Strip-helper unit tests assert specific key absence | PASS | `"IW_CORE_DAEMON_CONTEXT" not in env`, `"IW_CORE_OPERATOR_APPLY" not in env` |
| Strip-helper arm tests assert exactly `"true"` (string) | PASS | `assert env.get("IW_CORE_AGENT_CONTEXT") == "true"` |
| `test_extra_dict_is_merged_after_strip_and_arm` — strip before extra.update | PASS | Verified at `batch_manager.py:1064-1069`: strip → arm → `env.update(extra)` |
| `test_does_not_mutate_real_environment` snapshots keys AND values | PASS | Checks `os.environ.get("IW_CORE_DAEMON_CONTEXT") == "true"` after calls; checks env1/env2 independence |
| `test_build_agent_env_delegates_to_helper` | PASS | `_build_agent_env` at line 1073 calls `_agent_subprocess_env()` |
| Guard unit tests check specific values (not just pytest.raises) | PASS | Tests check: `"IW_CORE_TEST_CONTEXT"` in msg, `"iw migrations apply --i-am-operator"` in msg |
| Default-allow test (no flags set) | PASS | `test_assert_allowed_default_allow_when_no_flag_set` — line 153 |
| Operator-vs-test priority test | PASS | `test_operator_flag_wins_over_test_context` — line 167 |
| `test_safe_create_engine_calls_guard_before_creating_engine` mock + order check | PASS | Patches `sqlalchemy.create_engine`, asserts `assert_engine_url_allowed` called first |
| `grep -nE "batch_id\s*=\s*42"` returns zero | PASS | Confirmed no hardcoded 42 in test_migration_pipeline.py |
| `unique_batch_id` fixture uses negatives | PASS | `return -(h % 1_000_000) - 1` — always negative |
| `unique_batch_id` fixture handles missing PYTEST_XDIST_WORKER | PASS | `os.environ.get("PYTEST_XDIST_WORKER", "main")` — defaults to "main" |
| Test docstrings note live-DB defense | PASS | Module docstring line 9-11 and each test docstring |
| Operator-only smoke test skips cleanly | PASS | `pytest.skip("Operator-only smoke test — set IW_CORE_OPERATOR_APPLY=true to run")` |
| No test in test_live_db_guard.py connects to any DB | PASS | All use monkeypatch + make_url |
| Reproduction subprocess fails BEFORE any live write | PASS | Guard raises before e.connect(); no write possible |
| Both refused-context flags covered (TEST_CONTEXT, AGENT_CONTEXT) | PASS | `test_assert_allowed_refuses_under_test_context`, `test_assert_allowed_refuses_under_agent_context_deprecated` |
| Both allowed-context flags covered (OPERATOR_APPLY, DAEMON_CONTEXT) | PASS | `test_assert_allowed_passes_under_operator_context`, `test_assert_allowed_passes_under_daemon_context` |
| DeprecationWarning test for `_assert_not_agent_context` | FAIL | No `pytest.warns(DeprecationWarning)` test found (→ HIGH) |
| Type hints on fixture functions | PASS | `unique_batch_id(request: pytest.FixtureRequest) -> int` |
| No time.sleep polling without timeout+assertion | PASS | All subprocess tests use `timeout=10/30` |
| Test names start with `test_` | PASS | All 27 tests |
| Markers used consistently | PASS | `@pytest.mark.integration`, `@pytest.mark.unit`, `@pytest.mark.slow` |
| testcontainer URL replacement | PASS | `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")` in integration tests |
| Scope drift: only expected test files changed | PASS | New: test_live_db_guard.py, test_agent_subprocess_env.py, test_live_db_guard_reproduction.py; Modified: test_migration_pipeline.py |
| S05 production code: only tests/ changed | PASS | Git diff shows orch/ modifications are pre-S05 (S01/S03); S05 touches only tests/ |

---

## Verdict

**NEEDS_FIX**

The suite is high quality and would have caught the original bug. The two findings
(HIGH: missing deprecation warning test; MEDIUM: weak specific-value assertion on the
port placeholder) should be addressed before S07 final review. Both are fixable in S05
scope with minimal changes:

1. **HIGH fix**: Add `test_deprecation_warning_fires_when_assert_not_agent_context_called`
   to `tests/unit/test_safe_migrate_guards.py` using `pytest.warns(DeprecationWarning)`.
2. **MEDIUM fix**: Either (a) update the implementation to include the resolved port in
   the error message and assert `"5433" in stderr`, or (b) keep the placeholder but add
   a second specific assertion on the remediation string's presence.
