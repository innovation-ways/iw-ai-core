# I-00093_S05_CodeReview_Final_prompt

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No new migration files; no docker commands.

## Input Files

- `uv run iw item-status I-00093 --json`
- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `ai-dev/active/I-00093/I-00093_Functional.md`
- All `ai-dev/active/I-00093/reports/*.md`
- All files in S01/S03 `files_changed`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S05_CodeReview_Final_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Completeness vs Design**: AC1..AC6 each map to existing code +
   tests. Specifically:
   - AC1 message → S01 template change + S03 test
   - AC2 metadata JSON → S01 + S03
   - AC3 humanized heading → S01 + S03
   - AC4 verdict info → S01 + S03
   - AC5 diff section preserved → S01 (no removal); spot-verify
   - AC6 tests present
2. **Cross-Agent Consistency**: factory-set strings in S03's tests
   exactly match the field names the S01 template reads. e.g., a test
   that puts `event_metadata={"latency_ms": 412}` and asserts
   `assert "latency_ms" in html` — the template MUST render that key
   (it should, via `tojson(indent=2)`).
3. **Integration**: `auto_merge_event_detail` route returns 200 for
   every event_type rendered by the template; no `Internal Server
   Error` on event types that lack `metadata` or `message`.
4. **No regressions**: existing dashboard tests for the modal continue
   to pass.
5. **Security (XSS)**: `event.message` and `event.metadata` are
   auto-escaped. No `| safe` filter added. The
   `window.iwClipboard.copy(...)` `onclick` uses the `tojson | tojson`
   double-encode (or equivalent) so user-controlled metadata text
   cannot break out of the JS string literal.
6. **CSS additions**: new rules appended to `styles.css` as plain CSS,
   no Tailwind-only class names that won't appear in compiled output.
7. **clipboard.js usage**: the helper signature
   (`window.iwClipboard.copy(text, button)`) matches what S01 emits.
8. **Functional doc accurate**: matches what the user actually sees
   post-fix.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make allure-integration
```

Integration failure → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00093",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "missing_requirements": [],
  "notes": ""
}
```
