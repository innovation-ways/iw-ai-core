# I-00096_S08_CodeReview_prompt

**Work Item**: I-00096 — Auto-merge view duplicates the status chip and "all" filter shows non-auto-merge events
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- `uv run iw item-status I-00096 --json`
- `ai-dev/active/I-00096/I-00096_Issue_Design.md`
- `ai-dev/active/I-00096/reports/I-00096_S07_Tests_report.md`
- `tests/unit/test_auto_merge_aggregator.py`, `tests/dashboard/test_auto_merge_routes.py`

## Output Files

- `ai-dev/active/I-00096/reports/I-00096_S08_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

## Review Checklist

1. **Test placement (I-00067)** — unit / dashboard split correct.
2. **Semantic correctness (I003)** — chip-count assertion uses
   `.count(...) == 1`, not just `"chip" in html`. Default-filter
   tests assert specific event-type strings (`"step_launched"`,
   `"auto_merge_health_probe"`) that uniquely identify rows.
3. **Coverage** — all six named tests from the design:
   - `test_list_recent_events_default_excludes_non_auto_merge`
   - `test_list_recent_events_include_non_auto_merge_shows_everything`
   - `test_list_recent_events_explicit_event_type_filter_overrides_prefix_default`
   - `test_auto_merge_page_renders_exactly_one_chip`
   - `test_topbar_chip_appears_on_non_auto_merge_page`
   - `test_default_events_view_excludes_non_auto_merge`
   - `test_show_all_toggle_includes_non_auto_merge_events`
   - `test_show_all_toggle_button_renders_with_correct_aria_pressed`
   Missing any → HIGH.
4. **Topbar-on-other-page test guards the over-fix scenario** — if a
   future change accidentally suppresses the chip everywhere, this
   test fails.
5. **CSS class assertions are attribute-scoped (I-00067)**.
6. **Targeted-run discipline**.

### TDD RED Evidence

Coverage step.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_auto_merge_aggregator.py tests/dashboard/test_auto_merge_routes.py -v
```

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "I-00096",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
