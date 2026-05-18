# I-00093_S02_CodeReview_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00093 --json`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `ai-dev/active/I-00093/reports/I-00093_S01_Frontend_report.md`
- Touched files in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

Any new violation in S01's touched files → CRITICAL.

## Review Checklist

1. **Heading humanized** — `<h3 id="auto-merge-event-title">` no longer
   reads `Event #<id>` alone; contains `event.event_type` AND the
   formatted timestamp. AC3 covered.
2. **Message renders** — `event.message` appears in the template
   conditionally on `{% if event.message %}`. AC1 covered.
3. **Metadata renders as pretty-printed JSON** — uses
   `event.metadata | tojson(indent=2)` inside a `<pre>` inside a
   `<details>`. Adjacent "Copy as JSON" button uses
   `window.iwClipboard.copy(...)` (NOT `navigator.clipboard.writeText`).
4. **entity_type renders** — verify the chosen approach (extended
   EventRow vs raw event passing) is consistent with the route handler
   change.
5. **Verdict block** — renders for ANY event with `verdict` set, not
   just resolved. AC4 covered.
6. **Diffs section preserved** — the existing `difflib.HtmlDiff` table
   still renders for `merge_auto_resolved` events with `llm_calls`.
   AC5.
7. **Existing verdict form preserved** — for resolved events.
8. **CSS appended to styles.css** — plain CSS only; new class names
   prefixed `auto-merge-modal__`. No `<style>` blocks in the template.
9. **No new `<script>` blocks** — relies on the existing
   `clipboard.js`.
10. **Jinja2 `format` filter discipline** — `%`-style only (I-00075).
11. **Auto-escaping** — `{{ event.message }}` and `{{ event.metadata | tojson }}`
    both pass through Jinja2 auto-escape. NO `| safe` filter added.
12. **Inline JSON in `onclick`** — using `tojson | tojson` (or
    equivalent) to safely embed the metadata string as a JS string
    literal. A single `tojson` outputs JSON which is NOT a valid JS
    expression once the metadata contains quotes; the double encode is
    necessary. If S01 used `| safe` here instead, that is a HIGH
    finding (XSS risk via metadata text).
13. **No `<details>` open-state inconsistency** — small payloads
    expand, large ones collapse; the threshold rule is sane (e.g.,
    `<400 chars`).

### TDD RED Evidence

Frontend step — `tdd_red_evidence = "n/a — template + minor route
context-extension"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00093",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
