# I-00039_S02_CodeReview_prompt

**Work Item**: I-00039 -- Jobs page — drop color-coded Type chips and replace filter checkboxes with multi-select dropdowns
**Step Being Reviewed**: S01 (Frontend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard rule. See `docs/IW_AI_Core_Agent_Constraints.md`. Read-only docker
introspection is allowed; nothing in this review requires it.

## ⛔ Migrations: agents generate, daemon applies

Not relevant — S01 is a pure frontend change with no DB or alembic touches.
Verify that no Python files outside `dashboard/templates/` and
`dashboard/static/` were modified; if any were, that is a CRITICAL scope
violation.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00039/I-00039_Issue_Design.md` — design document
- `ai-dev/active/I-00039/reports/I-00039_S01_Frontend_report.md` — S01 report
- All files listed in S01's `files_changed`:
  - `dashboard/templates/pages/project/jobs.html`
  - `dashboard/templates/fragments/jobs_table.html`
  - `dashboard/templates/components/multi_select.html`
  - `dashboard/static/multi_select.js`
  - `dashboard/static/styles.css`
- `dashboard/CLAUDE.md` and project `CLAUDE.md`
- The pre-fix evidence at `ai-dev/active/I-00039/evidences/pre/`

## Output Files

- `ai-dev/active/I-00039/reports/I-00039_S02_CodeReview_report.md` — review

## Context

You are reviewing the frontend implementation done in S01. The change is
visual-only: remove `type_chip` colour coding from the Type column, and
replace flat checkbox filters for Type and Status with a single reusable
multi-select dropdown component. The query-string contract MUST be
unchanged. No Python files should have been touched.

## Review Checklist

### 1. Architecture / Scope Compliance

- **Scope adherence**: ONLY templates and static assets should have changed.
  Files outside `dashboard/templates/` and `dashboard/static/` (especially
  any `*.py`) being modified is a CRITICAL finding.
- **No new dependencies**: `package.json`, `pyproject.toml`, `uv.lock` should
  be untouched. The dropdown is implemented in vanilla JS — no new packages.
- **Query-string contract preserved**: Form `<form method="get">` and the
  field `name` attributes MUST still produce repeated `?type=A&type=B&status=X`
  pairs. Confirm by reading the rendered macro.
- **Fragment rule**: `fragments/jobs_table.html` MUST NOT extend `base.html`
  (per `dashboard/CLAUDE.md`).

### 2. Both `type_chip` macros deleted

Verify the macro has been DELETED from BOTH:

- `dashboard/templates/pages/project/jobs.html` (lines 21–32 in the pre-fix file)
- `dashboard/templates/fragments/jobs_table.html` (lines 21–32 in the pre-fix file)

`grep -n 'type_chip' dashboard/templates/` must return zero matches.

### 3. Type cell renders as plain text

- The Type cell in `jobs_table.html` must NOT wrap the value in a `<span>`
  with `bg-*` / `text-*-700` / `rounded-sm` chip styling.
- The Type cell text colour must match the Title cell's text colour
  (compare in the same file).
- `grep -E 'bg-(blue|purple|orange|teal|emerald)-100' dashboard/templates/`
  should return zero matches anywhere related to the Type column.

### 4. multi_select component quality

- `dashboard/templates/components/multi_select.html` exports a Jinja macro
  with the signature documented in the S01 prompt.
- The macro emits `data-multi-select="{name}"` on the wrapper and
  `data-multi-select-panel="{name}"` on the panel — Tests step (S03) asserts
  on these.
- The button has `aria-haspopup="listbox"` and `aria-expanded="false"`.
- Checkboxes inside the panel use `name="{{ name }}"` so the form
  submission produces repeated query params.
- Visual style of the button matches existing dashboard buttons (look at the
  Filter button in `pages/project/jobs.html` for reference).

### 5. multi_select.js quality

- Pure vanilla JS, no jQuery, no framework imports.
- Uses `addEventListener`, `querySelectorAll`, etc. — modern DOM APIs.
- Handles: click toggle, outside-click close, Escape close, label update on
  checkbox change, initial label on DOMContentLoaded based on pre-checked count.
- File is small (target ~50 lines or less). If much larger, flag as
  MEDIUM_SUGGESTION asking why.
- `node --check dashboard/static/multi_select.js` should pass (this is what
  `make lint` runs on dashboard JS — see `CLAUDE.md`).
- No console.log / debugger left in.

### 6. Accessibility

- Dropdown button is keyboard-focusable (default for `<button>`).
- Panel is keyboard-navigable (checkboxes are focusable by default).
- Escape closes the panel AND returns focus to the button.
- The panel has `role="listbox"` or equivalent, OR there is an explanation
  in the S01 report for why a different ARIA pattern was chosen.

### 7. Tailwind CSS regenerated

- `dashboard/static/styles.css` must be in `files_changed` if any new
  utility classes were used.
- `make css` must have been run by the agent.

### 8. No regression on other rendered elements

- Status badges, sort headers, row links, pagination, date inputs, Filter
  and Clear buttons — confirm by reading the diff of `jobs.html` and
  `jobs_table.html` that nothing else was incidentally changed.

### 9. No console errors expected

- Read `multi_select.js` carefully for any path that throws (null deref,
  missing element). Defensive checks expected for the case where the script
  loads on a page without any `[data-multi-select]` element.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make lint` — must pass.
2. Run `uv run ruff format --check .` — must pass.
3. Run `make typecheck` — must pass (no Python touched, but verify no
   incidental damage).
4. Run `make test-unit` — must pass (no regressions).

If any of these fail, that is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| CRITICAL | Files outside templates/static modified, query contract broken, lint/test failures | Must fix before merge |
| HIGH | `type_chip` not fully removed, missing `data-multi-select` attribute, accessibility broken | Must fix before merge |
| MEDIUM (fixable) | Style mismatch with existing buttons, missing Escape handler, JS exceeds ~80 lines | Should fix in fix cycle |
| MEDIUM (suggestion) | Better ARIA pattern available, dropdown could close on Tab | Optional |
| LOW | Minor readability, naming nits | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00039",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "lint pass, format pass, typecheck pass, X unit pass, 0 failed",
  "notes": ""
}
```
