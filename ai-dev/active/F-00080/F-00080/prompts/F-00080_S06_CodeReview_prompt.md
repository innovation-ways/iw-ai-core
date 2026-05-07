# F-00080_S06_CodeReview_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step Being Reviewed**: S05 (template-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status F-00080 --json`
- Design doc + S05 report + every page template touched in S05

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Page slug coverage (CRITICAL)
- Exactly 22 templates have `{% block page_help_slug %}<slug>{% endblock %}` declared (the list in S05's prompt).
- Pages explicitly out of scope (`dashboard.html`, `oss.html`, `item_execution_report.html`, detail variants of docs/research) do NOT have a help slug declared.
- Every declared slug matches an existing fragment file under `_partials/help/<slug>.html`.

### 2. Empty-state macro usage (HIGH)
- All 10 list views use `{{ empty_state(...) }}` from `templates/macros/empty_state.html` for their empty branch.
- The original empty-branch markup has been removed — no leftover dead HTML.
- Heading + body + primary CTA copy is concrete (not a placeholder), and matches the table in S05's prompt.
- Each `data-empty-state="<slug>"` attribute is present and matches the page slug.

### 3. data-tour attributes (HIGH)
- Every `data-tour="..."` attribute referenced in S03's `tours.js` has a matching DOM target in some page template.
- No spurious `data-tour` attributes on elements not referenced by any tour.

### 4. Inheritance / no-render-time-errors (HIGH)
- All edited pages still extend `base.html`.
- No new Tailwind classes introduced (broken toolchain in worktrees).
- No template renders to a broken page (smoke test in S07 catches this; flag any obvious typos here).

### 5. Convention checks (MEDIUM)
- `{% from "macros/empty_state.html" import empty_state %}` placed at top of each edited file.
- Existing imports preserved.
- No template indentation regressions.

## Test Verification

Run `make test-unit` and the smoke test from S03.

## Severity Levels

Standard scale.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "F-00080",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
