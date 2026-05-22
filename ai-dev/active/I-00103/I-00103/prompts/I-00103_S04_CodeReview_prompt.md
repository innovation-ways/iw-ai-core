# I00103_S04_CodeReview_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00103/reports/I-00103_S03_Frontend_report.md` -- S03 report.
- All files listed in S03's `files_changed` (expected: `dashboard/templates/fragments/auto_merge_event_detail.html`; possibly also `dashboard/static/styles.css`).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S04_CodeReview_report.md` -- Review report.

## Context

S03 added a "Per-file errors" section to the auto-merge event-detail modal. Verify the template change is correct, accessible, conventional, and degrades gracefully for historical events.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC3 (renders when present), AC4 (hides when absent / empty).
- `## TDD Approach` — note the test file `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py` and the I-00067 CSS-assertion lesson: tests should use **attribute-scoped** assertions like `'class="auto-merge-modal__per-file-error"'`, not bare substring. Your job in this review is NOT to grade S05's tests, but to confirm that S03's template uses class names that can be asserted on safely.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint     # includes scripts/check_templates.py
make format
```

If either reports NEW violations in the changed files, classify as CRITICAL findings.

## Review Checklist

### 1. Conditional rendering

- Is the section guarded by both `event.metadata is not None` AND `per_file_errors` being non-empty? Either guard alone is insufficient.
- Is the guard expressed in idiomatic Jinja2 — e.g. `{% set ... %}` + `{% if per_file_errors %}` — without raising on missing keys?
- Does an event without the field render with HTTP 200 and no template exception? You can spot-check by mentally walking the Jinja2 expressions against a metadata dict like `{"phase": 1, "abstained_files": [], "error_files": ["x"], ...}` (the historical shape from event 80689).

### 2. Faithful error rendering

- Is the error text wrapped in `<pre>` or has `white-space: pre-wrap` so newlines render? If not, multi-line stderr will mush together.
- Is `{{ entry.error }}` used directly (relying on Jinja2 autoescape)? Use of `| safe` on user/error text is a CRITICAL finding.

### 3. Class-name discoverability for tests

- Does the new section have a unique class name (e.g. `auto-merge-modal__per-file-errors`) that the dashboard test can pin via attribute-scoped assertion `'class="auto-merge-modal__per-file-errors"'`? Class names that collide with existing utility classes (e.g. plain `.error`) are a HIGH finding because they prevent reliable test pinning.

### 4. No collateral changes

- Existing message paragraph, metadata `<details>` block, and modal `<dl>` MUST render identically. Any reflow / reordering / wording change to existing elements is a HIGH finding (scope creep).

### 5. CSS additions (if any)

- If S03 modified `dashboard/static/styles.css`, the rules MUST be additive (new rules appended at the bottom), not modifications to existing rules. Project policy (`CLAUDE.md`): "MUST append plain CSS rules directly to dashboard/static/styles.css".
- New rules should be minimal — margin / padding / spacing. Any colour-system changes are a HIGH finding (out of scope for an observability fix).

### 6. Project conventions

- Match existing fragment's `<dl>`/`<dt>`/`<dd>` pattern.
- Tailwind utility classes used in the rest of the fragment (`text-muted-foreground`, `font-mono`) should be reused for consistency.
- I-00075 lesson: any `format`-filter call MUST be `%`-style, not `str.format`-style. (Unlikely to apply to this fix, but worth a glance.)

### 7. Security

- Free-form error strings can contain stderr text including stack traces. Confirm no `| safe` filter on `entry.error`. Confirm no `innerHTML`-style injection patterns. (The fragment is server-rendered Jinja2 with autoescape on, so this should be safe by default; flag any deviation.)

### 8. Accessibility

- `<h4>` for the section heading matches the existing fragment's heading rank.
- Semantic markup: `<dl>` for key/value pairs, `<pre>` for the error block. Avoid `<div>`-only soup.

## Test Verification (NON-NEGOTIABLE)

Run the existing dashboard route tests to confirm no regression:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v 2>&1 | tail -30
```

Report results accurately.

## Severity Levels

(Standard table — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.)

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00103",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
