# I-00058_S06_CodeReview_Tests_prompt

**Work Item**: I-00058 — DocGenerationJob IDs are UUIDs instead of sequential DOC-NNNNN identifiers
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Allowed exceptions: testcontainers (pytest), read-only introspection, `./ai-core.sh` / `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00058 --json`
- `ai-dev/active/I-00058/I-00058_Issue_Design.md` — Design document
- `ai-dev/active/I-00058/reports/I-00058_S05_Tests_report.md` — S05 implementation report
- All files listed in the S05 report's `files_changed`
- `tests/CLAUDE.md` — test conventions

## Output Files

- `ai-dev/active/I-00058/reports/I-00058_S06_CodeReview_Tests_report.md` — Review report

## Context

You are reviewing the tests written in S05 for **I-00058**. Focus on semantic correctness — not just that the tests exist and run, but that they would fail on buggy code and catch regressions.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

## Review Checklist

### 1. Reproduction test presence and correctness
- Is there a test that would FAIL against pre-fix code (no `public_id` column / listener)?
- Does the test use `db_session.flush()` to trigger the `before_insert` listener?
- Does it assert `job.public_id.startswith("DOC-")` **and** a regex check like `re.match(r"^DOC-\d{5}$", job.public_id)`?
- Does it assert the `public_id` is NOT a UUID? (Specific value check, not just non-null.)

### 2. Sequential increment test
- Are two jobs inserted and their `public_id` values asserted as `"DOC-00001"` and `"DOC-00002"` (exact values)?
- Is this an integration test against the testcontainer DB (not mocked)?

### 3. Aggregator tests
- Is `JobRow.job_id` asserted to equal `"DOC-00001"` when `public_id` is set? (Not just non-null.)
- Is the legacy UUID fallback tested (job with `public_id=None` returns UUID as `job_id`)?

### 4. Semantic correctness (I003 lesson)

Flag as HIGH any test that only checks:
- `assert job.public_id is not None` — not semantic
- `assert len(job.public_id) > 0` — not semantic
- `assert "DOC" in job.public_id` — too weak (a UUID with "DOC" somewhere would pass)

Required semantic assertions:
- `assert re.match(r"^DOC-\d{5}$", job.public_id)` or equivalent exact check
- `assert job.public_id == "DOC-00001"` for the first insertion

### 5. Test isolation
- Does each test clean up `id_sequences` rows or use a fresh testcontainer DB? No test should depend on another test's counter state.
- Is the testcontainer used (not port 5433)?

### 6. Conventions
- Does the file follow `tests/CLAUDE.md` naming and fixture conventions?
- Is `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` called where needed?

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00058",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
