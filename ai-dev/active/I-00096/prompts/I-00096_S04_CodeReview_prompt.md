# I-00096_S04_CodeReview_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies. No alembic.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/reports/I-00096_S03_Backend_report.md`
- `orch/auto_merge_aggregator.py` (post-S03)
- `tests/unit/test_auto_merge_aggregator.py` (post-S03)

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Module-level constant** — `AUTO_MERGE_EVENT_PREFIXES` is defined
   as `("auto_merge_", "merge_auto_")` (in some order). Adding new
   prefixes here is the documented extension point.

2. **Default behaviour changes** — when `event_type_filter is None`
   AND `include_non_auto_merge is False`, the SQL has an
   `(event_type LIKE 'auto_merge_%' OR event_type LIKE 'merge_auto_%')`
   clause. Confirm via code read OR by enabling SQLAlchemy
   `echo=True` in a test.

3. **Explicit `event_type_filter` still takes precedence** — if a
   user passes `event_type_filter="step_launched"`, that filter is
   honoured even though `step_launched` doesn't match the prefix.
   Otherwise the existing chip filters break.

4. **`include_non_auto_merge=True` opt-out**: when set, no prefix
   filter is applied AT ALL. Confirm.

5. **Backwards-compat** — existing tests that call `list_recent_events`
   without the new param still pass; the test fixtures that previously
   set up `step_launched` events plus assertions on the count or first
   row may now legitimately fail because of the new default. Such
   tests need to be updated to pass `include_non_auto_merge=True` —
   verify S03 updated those callers OR explain why none needed
   updating.

6. **No raw string interpolation** — SQL is built via SQLAlchemy
   `or_()` + `like()`, NOT via f-strings. CRITICAL if not.

### TDD RED Evidence

Backend behavioural step — verify `tdd_red_evidence` shows
`AssertionError` with the actual offending event type. Reason:
pre-S03 the function returned `step_launched` rows in the default
query, so the test would have asserted False on `"step_launched" not in types`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00096",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
