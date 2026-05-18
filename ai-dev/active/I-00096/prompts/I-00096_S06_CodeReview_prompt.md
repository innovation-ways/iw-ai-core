# I-00096_S06_CodeReview_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/reports/I-00096_S05_Api_report.md`
- `dashboard/routers/auto_merge_ui.py` (post-S05)

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S06_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Bool coercion** — FastAPI `bool = Query(default=False)` accepts
   `?all=1`, `?all=true`, `?all=on`. Verify.

2. **Forwarded** — `include_non_auto_merge=all` is passed to the
   aggregator.

3. **Template context** — `show_all` (or equivalent key) is added to
   the fragment context so S01's template can read it directly rather
   than re-parsing `request.query_params`.

4. **No regression on other route handlers**.

5. **`noqa: A002`** on the `all` parameter shadowing the builtin.

### TDD RED Evidence

API step — `tdd_red_evidence = "n/a — API surface extension"`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00096",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
