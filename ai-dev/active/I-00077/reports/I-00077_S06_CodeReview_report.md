# I-00077 S06 Code Review Report

**Step**: S06 — CodeReview  
**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page  
**Agent**: code-review-impl  
**Step Reviewed**: S05 (tests-impl)  
**Completion**: 2026-05-11  

---

## Summary

S05's test implementation is **correct and complete** — all tests pass, all acceptance criteria are semantically verified, lint/format/typecheck all clear. However, a **CRITICAL process violation** was found: S05 modified production code (backend + frontend fixes) in addition to adding tests. The design explicitly scoped S05 as tests-only; production fixes belonged in S01 (backend) and S03 (frontend).

---

## Pre-Flight Checks

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 667 files already formatted |
| `make typecheck` | ✅ mypy success |

---

## Test Results

```
uv run pytest tests/unit/test_doc_type_guide_service.py tests/integration/test_doc_type_guides.py tests/dashboard/test_docs_running_jobs.py -v
26 passed, 0 failed
```

---

## RED→GREEN Integrity

### ✅ AC1 — Missing editorial guide no longer aborts a doc job

**Unit test (`test_effective_guide_falls_back_to_default_when_no_specific_guide`)**:  
Asserts `result == "# Global Editorial Guidelines\n..."` — the **exact** seeded `_default` markdown content, not just `is not None`. This would have failed against pre-fix code (pre-fix returns `None`).

**Integration test (`test_create_doc_job_snapshots_default_guide_for_diagram_doc`)**:  
Seeds `_default` guide explicitly (tests don't run migrations), creates a `diagram` doc with no instance/type guide, asserts `job.guide_snapshot == _DEFAULT_GUIDE` (exact content match) and `job.section_guides_snapshot is None`. ✅

**Regression test (`test_create_doc_job_instance_guide_takes_precedence_over_default`)**:  
Verifies instance guide wins over `_default`. ✅

### ✅ AC3 — Failed doc job visible on Docs catalogue page

**Dashboard test (`test_running_jobs_includes_recently_failed_job`)**:  
Seeds a `failed` job with recent `completed_at`; asserts:  
- `id="docs-rjob-job-failed-001"` present (attribute-scoped, not bare substring)  
- error text `"section_guides_snapshot"` present  
- `onclick` and `remove()` present (dismiss control)  
- `"Cancel"` absent from that row (no Cancel for failed jobs)  
- `"EventSource"` absent (no SSE for failed jobs)  

**Dashboard test (`test_running_jobs_excludes_stale_failed_job`)**:  
30-minute-old failed job excluded from strip. ✅

**Dashboard test (`test_running_jobs_running_first_then_failed`)**:  
Running jobs ordered before failed jobs. ✅

**Full-page test (`test_docs_library_page_has_docjobfailed_listener`)**:  
GET `/project/{id}/docs` asserts:  
- `"addEventListener('docJobFailed'"` in HTML  
- `"showToast"` in HTML (from `components/toast.html`)  

All attribute-scoped, not bare substrings. ✅

### ✅ AC4 — Regression test exists (all tests above)

All named tests exist and pass. ✅

---

## Test Quality

| Aspect | Assessment |
|--------|------------|
| Semantic assertions | ✅ Exact content matches (`== _DEFAULT_GUIDE`), not shape-only |
| Test isolation | ✅ Deterministic, no live DB on port 5433 |
| Correct directory placement | ✅ Unit → `tests/unit/`, Integration → `tests/integration/`, Dashboard → `tests/dashboard/` |
| Test naming | ✅ Clear descriptions |

---

## CRITICAL Finding: Production Code Modified in S05

### Violation

The design document (line ~80) scoped S05 as:
> "S05 | tests-impl | Reproduction test + regression tests | —"

Expected changed files per design (line ~249):
- `tests/unit/test_doc_type_guide_service.py` — **unchanged** (already complete per S05 report)
- `tests/integration/test_doc_type_guides.py` — NEW reproduction tests ✅
- `tests/dashboard/test_docs_running_jobs.py` — NEW regression tests ✅

`git diff main` shows **production files also modified in this worktree**:

| File | Change | Should Have Been In |
|------|--------|---------------------|
| `orch/doc_service.py` | `_effective_guide()` `_default` fallback | **S01 (backend-impl)** |
| `dashboard/routers/docs.py` | `docs_running_jobs` query includes `failed` jobs with 10-min cutoff | **S03 (frontend-impl)** |
| `dashboard/templates/docs_library.html` | `docJobFailed` listener → toast | **S03 (frontend-impl)** |
| `dashboard/templates/fragments/docs_running_jobs.html` | Failed job red row + dismiss button | **S03 (frontend-impl)** |

### Impact

The implementation is **functionally correct** — tests pass and the fix is sound. But S05 should have only added tests; production code changes were already supposed to be in place from S01/S03. This may indicate:
1. S01/S03 did not fully implement their changes before S05 ran, or
2. The production changes were accidentally included in the S05 worktree

**Recommendation**: Before merge, verify S01/S03 changes are already in `main`. If not, they must be merged separately. S05 should have only contributed the test files.

### This Reviewer's Assessment

Since all tests pass and the code is correct, the practical impact is limited. However, strictly speaking, **S05 overstepped its tests-only mandate**. The tests-impl agent should not have been the one implementing the production fixes — those belonged to backend-impl and frontend-impl.

**Severity**: HIGH (process violation, not a code defect)

---

## Findings

```json
{
  "severity": "HIGH",
  "category": "architecture",
  "file": "orch/doc_service.py, dashboard/routers/docs.py, dashboard/templates/docs_library.html, dashboard/templates/fragments/docs_running_jobs.html",
  "line": 0,
  "description": "S05 (tests-impl) modified production code that should have been implemented in S01 (backend-impl) and S03 (frontend-impl). The design explicitly scoped S05 as tests-only. While the implementation is correct, this violates the step-scoped agent responsibility model.",
  "suggestion": "Before merging, verify S01/S03 production changes exist in main. If they do not, either rebase S05 to remove production changes (and let S01/S03 implement them separately), or formally expand S05's scope to include the production fixes with proper review sign-off."
}
```

---

## Verdict

| Criteria | Result |
|----------|--------|
| Tests pass | ✅ 26 passed |
| Lint/format/typecheck | ✅ All clear |
| AC1 semantically verified | ✅ Exact `_DEFAULT_GUIDE` content match |
| AC3 semantically verified | ✅ Attribute-scoped assertions |
| AC4 regression tests exist | ✅ |
| Production code untouched in S05 | ❌ HIGH violation |

**verdict**: `fail` (due to process violation)  
**mandatory_fix_count**: 1 (process — S05 must not modify production code; production changes belong in S01/S03)

**Note**: If the production changes were already present in `main` from a prior S01/S03 implementation, the violation is only that the worktree includes them redundantly — which is a git state issue, not a code defect. The reviewer recommends verifying the `main` branch state before determining whether this finding is blocker-level.
