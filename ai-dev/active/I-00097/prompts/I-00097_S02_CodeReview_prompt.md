# I-00097_S02_CodeReview_prompt

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00097 --json`
- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- `ai-dev/active/I-00097/reports/I-00097_S01_Frontend_report.md`
- Touched templates

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S02_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Zero-cost formatting**:
   - `total_cost_usd == 0` renders `$0` (not `$0.00`, not `$0.000000`).
   - Non-zero values either keep full precision OR have trailing
     zeros trimmed (both are acceptable; just check it isn't broken).

2. **Linkification regex**:
   - Pattern is anchored: `^(F|I|CR)-\d{5}$` (or equivalent — must NOT
     match `iw-ai-core`, `CR-005`, `CR-000571` longer/shorter forms).
   - The regex is in a single helper (filter / test / macro), not
     duplicated in the template.

3. **URL pattern**:
   - The constructed href matches the actual route in the dashboard
     for item details. Verify with grep against the existing routes
     in `dashboard/routers/items.py` or similar.

4. **Null handling**:
   - `entity_id is None` → renders `—`.
   - `entity_id` is set but doesn't match the pattern → plain text.
   - `entity_id` matches the pattern → link.

5. **No new Tailwind classes that aren't in compiled CSS** —
   `text-primary` and `hover:underline` are safe (used elsewhere). If
   S01 added something obscure, verify it's compiled.

6. **No `| safe`** added — entity_id is auto-escaped.

7. **Jinja2 `format`-filter `%`-style** (I-00075).

8. **No tampering with the verdict column, message column, actions
   column, or filter row**.

### TDD RED Evidence

Frontend step — `tdd_red_evidence = "n/a — template-only polish"`.

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
  "work_item": "I-00097",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
