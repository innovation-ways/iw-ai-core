# I00103_S06_CodeReview_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document (§TDD Approach pins exact test names + assertions).
- `ai-dev/active/I-00103/reports/I-00103_S05_Tests_report.md` -- S05 report.
- `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md` and `I-00103_S03_Frontend_report.md` -- Source-of-truth for the contracts under test.
- `tests/integration/test_auto_merge_failed_event_metadata.py` (S05's new file).
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` (S05's new file).
- `skills/iw-ai-core-testing/SKILL.md` -- Project testing standards.

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S06_CodeReview_report.md` -- Review report.

## Context

S05 wrote the reproduction + regression tests for I-00103 across two layers. Your job is to verify the tests pin the right contracts, use semantic assertions (not shape-only), and follow project testing rules.

## Read the Design Document FIRST

- `## TDD Approach` — every test the design names by path MUST exist in S05's `files_changed`. Any missing test is a **CRITICAL** finding.
- `## Acceptance Criteria` AC1, AC2, AC3, AC4, AC5 — each must be covered by at least one test.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in the new test files, classify as **CRITICAL** findings.

## Review Checklist

### 1. Test files exist with the documented names

- `tests/integration/test_auto_merge_failed_event_metadata.py` — present. MISSING ⇒ CRITICAL.
- `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` — present. MISSING ⇒ CRITICAL.

### 2. Cases match the design doc

For each of the 4 unit cases and 3 dashboard cases listed in §TDD Approach, verify there is a test function whose body matches the documented intent. A test with the right name but a stub body is a CRITICAL finding.

### 3. Semantic correctness, NOT shape-only

For each assertion:

- BAD: `assert "per_file_errors" in metadata` (passes even if value is `[]`)
- GOOD: `assert metadata["per_file_errors"][0]["error"] == expected` OR `assert "LLM call timed out after 120s" in metadata["per_file_errors"][0]["error"]`

Any test that only checks shape (key presence, length > 0) without checking specific values is a **HIGH** finding. The I003 lesson is non-negotiable.

### 4. CSS class assertions are attribute-scoped (I-00067 lesson)

For each dashboard test asserting on rendered HTML:

- BAD: `assert "per-file-error" in html`
- GOOD: `assert 'class="auto-merge-modal__per-file-error"' in html` OR a regex anchored on the attribute.

Any bare-substring class assertion is a **HIGH** finding (false-positive risk against `<script>` JSON / `data-*` / CSS source maps).

### 5. Test placement is correct

- The backend reproduction/regression test MUST be under `tests/integration/` (`test_auto_merge_failed_event_metadata.py`). It drives `attempt_resolution` and round-trips a `DaemonEvent` JSONB payload, so it requires the testcontainer-backed `db_session`. Placement under `tests/unit/` is a HIGH finding — the `tests/unit/` `db_session` is a `MagicMock` and the test cannot work there.
- Dashboard tests under `tests/dashboard/`: required because they use the `client` fixture (I-00067).
- Wrong placement is a HIGH finding.

### 6. RED proof

The `tdd_red_evidence` field should reference the pre-fix evidence in `evidences/pre/` and / or the historical events 80689 / 88770. A `tdd_red_evidence` value like `"n/a"` or empty string for a `tests-impl` step is a MEDIUM_FIXABLE finding — `tests-impl` is exempt from the live RED-run requirement (because the fix has already landed), but it MUST cite the design-time RED proof.

### 7. Fixture & isolation rules

- Tests MUST NOT connect to the live DB on port 5433. Look for `IW_CORE_DB_PORT` / `IW_CORE_DB_HOST` env reads inside the test or any `psycopg2` connection strings without testcontainer fixtures. Any direct live-DB connection is a CRITICAL finding.
- Tests MUST NOT mock the database; use testcontainer fixtures.
- `DaemonEvent.metadata` is `event_metadata` in Python. If the test asserts on `event.metadata` rather than `event.event_metadata`, that's a HIGH finding (it will silently get the SQLAlchemy DeclarativeBase's `metadata` table-registry object, not the JSONB column).

### 8. Tests actually pass

Run the new test files:

```bash
uv run pytest tests/integration/test_auto_merge_failed_event_metadata.py -v
uv run pytest tests/dashboard/test_auto_merge_event_detail_per_file_errors.py -v
```

Any failure is a CRITICAL finding (the test author is responsible for green tests on submission).

### 9. Cross-test independence

- No test should depend on another test's side effects.
- Each test fixture sets up its own state and tears down.
- No use of `pytest.mark.order` to enforce sequencing (project convention).

### 10. No test pollution of the live DB

(Repeat for emphasis.) The `db_session` and `client` fixtures from `tests/conftest.py` / `tests/dashboard/conftest.py` use testcontainers. Any deviation is a CRITICAL finding.

## Test Verification (NON-NEGOTIABLE)

Run the two new test files (above). Run the existing auto_merge tests to confirm no regression:

```bash
uv run pytest tests/integration/test_auto_merge_phase1.py tests/dashboard/test_auto_merge_routes.py -v 2>&1 | tail -50
```

## Severity Levels

(Standard table — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.)

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00103",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
