# I-00115_S04_CodeReview_Tests_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy — no docker mutations, testcontainer fixtures exempt.

## ⛔ Migrations: agents generate, daemon applies

This item touches NO migrations. CRITICAL if any alembic file appears in S03's `files_changed`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00115 --json`
- `ai-dev/active/I-00115/I-00115_Issue_Design.md` — design document (READ FIRST, especially `## Test to Reproduce` and `## Acceptance Criteria`)
- `ai-dev/active/I-00115/reports/I-00115_S03_Tests_report.md` — S03 implementation report
- `tests/dashboard/test_scope_amend_modal_i00115.py` — the new test file
- Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` for the assertion-strength rules

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_S04_CodeReview_report.md` — review report

## Context

S03 (tests-impl) wrote five tests for I-00115. You are reviewing those tests. The bar is high: shape-only assertions are the failure mode this review must catch (see "I003 Lesson" reminder below).

Read the design document's `## Test to Reproduce` section first — it names the exact assertions that must be present.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Both must report zero NEW violations on the new test file. CRITICAL if either fails.

## Scope Discipline

S03's `files_changed` MUST contain only `tests/dashboard/test_scope_amend_modal_i00115.py`. Anything else is scope creep — CRITICAL. (Implicit allowances for `ai-dev/active/I-00115/**` still apply.)

## Review Checklist

### 1. Five tests are present, named correctly, and each maps to a design-doc assertion

| Required test name (or close equivalent) | Maps to |
|---|---|
| `test_i00115_modal_submit_form_wires_cleanup_hook` | Defect 1 — submit teardown |
| `test_i00115_modal_close_button_uses_getelementbyid_for_overlay` | Defect 2 — broken `this.closest()` |
| `test_i00115_modal_esc_key_dismisses` | New UX — ESC dismissal |
| `test_i00115_modal_backdrop_click_dismisses` | New UX — backdrop click dismissal |
| `test_i00115_cancel_button_still_works` | Regression guard |

If any is missing, CRITICAL.

### 2. Semantic correctness (CRITICAL: I003 Lesson)

For EVERY assertion in EVERY test, apply the mutation question: **if I deleted the fix line in the template, would this assertion fail?**

Shape-only patterns to flag (any one = HIGH at minimum, CRITICAL if multiple):

- `assert "scope-amend" in html` — substring match against the modal's own ID which always exists, false positives.
- `assert html.count(...) > 0` without checking specific occurrence content.
- `assert "overlay" in html` — too loose; the overlay always renders.
- `assert "Escape" in html` alone — could match the literal text in unrelated context.

Strong patterns to verify:

- `assert "this.closest('#scope-amend-overlay')" not in html` — verifies the SPECIFIC broken pattern is gone. CRITICAL strong.
- Form open-tag asserted to contain BOTH IDs (not just one).
- Cancel button assertion targets the specific button (e.g. by text content or surrounding markup), not arbitrary template text.

### 3. RED-evidence reasoning is plausible

The `tdd_red_evidence` field in S03's report must explain, per test, why the assertion would fail against pre-fix HEAD. Cross-check by reading the pre-fix template (git log / diff against the S01 commit). If the reasoning is "would fail" but the pre-fix template clearly already satisfies the assertion, that is a HIGH finding (the test wouldn't actually have caught the bug).

### 4. No `git stash` / `git checkout HEAD~1 -- ...` in the test code

Per the iw-new-incident skill rule: a manual revert RED-check inside this step is forbidden. If S03's report references `git stash` or `git checkout HEAD~1` operations on source files during the step, MEDIUM (fixable).

### 5. Test isolation

- File-local `client` fixture (no shared `client` in conftest).
- `db_session` fixture used via `tests/dashboard/conftest.py` re-export.
- No `importlib.reload(orch.config)`.
- No mocked DB.
- No live-DB connection (no port 5433).

### 6. Targeted-only test verification

S03's report MUST show that it ran ONLY `pytest tests/dashboard/test_scope_amend_modal_i00115.py -v`, NOT `make test-integration` or `make test-unit`. If S03 ran the full suite, MEDIUM (fixable) — the I-00073 budget rule was violated.

### 7. Test name → behaviour clarity

Each test name should make the assertion's purpose obvious to a reader who doesn't open the file. If a name is `test_modal_works` or `test_cleanup`, LOW.

## Test Verification

```bash
uv run pytest tests/dashboard/test_scope_amend_modal_i00115.py -v
```

All 5 must pass against the post-S01 template.

## Severity Levels

| Severity | Action Required |
|----------|-----------------|
| CRITICAL | Must fix before merge |
| HIGH | Must fix before merge |
| MEDIUM (fixable) | Should fix in fix cycle |
| MEDIUM (suggestion) | Optional |
| LOW | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00115",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "notes": ""
}
```
