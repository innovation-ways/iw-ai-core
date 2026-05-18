# I-00092_S04_CodeReview_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies — `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00092 --json`
- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `ai-dev/active/I-00092/reports/I-00092_S03_Tests_report.md`
- `tests/dashboard/test_auto_merge_routes.py` (post-S03)
- `tests/CLAUDE.md`, `skills/iw-ai-core-testing/SKILL.md`

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)** — every new test that uses `client` is
   under `tests/dashboard/`. CRITICAL otherwise.
2. **Semantic correctness over shape (I003)** — every assertion targets
   a specific value, not just substring presence. Particular smells to
   flag:
   - `assert "bg-primary" in html` without attribute scoping → HIGH
   - `assert "resolved" in html` → HIGH (the word also appears in the
     event type column)
   - `assert response.status_code == 200` as only assertion → CRITICAL
3. **Coverage** — at minimum:
   - `test_filter_chip_resolved_is_highlighted_when_active`
   - `test_filter_chip_all_is_highlighted_when_no_type_param`
   - `test_filter_chip_title_tooltips_match_event_types`
   Missing any → HIGH.
4. **Helper isolation** — `_extract_filter_chip_blocks` (or similar)
   raises if not all 7 chips found, so a future template refactor that
   drops a chip surfaces as a clear failure.
5. **Attribute-scoped CSS class assertions (I-00067)** —
   `re.search(r'class\s*=\s*"[^"]*\bbg-primary\b[^"]*"', chip)` or
   equivalent, not bare substring.
6. **Targeted-run discipline** — `tests_passed` reflects ONLY the
   touched test file's run, NOT `make test-unit` /
   `make test-integration` (which are S10 / S11 QV gates).

### TDD RED Evidence

Coverage step (`tests-impl`) — expected to read `n/a — coverage step
(tests-impl)`.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Missing named tests in the collection list → CRITICAL.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00092",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
