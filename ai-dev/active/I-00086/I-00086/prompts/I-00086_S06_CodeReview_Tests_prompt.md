# I-00086_S06_CodeReview_Tests_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures spun up by pytest are exempt.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this work item.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00086 --json`.
- `ai-dev/active/I-00086/I-00086_Issue_Design.md` — design document
- `ai-dev/active/I-00086/reports/I-00086_S05_Tests_report.md` — S05 step report
- All test file(s) listed in S05's `files_changed`

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_S06_CodeReview_report.md` — Review report

## Context

You are reviewing the test suite written in S05. The tests must cover the reproduction case AND every regression scenario named in the design's **TDD Approach** section AND the three Acceptance Criteria (AC1, AC2, AC3 — AC4 is "tests exist", satisfied by S05 existing).

## Read the Design Document FIRST

Read `ai-dev/active/I-00086/I-00086_Issue_Design.md`. Note every test name and behavior the design names by path:

- The reproduction test in **Test to Reproduce** must exist with that exact name (`test_i00086_bulk_apply_returns_fragment_and_toast_trigger`).
- Per-step success + clear-override.
- Bulk success.
- Bulk zero-eligible branch (info toast, no event).
- 404 validation paths.
- Bulk count = number of EDITABLE steps changed, not total.
- Fragment content reflects updated model labels.

Any of the above missing from `files_changed` is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in the new test file is a **CRITICAL** finding with `category: "conventions"`.

## Review Checklist

### 1. Coverage Completeness

For each scenario listed above, confirm a test exists, has a descriptive name, and exercises the right code path.

### 2. Semantic Correctness (I003 Lesson)

This is the heart of this review. Every assertion in the file must check **specific expected values**, not just shape:

- BAD: `assert "showToast" in trigger` — flag as **HIGH**.
- BAD: `assert trigger["showToast"]["message"]` (truthy check) — flag as **HIGH**.
- BAD: `assert trigger["showToast"]["message"].startswith("Model updated")` — flag as **MEDIUM_FIXABLE** (allows bug where bulk message says `"Model updated for"` with no count to pass).
- GOOD: `assert trigger["showToast"]["message"] == "Model updated for 3 step(s)"`.

The bulk-count test in particular MUST assert the literal `"3 step(s)"` substring with the actual count from the seed, NOT just check that a number appears.

### 3. Isolation and Determinism

- Each test creates its own work item / steps; no order-dependence on other tests.
- Each test cleans up after itself (the `db_session` fixture should handle rollback — confirm).
- No `time.sleep` or wall-clock sensitivity.
- No reliance on auto-incremented IDs being a specific value.

### 4. Test Location

- File lives under `tests/dashboard/` because it uses the `client` fixture (registered in `tests/dashboard/conftest.py`).
- A test placed elsewhere fails with `fixture 'client' not found` per I-00067 / `tests/CLAUDE.md`.

### 5. Project Conventions

Read `tests/CLAUDE.md`:

- Uses testcontainer Postgres, NEVER live DB on port 5433.
- `DaemonEvent.metadata` accessed as `event_metadata` in Python.
- `monkeypatch.delenv()` for env vars; never `importlib.reload`.
- After `Base.metadata.create_all()`, FTS function/trigger SQL is applied (handled by fixture).
- CSS-class assertions use attribute-scoped form (e.g. `'class="my-class"'`), NOT bare substring (per `Issue_Design_Template.md` and I-00067).

### 6. Validation-Path Tests

Confirm that the 404 tests explicitly assert `"HX-Trigger" not in resp.headers` — without this, a regression that adds a toast to a 404 will silently slip through.

### 5a. TDD RED Evidence

S05 is a `tests-impl` step — exempt from the per-step RED-evidence rule per
`CodeReview_Prompt_Template.md`. The `tdd_red_evidence` field should be the
`"n/a — coverage step..."` form. If S05 reports anything different, raise a
**MEDIUM_SUGGESTION** rather than blocking.

## Test Verification (NON-NEGOTIABLE)

Run the new test file:

```bash
uv run pytest tests/dashboard/test_runtime_override_response.py -v
```

All tests must pass.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing scenario from the TDD Approach list; tests pass against the broken pre-fix code (no actual regression protection); test placed under `tests/unit/` or `tests/integration/` so `client` fixture is missing |
| **HIGH** | Shape-only assertions (e.g. `assert "showToast" in trigger`); test passes when toast says `"Model updated for "` with no count |
| **MEDIUM (fixable)** | Loose substring assertions; missing isolation; missing 404 toast-absence assertion |
| **MEDIUM (suggestion)** | Better fixture reuse, naming |
| **LOW** | Style nitpicks |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00086",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
