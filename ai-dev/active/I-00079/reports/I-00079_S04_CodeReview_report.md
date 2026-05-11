# I-00079 S04 — CodeReview Report (review of S03)

## What Was Reviewed

S03 (`tests-impl`) extended `tests/dashboard/test_empty_states.py` with 8 new test cases
across 2 new classes, targeting all acceptance criteria from the I-00079 design doc.

## Pre-Review Gates

| Gate | Result |
|------|--------|
| `make lint` | All checks passed (ruff + `scripts/check_templates.py`) |
| `make format` | All files already formatted |
| `uv run pytest tests/dashboard/test_empty_states.py -v` | **14 passed, 0 failed** |

No violations found. Coverage failure (19% < 46%) is pre-existing and unrelated.

## Review Checklist

### 1. Coverage vs the ACs

**AC1 (CTAs no longer 404)** — All 6 pages covered:

| Test | Page | Route |
|------|------|-------|
| `test_i00079_queue_empty_state_cta_resolves` | Queue (2 CTAs) | `/project/{id}/queue` |
| `test_i00079_history_empty_state_cta_resolves` | History | `/project/{id}/history` |
| `test_i00079_batches_empty_state_cta_resolves` | Batches | `/project/{id}/batches` |
| `test_i00079_all_active_empty_state_cta_resolves` | All Active | `/system/all-active` |
| `test_i00079_docs_library_empty_state_cta_resolves` | Docs Library | `/project/{id}/docs` |
| `test_i00079_research_library_empty_state_cta_resolves` | Research Library | `/project/{id}/research` |

Each test: (a) renders the page, (b) extracts `empty-state__cta-primary` hrefs via
attribute-scoped regex `<a href="..." class="empty-state__cta-primary"`, (c) asserts
`not href.startswith("/docs/")` and `".md" not in href.split("#")[0]` (the negative
invariants that make the test **fail against pre-fix code**), (d) issues `client.get()`
on the target and asserts `status_code == 200`, and (e) asserts the specific expected
destination (`startswith("/system/docs/IW_AI_Core_CLI_Spec")`, etc.).

**AC2 (regression test exists & fails pre-fix)** — Both structural guards present:

1. `test_i00079_no_legacy_docs_md_links_in_templates` — file-system scan across all
   `dashboard/templates/**/*.html`; checks for `primary_href="/docs/` and the regex
   `/docs/[A-Za-z0-9_./-]*\.md`; would fire if any developer reintroduced the broken form.
2. Each `TestEmptyStateHrefResolves` test carries the negative invariant assertions
   (`not href.startswith("/docs/")`, `".md" not in href.split("#")[0]`) that make the
   test fail against the pre-fix templates.

**AC3 (CTA targets agree with `help.py`'s `_SLUG_TO_DOC`)** — Covered by
`test_i00079_empty_state_cta_agrees_with_help_doc_map`, which asserts for
queue/history/batches/all_active: both the empty-state CTA and `_SLUG_TO_DOC[slug]`
start with `/system/docs/` and have no `.md` suffix.

### 2. Semantic Correctness (I003 lesson)

- **Attribute-scoped regex**: `_primary_hrefs()` uses
  `re.findall(r'<a\s+href="([^"]+)"\s+class="empty-state__cta-primary"', html)` —
  correctly keys on `class="empty-state__cta-primary"`, not bare substring `"IW_AI_Core_CLI_Spec"`
  (which could appear in the help-popover link) and not bare `"empty-state__cta-primary"`
  (which only proves the element exists).
- **Resolves-to-200 check**: each loop calls `client.get(target)` and asserts
  `followed.status_code == 200` — not merely "string looks plausible".
- **Negative invariants**: `not href.startswith("/docs/")` and `".md" not in href.split("#")[0]`
  are present in all 6 per-page tests. These are what make the test fail against pre-fix code.
- **No weakened assertions**: no `!= 404`, no `2xx`, no skipped pages.

### 3. Test Hygiene

- File location: `tests/dashboard/test_empty_states.py` ✓ (correct for `client`/`test_project` fixtures)
- No live-DB usage; no testcontainer needed for these tests (they use `db_session` via
  `app.dependency_overrides[get_db]` but don't hit the network)
- `encoding="utf-8"` on `filepath.read_text(encoding="utf-8")` in the template scan test ✓
- Existing `TestEmptyStateRendering` (6 tests) unchanged ✓
- Style consistent with the rest of the file ✓

### 4. Tests Actually Passed

```
tests/dashboard/test_empty_states.py::TestEmptyStateRendering (6 tests)        — PASSED
tests/dashboard/test_empty_states.py::TestEmptyStateHrefResolves (6 tests)    — PASSED
tests/dashboard/test_empty_states.py::TestI00079RegressionPrevention (2 tests) — PASSED
Total: 14 passed, 0 failed
```

S03's reported results match exactly.

### 5. Security

- No hardcoded secrets/URLs/ports in the changed file ✓

## Verdict

**PASS** — zero CRITICAL, zero HIGH, zero MEDIUM (fixable) findings.

---

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00079",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "14 passed, 0 failed",
  "notes": "All ACs covered; attribute-scoped regex correctly applied; negative invariants present; templates-wide regression scan present; AC3 consistency test present; S03 report is accurate."
}
```