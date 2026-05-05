# I-00067_S04_CodeReview_Tests_prompt

**Work Item**: I-00067 -- Recent Activity messages need truncation + click-to-expand popup
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00067 --json` — runtime step state
- `ai-dev/active/I-00067/I-00067_Issue_Design.md` — Design document
- `ai-dev/active/I-00067/reports/I-00067_S03_Tests_report.md` — S03 report
- `tests/integration/test_i00067_recent_activity_truncation.py` — Tests added in S03
- `tests/integration/test_dashboard_pages.py` — existing dashboard tests for comparison
- `tests/conftest.py` and `tests/CLAUDE.md` — fixture conventions

## Output Files

- `ai-dev/active/I-00067/reports/I-00067_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

Report new violations as CRITICAL findings with `category: conventions`.

## Review Checklist

### 1. Falsifiability

For EACH test, verify it would fail against the pre-fix template (single inline `<span>` rendering full message). For example:
- `test_long_message_is_truncated_to_100_chars_with_dots` — would FAIL on `main` because the pre-fix template emits the full 200-char string inline; the test asserts `"x" * 100 + "..."` is present, which would NOT appear pre-fix.
- `test_message_at_exactly_101_chars_is_truncated` — would FAIL on `main`; same reasoning.
- `test_short_message_renders_verbatim_with_no_dots` — would PASS on `main` too (short messages always render verbatim). This test guards REGRESSION: the fix must not start adding `...` to short messages. Document this in the review notes (it's not failing on main, but it's still valuable).

If any test would pass against the pre-fix code AND its purpose is reproduction (not regression-prevention), flag as CRITICAL.

### 2. Semantic correctness, not shape

- Tests assert SPECIFIC values, not just presence of keys/substrings. Examples that should be present:
  - `assert "x" * 100 + "..." in html`
  - `assert "x" * 101 + "..." not in html`
  - `assert 'data-full-text="' + ("x" * 200) + '"' in html` (or equivalent)
- Flag any `assert "..." in html` (without the surrounding context) — that's shape-checking and would pass even on the empty-state line "View all batches.".
- Flag any `assert len(rows) > 0` style checks that don't bind specific rows to specific expected content.

### 3. Boundary cases

The suite must include at least one test EACH for:
- `len == 100` (no truncation)
- `len == 101` (truncated)
- `len == 200` (truncated, full payload available)
- `len < 100` (no truncation)
- empty / `None` message (falls back to event_type)

### 4. Escape safety test

There must be an HTML-injection test asserting unescaped `<script>` is NOT present and the escaped form IS present in both the preview and the payload.

### 5. No-regression entity link test

There must be a test asserting that `entity_type=batch|doc_job|work_item` rows still render the correct route URLs.

### 6. Test isolation and conventions

- Tests use the testcontainer-backed fixtures (no live DB).
- Tests don't share state in ways that would cause order-dependence.
- Test names start with `test_` and clearly describe the behaviour.
- No mocks for the database.
- Read `tests/CLAUDE.md` for additional rules.

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration`. All tests must pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

Same shape as `S02`. `verdict: "pass"` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
