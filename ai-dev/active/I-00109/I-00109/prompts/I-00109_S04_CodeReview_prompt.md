# I00109_S04_CodeReview_prompt

**Work Item**: I-00109 -- `GET /project/{project_id}/docs/{doc_id}/pdf` raises unhandled `PermissionError` → HTTP 500 when on-disk PDF cache dir is not writable
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. You MUST NOT run any `alembic upgrade/downgrade/stamp` command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00109 --json`.
- `ai-dev/active/I-00109/I-00109_Issue_Design.md` -- Design document (read §Acceptance Criteria, §TDD Approach, §Regression Prevention).
- `ai-dev/active/I-00109/reports/I-00109_S03_Tests_report.md` -- S03 implementation report.
- All files listed in S03's `files_changed` (expected: `tests/dashboard/test_docs_pdf_cache_failure.py` (new), `tests/dashboard/test_route_contract_sweep.py` (modified)).
- `tests/dashboard/conftest.py` -- The `client` fixture (registered here only — tests using `client` MUST live under `tests/dashboard/`).
- `dashboard/routers/docs.py` -- Read-only: confirm the cross-step coherence (the test exercises the guarded code path S01 added).
- `tests/CLAUDE.md` -- Test layer conventions; assertion-strength rules.
- `skills/iw-ai-core-testing/SKILL.md` -- Mutation-test question (§0).

## Output Files

- `ai-dev/active/I-00109/reports/I-00109_S04_CodeReview_report.md` -- Review report.

## Context

S03 added a regression test pinning the I-00109 contract (route returns 200 + PDF on read-only `repo_root`) and removed the `EXPECTED_5XX` entry from the route sweep. Your review must verify the test asserts SEMANTIC correctness (not shape), the `EXPECTED_5XX` removal is in the same commit as the route fix, the test file lives under `tests/dashboard/` (the `client`-fixture rule), and the test would actually fail against pre-fix code.

## Read the Design Document FIRST

Read `ai-dev/active/I-00109/I-00109_Issue_Design.md` in full **before** running the lint/format gate. Specifically:

- §Acceptance Criteria — AC1 lists the EXACT post-fix assertions (status 200, Content-Type `application/pdf`, body starts with `%PDF`, Content-Disposition `attachment`, warning logged, no unhandled exception, `pdf_path` not updated). Every one of these MUST appear as an assertion in S03's test. Any missing assertion is a **CRITICAL** finding (semantic-incompleteness vs the design's pinned contract).
- §TDD Approach — the design names the test file `tests/dashboard/test_docs_pdf_cache_failure.py` by path. Verify it appears in S03's `files_changed`; if not, **CRITICAL**.
- §File Manifest — `tests/dashboard/test_docs_pdf_cache_failure.py` is listed as a new file; `tests/dashboard/test_route_contract_sweep.py` is listed as modified. Anything else in `files_changed` is a scope violation — **HIGH**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

If either reports NEW violations on the changed files, flag as **CRITICAL** with `"category": "conventions"`.

If a tool is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Semantic Correctness, Not Shape (CRITICAL)

For the new test `test_docs_pdf_returns_200_when_cache_dir_not_writable`, verify EVERY assertion is semantic:

- `assert resp.status_code == 200` ✓ (NOT `< 500`, NOT `!= 500`, NOT `in (200, 202)`).
- `assert resp.headers["content-type"] == "application/pdf"` ✓ (NOT `"pdf" in content-type`).
- `assert resp.content.startswith(b"%PDF")` ✓ (NOT `len(resp.content) > 0`, NOT `resp.content != b""`).
- `assert "attachment" in resp.headers["content-disposition"]` ✓ (NOT just checking the header exists).
- A `WARNING`-level log record containing the exact substring `"Failed to write pdf_path cache for doc"` is captured ✓ (NOT just `len(caplog.records) > 0`).
- `db_session.refresh(doc); assert doc.pdf_path is None` ✓ (proves the cache write failed AND the guard caught it — without this assertion, the test would pass even if the route silently corrupted the DB column).

Any shape-only assertion is a **HIGH** finding — quote the line, explain why a mutation in the production code wouldn't fail the test, and recommend the strengthened form. Reference the I003 lesson from `skills/iw-ai-core-testing/SKILL.md` §0.

### 2. The Test Would Fail Against Pre-Fix Code (HIGH)

Reason about whether the test would fail against `dashboard/routers/docs.py` BEFORE S01's guard was added:

- Pre-fix, the unguarded `cache_dir.mkdir(...)` raises `PermissionError`.
- FastAPI surfaces it as HTTP 500.
- `resp.status_code` is 500, not 200 → first assertion fails.

If the test would pass against pre-fix code (e.g. it patches the production code itself, or it asserts on a path that doesn't actually exercise the cache write), flag as **HIGH** — the test does not pin the bug.

You may optionally (not mandatorily) verify by `git stash`-ing S01's `dashboard/routers/docs.py` change and re-running the targeted test file. State explicitly whether you performed the stash-recheck.

### 3. File Location Discipline (CRITICAL)

The new test file MUST live at `tests/dashboard/test_docs_pdf_cache_failure.py`. Per `tests/CLAUDE.md`, the `client` fixture is registered only in `tests/dashboard/conftest.py`; a file under `tests/unit/` or `tests/integration/` would fail at collection with `fixture 'client' not found` (I-00067 lesson). If the file is in the wrong directory, flag as **CRITICAL**.

### 4. `EXPECTED_5XX` Removal Is in the Same Commit as the Test (HIGH)

Verify that S03's `files_changed` contains BOTH:

- `tests/dashboard/test_docs_pdf_cache_failure.py` (new, the regression).
- `tests/dashboard/test_route_contract_sweep.py` (modified, with the `EXPECTED_5XX` entry removed).

If only one is present, flag as **HIGH** — splitting the removal from the test breaks the regression-net story (the sweep would still report `XPASS(strict)`→FAIL until the entry is removed).

Verify the `EXPECTED_5XX` declaration is preserved as `EXPECTED_5XX: dict[str, str] = {}` (or left with other unrelated entries if any were added since I-00109's design time). Removing the surrounding declaration or the explanatory comment block is a **MEDIUM_FIXABLE** finding.

### 5. No Manual Source Revert (HIGH)

Verify S03 did NOT use `git stash`, `git checkout HEAD~1 -- ...`, or any other runtime source-revert to "verify the test would have caught the bug." Such operations are thrash-prone in worktrees (see I-00073 post-mortem). If the report mentions a runtime source revert, flag as **HIGH**.

### 6. No Full-Suite Run Inside the Step (MEDIUM_FIXABLE)

S03's verification must run ONLY the two test files it touched (`uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov`). If S03's `test_summary` reports running `make test-integration`, `make test-unit`, or the full dashboard suite, flag as **MEDIUM_FIXABLE** — those are S10/S11/S07 QV gates and duplicating them inside the step blows the timeout budget (I-00073/S03 post-mortem).

### 7. Scope Discipline (CRITICAL)

S03's `files_changed` must contain ONLY the two test files. Touching `dashboard/routers/docs.py` (or any other file) is a scope violation — **CRITICAL** (the merge gate will block it regardless).

### 8. Project Conventions

- File header `from __future__ import annotations` (project default for new test files).
- Imports follow ruff's isort order.
- Docstring mentions I-00109 by ID (operators grep by incident ID).
- No bare `mock.patch(...)` — use `monkeypatch` (fixture-style).
- `caplog.at_level("WARNING", logger="dashboard.routers.docs")` is scoped to the route's logger (not all loggers).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the targeted test files:
   ```bash
   uv run pytest tests/dashboard/test_docs_pdf_cache_failure.py tests/dashboard/test_route_contract_sweep.py -v --no-cov
   ```
   Expected: new test passes; sweep case for the docs-pdf route passes as a normal pass (no longer xfail-marked); all other sweep cases pass.

2. Run `make test-unit` to confirm no broader regressions. (Cheap, ~seconds.)

Do NOT run `make test-integration` — that is the S11 QV gate.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Shape-only assertions; wrong test directory; scope violation; missing test the design names by path | Must fix before merge |
| **HIGH** | Test would pass against pre-fix code; `EXPECTED_5XX` removal split from the test; manual source revert in the step | Must fix before merge |
| **MEDIUM (fixable)** | Full-suite run inside the step; convention drift; missing log scope | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Add an additional edge-case test (e.g. `write_bytes` failing instead of `mkdir`) | Optional, author decides |
| **LOW** | Nitpick / style | Informational only |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00109",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "test_docs_pdf_returns_200_when_cache_dir_not_writable: PASSED; route sweep cases for docs-pdf: PASSED (normal pass after EXPECTED_5XX removal); make test-unit: <N> passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE findings.
