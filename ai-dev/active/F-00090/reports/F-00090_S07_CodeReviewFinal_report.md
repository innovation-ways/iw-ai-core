# F-00090 S07 — Final Cross-Agent Code Review

## Summary
Reviewed S01..S05 together against the design AC1..AC8, checked cross-agent consistency/integration/security, and ran required gates:
- `make lint` ✅
- `make format` ✅
- `make test-unit` ✅ (3601 passed, 0 failed)

All 4 required TDD files are present in changed files:
- `tests/integration/test_regression_link_service.py`
- `tests/dashboard/test_regression_classification_form.py`
- `tests/dashboard/test_quality_kpis_section.py`
- `tests/integration/test_backfill_regression_classification.py`

## Findings

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00090",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05"],
  "verdict": "fail",
  "findings": [
    {
      "severity": "HIGH",
      "category": "consistency",
      "file": "dashboard/routers/items.py",
      "line": 2329,
      "description": "Cross-call inconsistency: UI suggestion paths call suggest_introducer() without repo_path, while CLI/backfill can pass it. Service then falls back to Path.cwd(), which may not be the managed project's repo root. This can silently suppress suggestions in UI for multi-repo/runtime contexts.",
      "suggestion": "Pass repo_path consistently from project.repo_root in all UI suggestion callsites (both _top_suggestion and GET /regression-suggestions), matching the explicit-path pattern used by CLI/backfill.",
      "cross_cutting": true
    },
    {
      "severity": "HIGH",
      "category": "completeness",
      "file": "dashboard/routers/project_dashboard.py",
      "line": 131,
      "description": "KPI denominator counts every completed WorkItem as a merge, including Incident rows. That conflicts with the intended regressions-to-merges metric and invalidates boundary semantics like 'zero merges, N regressions' in practical scenarios.",
      "suggestion": "Restrict merges/week query to true merge-source item types (exclude incident-class items) so regression rate reflects regressions per merge, not regressions per completed item.",
      "cross_cutting": true
    },
    {
      "severity": "MEDIUM_SUGGESTION",
      "category": "testing",
      "file": "tests/dashboard/test_quality_kpis_section.py",
      "line": 142,
      "description": "No holistic scenario test validates classify -> KPI section -> badge consistency in one flow. Current tests are split by surface.",
      "suggestion": "Add one end-to-end dashboard/integration test asserting that a classification write is reflected consistently in KPI cards and row badge counts.",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 2,
  "tests_passed": true,
  "test_summary": "make test-unit: 3601 passed, 0 failed, 7 skipped, 5 xfailed, 3 xpassed",
  "missing_requirements": [],
  "notes": "AC1..AC8 all map to implementation paths and tests; required test files exist; no new lint/format violations."
}
```

## Files changed
- `ai-dev/active/F-00090/reports/F-00090_S07_CodeReviewFinal_report.md`
