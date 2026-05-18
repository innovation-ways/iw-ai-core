# I-00097_S04_CodeReview_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00097 --json`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/reports/I-00097_S03_Tests_report.md`
- `tests/dashboard/test_auto_merge_routes.py` (post-S03)

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)** — every test uses `client` and lives
   under `tests/dashboard/`.

2. **Semantic correctness (I003)**:
   - Zero-cost test asserts on `$0` (exact value extracted via regex),
     NOT just `"$0" in html`.
   - Linkification test asserts on the full `<a href=...>CR-00057</a>`
     pattern (with `/project/<id>/item/CR-00057` — singular `item`),
     NOT just `"CR-00057" in html`.
   - Plain-text test asserts the absence of the `/item/iw-ai-core`
     link, NOT just the absence of "iw-ai-core" (which would also
     fail because the value MUST appear in the table).

3. **Coverage**:
   - `test_token_cost_zero_renders_as_dollar_zero`
   - `test_token_cost_nonzero_keeps_precision`
   - `test_entity_id_renders_as_link_for_work_item_ids`
   - `test_entity_id_renders_plain_when_not_work_item_id`
   - `test_entity_id_renders_dash_when_null`

   Missing any → HIGH.

4. **Linkification test covers all three IW prefixes** — F-NNNNN,
   I-NNNNN, CR-NNNNN. A test that only covers CR- misses regressions
   on the other two. If S03 covered only CR-, that's MEDIUM (fixable)
   — add F- and I- cases (or use `pytest.mark.parametrize`).

5. **Targeted-run discipline**.

6. **CSS class assertions are attribute-scoped (I-00067)** — though
   this incident is unlikely to need any.

### TDD RED Evidence

Coverage step.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00097",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
