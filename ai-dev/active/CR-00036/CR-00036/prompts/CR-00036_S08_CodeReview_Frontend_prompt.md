# CR-00036_S08_CodeReview_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step Being Reviewed**: S07 (frontend-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S07_Frontend_report.md`
- All files listed in S07's `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S08_CodeReview_report.md`

## Context

You are reviewing the dashboard UI changes for CR-00036.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

`make lint` includes `make lint-js` (node --check on dashboard static JS). NEW violations → CRITICAL findings under `category: conventions`.

## Review Checklist

### 1. Macro and template integration

- `approve_merge_button` macro is imported at the top of `item_overview.html` and any other template that uses it.
- Branching order in `item_overview.html` puts `awaiting_approval` BEFORE the existing failed/merge_failed branch (otherwise the wrong button could render).
- Macro accepts `(project_id, item_id)` in the same order as sibling button macros.

### 2. htmx wiring

- Button posts to the exact URL S05 added: `/actions/item/{item_id}/approve-merge` (no double slashes, no leading `/api/`).
- Plan-tab toggle posts to the exact URL S05 added: `/project/{project_id}/api/batch/{batch_id}/auto-merge`.
- Both endpoints use the SSE refresh pattern (`hx-on::after-request="htmx.trigger(...)"`).
- The Plan-tab toggle is disabled exactly when the existing max-parallel select is disabled — same status set (`planning|approved|paused`).

### 3. Tailwind / CSS

- New utility classes appear in compiled CSS (run `make css` and verify the resulting `styles.css` includes them) OR plain CSS rules are appended to `dashboard/static/styles.css` per the I-00067 workaround.
- No dynamic class construction (string-concat in template) — that breaks JIT purging.

### 4. Status badge

- `awaiting_approval` value is recognized by the status badge component.
- Label is human-readable ("Awaiting approval" or similar). Title attribute explains the state.

### 5. Create-batch-from-selection form

- Pre-fills from the project's `auto_merge_default` (verify the template variable is populated by the route — read `S05` report to confirm).
- Hardcoded `True`/`checked` is a HIGH finding.

### 6. Tests

- `test_item_overview_awaiting_merge.py` covers both branches (approve button rendered for awaiting_approval; not rendered for other statuses).
- `test_batch_detail_auto_merge_toggle.py` covers enabled and disabled states.

### 7. Visual sanity check

- The S07 report should describe a manual screenshot/playwright session confirming the templates render. Missing this is a MEDIUM (fixable) finding.

## Test Verification

`make test-unit`, `make test-integration`, `make test-dashboard` MUST pass.

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | Wrong endpoint URL silently no-ops the action; branching order shows wrong button |
| HIGH | Hardcoded auto_merge default in form; macro placed in wrong file; missing import |
| MEDIUM (fixable) | Missing test, weak label text, no visual sanity check |
| LOW | Style nitpick |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
