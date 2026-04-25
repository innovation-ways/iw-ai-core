# I-00039_S04_CodeReview_prompt

**Work Item**: I-00039 -- Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard rule. Read-only docker introspection allowed. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Not relevant for this review — S03 only added test files. Verify no live-DB
migrations were run by the test step.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00039/I-00039_Issue_Design.md` — design document
- `ai-dev/active/I-00039/reports/I-00039_S03_Tests_report.md` — S03 report
- All files listed in S03's `files_changed` (expected:
  `tests/dashboard/test_jobs_filter_ui.py`)
- `tests/CLAUDE.md`, `tests/dashboard/conftest.py`, parent `tests/conftest.py`
- `tests/integration/test_jobs_api.py` (the seed pattern source)

## Output Files

- `ai-dev/active/I-00039/reports/I-00039_S04_CodeReview_report.md` — review

## Context

You are reviewing the test work done in S03. S03's job was to write
reproduction + regression tests that lock in the fix from S01. Your job is to
verify those tests actually do what they claim.

## Review Checklist

### 1. Semantic correctness over shape checking (CRITICAL — I003 lesson)

Every assertion MUST verify a **specific value**, not merely shape:

- BAD: `assert "type" in html` (only checks substring exists)
- BAD: `assert len(rows) > 0` (only checks non-empty)
- GOOD: `assert "bg-blue-100" not in html` (specific class IS absent)
- GOOD: `assert 'data-multi-select="type"' in html` (specific marker IS present)
- GOOD: `assert ids["cij_id"] in html and ids["batch_id"] not in html` (specific row IS / IS NOT)

Walk through every `assert` in `tests/dashboard/test_jobs_filter_ui.py`. Any
assertion that only checks shape, not semantics, is a CRITICAL finding.

### 2. Tests would actually FAIL pre-fix

For each test, mentally simulate the pre-fix HTML (the design document's
`Root Cause Analysis` section describes it: `type_chip` macro emitting
`<span class="... bg-blue-100 text-blue-700 ...">code_mapping</span>` and
flat `<label><input type="checkbox" name="type" value="...">` rows). Confirm
each assertion would fail against that HTML.

If a test would PASS against the pre-fix HTML, it is not a real reproduction
test — that is a CRITICAL finding.

The S03 report should already contain this reasoning. Sanity-check it.

### 3. No live-DB connections

Verify no test in the new file uses anything other than the standard
testcontainer fixtures (`client`, `db_session`, `test_project`). If any
test imports `orch.db.session.SessionLocal` or hits port 5433, that is a
CRITICAL finding (per `CLAUDE.md`'s "NEVER connect tests to live DB" rule).

### 4. Test isolation

- Each test uses fresh fixtures or explicitly seeds and cleans state.
- Tests are deterministic — no time-of-day assumptions, no randomness without
  fixed seed.
- Tests use the project's standard `_seed_all_sources` pattern from
  `tests/integration/test_jobs_api.py` — verify the import or duplication is
  correct and current.

### 5. Coverage

The design's three test scenarios MUST all be present:

1. Type cell has no `bg-(blue|purple|orange|teal|emerald)-100` classes.
2. Filter renders `data-multi-select="type"` and `data-multi-select="status"`
   markers AND does NOT render flat `<input type="checkbox" name="type">` /
   `<input type="checkbox" name="status">` at the form root.
3. Multi-value query (`?type=A&type=B`) still filters correctly.

Missing any of the three is a HIGH finding.

### 6. Conventions

- Test file location: `tests/dashboard/test_jobs_filter_ui.py` per the
  design's File Manifest.
- Test naming follows existing patterns in `tests/dashboard/`.
- Imports organised per project style (ruff isort rules).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the new test file:
   ```bash
   uv run pytest tests/dashboard/test_jobs_filter_ui.py -v
   ```
   All tests must pass.
2. Run `make lint` and `make test-unit` to confirm no regressions.
3. Report results in the contract.

If the new tests do NOT pass against the current (post-S01) code, that is a
CRITICAL finding — it means either S01 is incomplete or S03's tests are
wrong.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Tests check only shape; tests pass against pre-fix code; live-DB connection | Must fix before merge |
| HIGH | Missing one of the three required scenarios; broken isolation | Must fix before merge |
| MEDIUM (fixable) | Brittle assertion (whitespace-sensitive in a fragile way), poor naming | Should fix in fix cycle |
| MEDIUM (suggestion) | Could share more helpers with `test_jobs_api.py` | Optional |
| LOW | Minor readability nits | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00039",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions",
      "file": "tests/dashboard/test_jobs_filter_ui.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3 dashboard tests passed; full unit suite X passed, 0 failed",
  "notes": ""
}
```
