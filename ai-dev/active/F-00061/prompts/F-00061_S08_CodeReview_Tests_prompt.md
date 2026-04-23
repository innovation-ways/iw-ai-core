# F-00061_S08_CodeReview_Tests_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S08
**Agent**: code-review-impl
**Reviews**: S07 (Tests)

---

## ⛔ Docker is off-limits

(Same policy as S01. Testcontainers spun up by pytest are the ONLY allowed docker interaction. Read-only `docker ps/inspect/logs` is fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(NEVER `alembic upgrade|downgrade|stamp` against port 5433. Tests' own testcontainer migrations are handled by the fixture chain.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — **Acceptance Criteria AC1–AC7**, **Boundary Behavior**, **Invariants**, **TDD Approach**
- `ai-dev/active/F-00061/reports/F-00061_S07_Tests_report.md` — S07's self-report with AC-to-test mapping
- `tests/unit/orch/daemon/test_qv_baseline.py` — unit tests
- `tests/integration/daemon/test_baseline_qv_pipeline.py` — integration tests
- `tests/unit/executor/test_scope_gate.py` — bundled P1 coverage
- `tests/CLAUDE.md` — testcontainer rules, fixture conventions, N+1 discipline

## Output Files

- `ai-dev/active/F-00061/reports/F-00061_S08_CodeReview_Tests_report.md`

## Context

Your review is the test-suite quality gate. F-00061's correctness in production depends entirely on these tests catching regressions in the parsers, subtraction, and daemon hook paths. A permissive test suite — one that passes on broken code, misses an AC, or uses mocks where testcontainers should be used — is worse than no tests because it gives false confidence.

## Review Checklist

### CRITICAL — must pass

1. **AC1–AC7 fully covered.** Confirm S07's `acceptance_criteria_coverage` mapping by opening each named test and verifying it genuinely exercises the AC's Given/When/Then. A test that never actually asserts the AC's outcome (e.g. checks that "no exception" was raised but doesn't check the subtraction result) is a CRITICAL gap.
2. **Tests FAIL on pre-fix code** (for AC1/AC2/AC3/AC4). Mentally run each integration test against a checkout where S03 + S05 are reverted — does it RED? If the test would pass against the base branch, it's not actually testing F-00061's behaviour. S07 should have documented this check; confirm.
3. **Testcontainer compliance**:
   - Zero references to `localhost:5433`, `postgresql+psycopg2://`, or `IW_CORE_DB_HOST=localhost` in the tests
   - All DB-touching tests use `db_session` from `tests/integration/conftest.py`
   - No `importlib.reload(orch.config)` calls
4. **No live-DB risk**: `git grep -n 'port.*5433' tests/unit/orch/daemon/ tests/integration/daemon/ tests/unit/executor/` returns nothing.
5. **Fingerprint determinism test exists** (Invariant 6): calling `parse_ruff`, `parse_pytest`, `parse_mypy` twice on the same input produces byte-identical JSON.
6. **Unparseable-survives-subtract test exists** (Boundary Behavior row 3, Invariant 5): `delta.unparseable` from `current` is preserved regardless of baseline.
7. **Scope gate tests cover ALL eight items in AC7 enumeration**: legacy-mode, exact-match, `dir/**`, fnmatch wildcard, implicit active allow, implicit archive allow, violation listing, malformed manifest. Cross-check one-to-one.
8. **Scope discipline in the diff**: `git diff main..HEAD --name-only` shows ONLY the new test files (plus F-00061 artefacts). If S07 accidentally modified `executor/scope_gate.py` or `orch/daemon/qv_baseline.py`, flag CRITICAL (out-of-scope drift).

### HIGH — should pass

9. **Query-count / N+1 discipline**: `test_no_n_plus_one_in_compute_qv_baselines` (or equivalent) exists and asserts a bounded query count per gate.
10. **Test isolation**: each integration test uses its own `db_session` scope; no cross-test state leakage. Spot-check a few setUp/tearDown patterns.
11. **Fixtures match house style**: sample gate outputs are either inline string literals or under a clearly named fixtures directory. No random test-file sprawl.
12. **`monkeypatch.setenv` used for kill-switch tests** (not `os.environ[...] = ...` which leaks across tests).
13. **Clear test names**: every `test_*` function name encodes the AC or behaviour it covers. No `test_1`, `test_behaviour`, etc.
14. **TDD documentation**: S07's report documents the RED-confirmation per test (or for the P1 tests, notes that RED phase is retroactive N/A).

### MEDIUM_FIXABLE — fix if noticed

15. Test docstrings link to the AC or Boundary Behavior row they cover.
16. Parametrized tests use descriptive `ids=` so failure output is human-readable.

### MEDIUM_SUGGESTION

17. Boundary Behavior rows 6–9 coverage — if all rows 1–5 and 6–9 are exercised, great. If any are missing, note which and let S09 decide if they're required for release.

## Verification Commands

- `make test-unit` — all new unit tests pass; no pre-existing regressions
- `make test-integration` — all new integration tests pass; no pre-existing regressions
- `uv run mypy tests/unit/orch/daemon/test_qv_baseline.py tests/integration/daemon/test_baseline_qv_pipeline.py tests/unit/executor/test_scope_gate.py` — zero errors
- `uv run ruff check tests/unit/orch/daemon/ tests/unit/executor/ tests/integration/daemon/` — zero errors on the new test files
- `git grep -n '5433\|psycopg2://\|importlib.reload' tests/unit/orch/daemon/ tests/integration/daemon/ tests/unit/executor/` — must return no matches

## Report

Standard CodeReview report. Findings grouped by severity. Overall verdict **pass** only if zero CRITICAL + zero HIGH.

Call `iw step-done` or `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "make test-unit + make test-integration green on F-00061 suite; no port 5433; no importlib.reload",
  "notes": ""
}
```
