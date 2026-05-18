# I-00101_S06_CodeReview_Tests_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step Being Reviewed**: S05 (Tests)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures invoked by pytest are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations in S05.

## Input Files

- `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — READ FIRST
- `ai-dev/active/I-00101/reports/I-00101_S05_Tests_report.md`
- Four new test files in S05's `files_changed`
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — test-quality rules

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S06_CodeReview_Tests_report.md`

## Context

Reviewing test coverage and quality. Tests are the regression-prevention spine for this incident — review with appropriate rigor.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. File locations

- `test_fix_cycle_budget_exemption.py` lives under `tests/unit/daemon/`.
- `test_scope_amendment.py` lives under `tests/unit/daemon/`.
- `test_scope_blocked_badge.py` lives under `tests/dashboard/` (NOT `tests/unit/`; the `client` fixture is registered only in `tests/dashboard/conftest.py` per I-00067). **CRITICAL** if misplaced.
- `test_scope_amend_endpoints.py` lives under `tests/integration/`.

### 2. Assertion strength — semantic, not shape

For every assertion in all four files, classify:
- **Shape-only** (BAD): `assert "key" in dict`, `assert len(x) > 0`, `assert x is not None` for non-bool checks. **CRITICAL** finding per the I003 lesson the design doc cites.
- **Semantic** (GOOD): `assert x == specific_value`, `assert specific in collection`, `assert sequence == [exact, list]`.

Surface every shape-only assertion as **CRITICAL** with file:line.

### 3. Required test coverage

Verify all the design's named tests exist with the right names:

- `test_fix_cycle_budget_exemption.py`: at least 4 tests including `test_i00101_scope_escalated_cycle_not_counted_toward_per_step_budget`, `..._aggregate_budget`, `..._non_scope_escalated_cycle_IS_counted`, `..._failed_cycle_IS_counted`. Missing any of the four is **HIGH**.
- `test_scope_amendment.py`: at least 9 tests covering amend (both manifests + idempotency + key preservation + missing parent), revert (success + failure), and `latest_scope_violation` (latest semantics + None for no cycle + None for empty list). Missing any of the named cases is **HIGH**.
- `test_scope_blocked_badge.py`: at least 4 tests — badge renders, badge omitted when no violations, Restart button hidden on scope-blocked row, amend modal trigger URL correct. **HIGH** on any missing.
- `test_scope_amend_endpoints.py`: at least 5 tests — amend full flow, revert full flow, 422 on non-scope-blocked, 422 on off-list paths, idempotency at endpoint level. **HIGH** on missing.

### 4. CSS class assertions

The dashboard test uses the attribute-scoped form `class="badge-scope-blocked"` (or whatever exact class S03 produced), NOT bare-substring. **HIGH** if any assertion uses the bare form (per CLAUDE.md I-00067).

### 5. DB mocking forbidden

The integration test uses the real testcontainer `db_session` fixture, NOT mocks (per CLAUDE.md). Any `Mock()` or `MagicMock()` standing in for a DB session = **CRITICAL**.

### 6. Fixture seeding correctness

- The integration test's seeding actually creates a `FixCycle` row with `fix_metadata={'scope_violations': [...]}` (JSONB) so the predicate from S01 is genuinely exercised — not just a Python dict in a Python-side filter. **HIGH** if the test sidesteps the JSONB path.
- The dashboard test's seeding produces a step row that the same query in `items.py` would pick up — i.e. it doesn't bypass the `latest_scope_violation` call by stuffing `step.scope_violations` directly into the template context. **HIGH** if it does.

### 7. Async / sync mismatch

All tests are sync (FastAPI's `TestClient` is sync). Any `async def test_…` is **CRITICAL**.

### 8. Test isolation

Tests use `tmp_path` for filesystem and the per-test DB fixture for the database. No shared state between tests. No reliance on test execution order. **HIGH** on shared-state coupling.

### 9. TDD RED evidence

S05's report records `tdd_red_evidence` with per-test reasoning OR documented RED runs against pre-fix code. The reasoning must be plausible (would the test actually fail against pre-S01 code?). Missing or implausible = **HIGH**.

### 10. Scope discipline

Files changed are ONLY the four new test files. Any other file = **CRITICAL** scope creep.

## Test Verification (NON-NEGOTIABLE)

Run the same targeted command the agent ran:

```bash
uv run pytest \
  tests/unit/daemon/test_fix_cycle_budget_exemption.py \
  tests/unit/daemon/test_scope_amendment.py \
  tests/dashboard/test_scope_blocked_badge.py \
  tests/integration/test_scope_amend_endpoints.py \
  -v --no-cov
```

Confirm all pass. If any fail, **HIGH** finding with the failure output.

## Review Result Contract

Standard JSON contract.

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00101",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
