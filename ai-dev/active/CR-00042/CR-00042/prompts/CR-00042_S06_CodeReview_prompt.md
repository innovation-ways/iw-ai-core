# CR-00042_S06_CodeReview_prompt

**Work Item**: CR-00042 — Fix Broken "Open full docs" Links in Help Popups
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/CR-00042/CR-00042_CR_Design.md` — TDD Approach section, AC1–AC5
- `tests/dashboard/test_system_docs_route.py` — new tests
- `tests/dashboard/test_help_router.py` — updated tests
- `ai-dev/active/CR-00042/reports/CR-00042_S05_tests-impl_report.md` — S05 report

## Output Files

- `ai-dev/active/CR-00042/reports/CR-00042_S06_code_review_report.md` — findings with severities

## Review Checklist

### Critical checks

- [ ] T2 (unknown slug → 404) is present and tests the actual route (not just import)
- [ ] T3 (traversal) tests path segments with `.`, `/`, `%` — at minimum `../etc/passwd` and `foo/bar`
- [ ] T5 asserts all `_SLUG_TO_DOC` values start with `/system/docs/` (not `/docs/`)
- [ ] T6 covers all 22 expected slugs and the assertion is `assert not missing`
- [ ] `test_help_fragment_docs_link_points_to_system_docs` asserts presence of `href="/system/docs/` AND absence of `href="/docs/` and `href="/orch/` — the negative checks MUST be anchored to the `href="` prefix (a bare `"/docs/IW_AI_Core"` substring check is wrong: it matches the *valid* new path `/system/docs/IW_AI_Core_...`)

### High checks

- [ ] T1 asserts rendered HTML (presence of `<h`) not raw markdown (absence of raw `#` headings)
- [ ] T4 asserts `id="` is present (toc extension generating heading IDs)
- [ ] Tests use the project's test client fixture from `tests/conftest.py` (not a custom client)
- [ ] Parametrize on multiple slugs in `test_help_fragment_docs_link_points_to_system_docs`

### Medium checks

- [ ] Test names follow the project's naming convention (read `tests/CLAUDE.md`)
- [ ] No test imports `dashboard.app` directly if the client fixture handles setup

### Low checks

- [ ] No hardcoded port numbers in test URLs
- [ ] `EXPECTED_SLUGS` constant is defined at module level (not inside the test)

## Severity Guide

- **CRITICAL**: Missing traversal test; `_SLUG_TO_DOC` coverage test missing; old broken paths not asserted absent
- **HIGH**: T1 doesn't distinguish rendered HTML from raw markdown; no toc test; wrong fixture
- **MEDIUM**: Naming convention violation; import style
- **LOW**: Code style issues

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00042",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00042/reports/CR-00042_S06_code_review_report.md"
  ],
  "blockers": [],
  "notes": ""
}
```
