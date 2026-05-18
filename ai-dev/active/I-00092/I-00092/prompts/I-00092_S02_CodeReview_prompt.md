# I-00092_S02_CodeReview_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00092 --json`
- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `ai-dev/active/I-00092/reports/I-00092_S01_Frontend_report.md`
- `dashboard/templates/fragments/auto_merge_events_table.html` (post-S01)

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any new violation → CRITICAL with `category: conventions`.

## Review Checklist

1. **Comparison logic** — `_is_active` correctly compares `type_filter`
   to `mapped`, NOT to `key`. The `all` chip's special case (no `type`
   param) is preserved.
2. **Attributes** — every chip carries `title="<full event_type or
   'all event types'>"` and `aria-pressed="{true|false}"`. The active
   chip has `aria-pressed="true"`; exactly one chip is active per
   render.
3. **No regression** — labels, URLs, layout, pagination, and the events
   table itself are unchanged.
4. **Jinja2 `format` filter discipline** — any `format` call uses
   `%`-style (I-00075). (S01 likely added no such call; verify by grep.)
5. **Class names** — only existing Tailwind classes are used (so JIT
   purge doesn't drop them). No new class names.
6. **No new `<script>` blocks** in templates.
7. **Test placement** — S01 should not have added tests; those belong
   in S03.

### TDD RED Evidence

Frontend step — `tdd_red_evidence` should read `n/a — template-only
edit`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard (CRITICAL/HIGH/MEDIUM_FIXABLE/MEDIUM_SUGGESTION/LOW).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00092",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
