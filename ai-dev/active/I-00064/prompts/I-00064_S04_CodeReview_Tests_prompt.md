# I-00064_S04_CodeReview_Tests_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

(Standard policy. Allowed exceptions: testcontainer fixtures, read-only
introspection, `./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item does not touch migrations.)

## Input Files

- `uv run iw item-status I-00064 --json` — runtime step state.
- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design.
- `ai-dev/active/I-00064/reports/I-00064_S03_Tests_report.md` — S03 report.
- `tests/integration/test_i00064_doc_generation_view_document_url.py` — the new tests.

## Output Files

- `ai-dev/active/I-00064/reports/I-00064_S04_CodeReview_Tests_report.md`

## Context

Review the tests written in S03. The bug (I-00064) is a real, reproducible
404 — your job is to confirm the new tests really catch it.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violations in the new test file → CRITICAL with
`"category": "conventions"`.

## Review Checklist

### 1. Falsifiability — does the reproduction test really fail pre-fix?

For `test_i00064_reproduces_bug`:

- The assertion `row.raw["doc_id"] == "code-index"` would fail against
  the pre-fix code (which returned the composite). ✅ verify the
  assertion is actually written that way.
- The assertion `":" not in row.raw["doc_id"]` is a strong
  anti-shape guard. ✅ verify it is present and not weakened to
  `not row.raw["doc_id"].startswith(...)` or similar.

If the test could pass pre-fix (e.g., because it only asserts truthiness
or shape), classify as **CRITICAL** — "Reproduction test is not
falsifiable; passes against the buggy code".

### 2. Semantic correctness, not shape

Walk every `assert` in the new file. Each one should verify a SPECIFIC
expected value or a SPECIFIC unwanted value. Reject:

- `assert "doc_id" in row.raw` (shape only)
- `assert row.raw["doc_id"]` (truthiness — passes for the composite)
- `assert isinstance(row.raw["doc_id"], str)` (type only)

### 3. End-to-end reach

For `test_i00064_view_document_link_resolves`:

- Does it actually call the FastAPI TestClient against
  `/project/iw-ai-core/docs/{row.raw['doc_id']}` — i.e., **using the
  same value the template uses**, not a hardcoded `code-index`?
- Does it assert `response.status_code == 200`?
- Bonus: does it confirm the response body contains content from the
  doc (title or content snippet)?

### 4. Orphan case

For `test_i00064_orphan_doc_id_is_none`:

- Both sub-cases covered (doc_id=None, AND doc deleted after job
  insert)?
- Asserts `row.raw["doc_id"] is None` (specific value), not just falsy?

### 5. Fixture hygiene

- Does the test use the project's `db_session` fixture (testcontainer-
  backed)?
- Does it follow `tests/CLAUDE.md` rules (no live DB, no
  `importlib.reload`, no DB mocks, psycopg URL replacement,
  `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` already wired by the fixture)?
- Uses `db_session.flush()` / `db_session.commit()` correctly for the
  TestClient's read?

### 6. No leakage between tests

- Each test arranges its own rows.
- No reliance on test ordering.
- No global state mutated.

### 7. Naming and structure

- Test file at `tests/integration/test_i00064_doc_generation_view_document_url.py`.
- Function names match `test_i00064_*` pattern.
- Each function has a docstring explaining its claim.

### 8. No collateral regressions

- Does the existing
  `tests/integration/test_i00059_doc_generation_get_job.py` still pass?
  (The line-92 assertion `row.raw.get("doc_id") is None` for the orphan
  case should still hold.)

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration`. Confirm the 3 new tests pass and no other
test regressed. Run `make test-unit` for completeness.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Reproduction test is not falsifiable, or asserts shape only |
| HIGH | Missing end-to-end TestClient case; orphan case missing/weak |
| MEDIUM_FIXABLE | Assertion message missing, fixture inefficient, naming inconsistent |
| MEDIUM_SUGGESTION | Style improvement, fixture extraction |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00064",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict` is `pass` only when CRITICAL + HIGH + MEDIUM_FIXABLE = 0.
