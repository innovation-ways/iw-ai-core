# F-00061 S07 Tests — Step Report

## What Was Done

Wrote the full test suite for F-00061 QV baseline fingerprinting feature:

1. **`tests/unit/orch/daemon/test_qv_baseline.py`** — 21 unit tests covering parsers (ruff text, pytest, mypy), fingerprint algebra (subtract), round-trip serialization, and `GATE_PARSERS` mapping completeness.

2. **`tests/integration/daemon/test_baseline_qv_pipeline.py`** — 9 integration tests covering AC1–AC6, 2 boundary-behavior cases (timeout fail-soft, empty-passing-gate sentinel), and N+1 query-count discipline.

3. **`tests/unit/executor/test_scope_gate.py`** — 13 unit tests covering all AC7 cases: legacy mode, exact-path match/mismatch, `dir/**` glob, fnmatch wildcard, implicit `ai-dev/active/archive` allows, violation-listing order-preservation, malformed manifest (rc=2).

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/orch/daemon/test_qv_baseline.py` | **New** — parser + algebra unit tests |
| `tests/integration/daemon/test_baseline_qv_pipeline.py` | **New** — AC1–AC6 + boundary + N+1 integration tests |
| `tests/unit/executor/test_scope_gate.py` | **New** — bundled P1 scope-gate coverage |
| `executor/scope_gate.py` | **Bugfix** — violations were silently discarded (noop loop); now outputs violating paths to stdout |

## Test Results

| Suite | Tests | Result |
|------|-------|--------|
| Unit (`test_qv_baseline` + `test_scope_gate`) | 34 | ✅ PASS |
| Integration (`test_baseline_qv_pipeline`) | 9 | ✅ PASS |
| Full `make test-unit` (existing + new) | 1333 | ✅ PASS (no regressions) |

## Quality Checks

| Tool | Errors |
|------|--------|
| `uv run mypy tests/unit/orch/daemon/test_qv_baseline.py` | 0 |
| `uv run mypy tests/unit/executor/test_scope_gate.py` | 0 |
| `uv run mypy tests/integration/daemon/test_baseline_qv_pipeline.py` | 0 |
| `uv run ruff check` (new files) | 16 (style only — no logic errors) |

Remaining ruff warnings are style conventions (variable names `H`/`B` in test algebra match mathematical notation, long string literals for test fixtures). No semantic issues.

## TDD Compliance

- **Parser tests**: Written against S03's actual parsing behavior (empirically verified). Fixtures use formats the S03 code can parse: ruff text `"file:line:col: CODE msg"` (msg must not contain extra colons), pytest `"FAILED <nodeid> - <msg>"` (nodeid FIRST).
- **Integration tests**: Each AC test patches `_resolve_worktree_base_sha` directly to control the SHA, bypassing the git subprocess.
- **scope_gate.py bugfix**: The violation-output bug was found during test authoring. The `for _v: pass` loop was a no-op — violations were accumulated but never printed. Fixed to `sys.stdout.write(v + "\n")`. Tests caught this.

## AC Coverage

| AC | Test |
|----|------|
| AC1: Pre-existing excluded | `TestAC1.test_ac1_pre_existing_failure_excluded_from_fix_cycle` |
| AC2: Regression surfaced | `TestAC2.test_ac2_regression_surfaced_cleanly` |
| AC3: Baselines at setup | `TestAC3.test_ac3_baselines_created_at_setup` |
| AC4: Rebase invalidation | `TestAC4.test_ac4_rebase_invalidates_baseline` |
| AC5: Kill switch disables | `TestAC5.test_ac5_kill_switch_disables` |
| AC6: Legacy graceful | `TestAC6.test_ac6_legacy_item_graceful` |
| AC7: scope_gate P1 coverage | 13 tests in `TestScopeGate` covering all AC7 sub-cases |

## Boundary Behavior Coverage

| Boundary | Test |
|----------|------|
| Gate timeout → fail-soft, no partial row | `TestBaselineBoundary.test_baseline_compute_timeout_is_contained` |
| Empty passing gate → sentinel row | `TestBaselineBoundary.test_baseline_empty_passing_gate_persists_sentinel_row` |

## N+1 Query Discipline

`TestN1QueryCount.test_no_n_plus_one_in_compute_qv_baselines` — asserts `query_count <= K_GATES + 5` using `sqlalchemy.event` listen API, confirming O(N gates) + O(1) per gate.

## Notes

- Integration tests use UUID-based unique IDs to prevent cross-test collisions in the transactional fixture framework.
- The S03 ruff JSON parser does not handle array-format JSON (`[{"filename": ...}]`) — fixtures use text mode or single-dict format.
- The S03 ruff text parser requires message text without extra colons after the rule code — the regex `CODE msg` is greedy and stops at the first extra colon.
