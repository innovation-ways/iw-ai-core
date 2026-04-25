# I-00039_S05_CodeReview_Final_prompt

**Work Item**: I-00039 -- Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

Standard rule. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Not relevant — no DB/migration work in this incident.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00039/I-00039_Issue_Design.md` — design document
- All step reports under `ai-dev/active/I-00039/reports/`:
  - `I-00039_S01_Frontend_report.md`
  - `I-00039_S02_CodeReview_report.md`
  - `I-00039_S03_Tests_report.md`
  - `I-00039_S04_CodeReview_report.md`
- All files listed in S01 and S03 `files_changed`:
  - `dashboard/templates/pages/project/jobs.html`
  - `dashboard/templates/fragments/jobs_table.html`
  - `dashboard/templates/components/multi_select.html`
  - `dashboard/static/multi_select.js`
  - `dashboard/static/styles.css`
  - `tests/dashboard/test_jobs_filter_ui.py`

## Output Files

- `ai-dev/active/I-00039/reports/I-00039_S05_CodeReview_Final_report.md`

## Context

You are performing the final cross-step review of all implementation work
for I-00039. Per-step reviews (S02, S04) have already been done; your job is
to catch cross-cutting issues they could not.

This is a small, focused incident: pure-frontend refactor (delete colour
chips, replace filter checkboxes with dropdown) plus tests. There are no
multi-agent integration concerns in the traditional sense, but you should
still verify:

- The implementation in S01 actually satisfies all four ACs from the design.
- The tests in S03 actually exercise all four ACs, not a subset.
- The whole thing reads coherently — no orphan files, no leftovers, no
  inconsistencies between what the design promised and what shipped.

## Review Checklist

### 1. Acceptance Criteria coverage map (CRITICAL)

For each AC in the design document, identify the implementing code AND the
corresponding test:

| AC | Implementation | Test | Status |
|----|----------------|------|--------|
| AC1 (Type plain text) | `dashboard/templates/fragments/jobs_table.html` line ? | `test_jobs_type_cell_is_plain_text_no_color_chip` | pass/fail |
| AC2 (Multi-select dropdowns) | `dashboard/templates/components/multi_select.html` + `dashboard/static/multi_select.js` + edits to `jobs.html` | `test_jobs_filter_uses_multiselect_dropdown_not_checkbox_groups` | pass/fail |
| AC3 (Regression test exists) | — | The whole new test file | pass/fail |
| AC4 (No regressions) | — | Existing `tests/integration/test_jobs_api.py` still green + qv-browser V4 (next step) | pass/fail |

Any AC without code AND a test is a CRITICAL `missing_requirements` finding.

### 2. No leftover `type_chip` references

Run:
```bash
grep -rn 'type_chip' dashboard/ tests/
```

Must return zero matches. Any match is a HIGH finding.

### 3. No leftover legacy color classes

Run:
```bash
grep -rEn 'bg-(blue|purple|orange|teal|emerald)-100' dashboard/templates/
```

Match the result against legitimate uses (e.g. status badges may use these
colours — check `dashboard/templates/components/status_badge.html`). Any new
or remaining match in the Type-cell rendering path is a HIGH finding.

### 4. Query-string contract preserved end-to-end

Verify by reading the code path:

- `dashboard/templates/components/multi_select.html` emits checkboxes with
  `name="{{ name }}"`.
- `dashboard/templates/pages/project/jobs.html` calls
  `multi_select("type", ...)` and `multi_select("status", ...)` inside the
  same `<form method="get">` that wraps the date inputs and Filter button.
- Submitting the form produces `?type=A&type=B&status=X&date_from=&date_to=`.
- `dashboard/routers/jobs_ui.py` accepts `type: list[str] = Query(...)` —
  unchanged.

If any link in this chain is broken, the filter is silently broken. CRITICAL.

### 5. Scope discipline

- No Python files under `orch/` or `dashboard/routers/` were modified
  (verify via `git diff --stat`).
- No new dependencies added (`pyproject.toml`, `uv.lock`,
  `package.json` — none of these should appear in the diff).
- No fragment template extended `base.html` (per `dashboard/CLAUDE.md`).

### 6. Tailwind CSS regenerated

`dashboard/static/styles.css` should be in S01's `files_changed` and
should contain any new utility classes used by `multi_select.html`. If new
classes were added but `make css` was not run, the live UI will silently
miss styling. Verify the diff includes `styles.css` changes.

### 7. Cross-step consistency

- Test file uses the same `data-multi-select="..."` markers that
  `multi_select.html` emits — names match exactly.
- Test file's "legacy color classes" tuple matches the classes that
  `type_chip` used to emit (`bg-blue-100`, `bg-purple-100`,
  `bg-orange-100`, `bg-teal-100`, `bg-emerald-100`).

### 8. Architecture compliance

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`.
- Templates only — no business logic moved into views.
- Vanilla JS only — no React, no jQuery, no module bundler additions.

### 9. Security (cross-cutting)

- No secrets, hardcoded URLs, or credentials added.
- Input validation: the form values land back on the FastAPI route which
  already validates via Pydantic / `JobType()` enum coercion at
  `dashboard/routers/jobs_ui.py:47,117`. Confirm no new injection point was
  introduced (the new `multi_select.js` does not write user input into the
  DOM unsanitised — it only toggles `hidden` and updates an integer counter).

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite**:
   ```bash
   make test-unit
   ```
   Must pass.
2. Run lint, format, typecheck:
   ```bash
   make lint
   uv run ruff format --check .
   make typecheck
   ```
   All must pass.
3. Report test results accurately.

If unit tests fail, that is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Missing AC implementation, query contract broken, lint/test fail, scope violation | Must fix before merge |
| HIGH | Leftover `type_chip` references, leftover legacy colour class on Type cell, broken integration | Must fix before merge |
| MEDIUM (fixable) | CSS not regenerated, missing aria attributes, brittle test | Should fix in fix cycle |
| MEDIUM (suggestion) | Refactor opportunity, better pattern available | Optional |
| LOW | Style preferences, naming nits | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00039",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint pass, format pass, typecheck pass, X unit pass, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
