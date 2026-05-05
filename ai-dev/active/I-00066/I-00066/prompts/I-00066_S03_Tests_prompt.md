# I-00066_S03_Tests_prompt

**Work Item**: I-00066 -- OSS finding modal too narrow and footer buttons unclear
**Step**: S03
**Agent**: Tests (tests-impl)

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident touches no database state — there is no migration step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00066 --json`.
- `ai-dev/active/I-00066/I-00066_Issue_Design.md` -- Design document
  (read the **Test to Reproduce** section verbatim — it contains the
  exact test code structure and assertions you must produce).
- `ai-dev/active/I-00066/reports/I-00066_S01_Frontend_report.md` -- S01 report
- `dashboard/static/tailwind.src.css` -- CSS source under test
- `dashboard/static/styles.css` -- Compiled CSS under test
- `dashboard/templates/fragments/oss_finding_modal.html` -- Template under test
- `tests/conftest.py` -- existing pytest fixtures
- `tests/dashboard/` -- where this test lives

## Output Files

- `tests/dashboard/test_i00066_oss_modal_styling.py` -- New test file
- `ai-dev/active/I-00066/reports/I-00066_S03_Tests_report.md` -- Step report

## Context

You are producing the reproduction + regression tests for **I-00066**.
This is a frontend cosmetic bug, so the assertions look at the rendered
template fragment and the compiled stylesheet rather than at Python
return values.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert ".oss-modal-inner" in css` (only checks the selector exists — would pass on the buggy `main`)
- BAD: `assert "max-width" in css_block` (only checks the property name — would pass on the buggy `main`)
- BAD: `assert any(b for b in buttons if b.get("class"))` (only checks any button has a class)
- GOOD: `assert "max-width: 80vw" in css_block` (specific expected value)
- GOOD: `assert "36rem" not in css_block` (specific UNWANTED value is absent)
- GOOD: `assert 'modal-footer-close' in classes_on_footer_close_button` (specific expected class)

Each test MUST fail on `main` (pre-fix) and pass on the fix branch.

## Requirements

### 1. Create the test file

Create `tests/dashboard/test_i00066_oss_modal_styling.py`. Base its
structure on the **Test to Reproduce** section of the design document
(`ai-dev/active/I-00066/I-00066_Issue_Design.md`) — that section
contains the canonical test code. You may refine wording/comments but
keep the four test functions and their semantic assertions:

1. `test_i00066_modal_inner_widened_in_source_css` — asserts
   `max-width: 80vw` is INSIDE the `.oss-modal-inner` block of
   `dashboard/static/tailwind.src.css` AND that `36rem` is NOT in the
   same block.
2. `test_i00066_modal_inner_widened_in_compiled_css` — asserts the
   same semantic value (`max-width: 80vw` or `max-width:80vw`) is
   present in the `.oss-modal-inner` block of the compiled
   `dashboard/static/styles.css`, and that `36rem` is NOT in that
   block.
3. `test_i00066_footer_close_uses_peer_button_class` — asserts
   `dashboard/templates/fragments/oss_finding_modal.html` has a
   `<button>` with class containing `modal-footer-close` whose text
   content (after surrounding whitespace stripped) is `Close`.
4. `test_i00066_footer_button_class_styled_in_source_css` — asserts
   the `.modal-footer-close` rule exists in `tailwind.src.css` AND
   contains the substrings `border:` and `padding:` (real
   declarations, not just the selector).

### 2. Reproduction guarantee

Each test MUST FAIL against pre-fix `main`. Verify by mental check:
- Test 1: `tailwind.src.css` on `main` has `max-width: 36rem` →
  `"max-width: 80vw" in body` is False → test fails.
- Test 2: `styles.css` on `main` has `36rem` in `.oss-modal-inner` →
  `"max-width:80vw" in body` is False → test fails.
- Test 3: `oss_finding_modal.html` on `main` line 74 has
  `class="modal-close"` only → no `modal-footer-close` substring →
  test fails.
- Test 4: `.modal-footer-close` rule does not exist on `main` →
  `_block(...)` raises AssertionError → test fails.

If your formulation of any test would PASS on `main`, redesign it.

### 3. Test isolation and conventions

- Tests must be deterministic (read files synchronously, no network,
  no DB).
- Tests live under `tests/dashboard/` (this is dashboard-level, not a
  pure unit test, but the assertions only read static files so the
  test category is fine).
- Use a `REPO_ROOT = Path(__file__).resolve().parents[2]` constant to
  locate files — DO NOT use `os.getcwd()` or hardcoded absolute paths.
- Match existing pytest style in `tests/dashboard/` (no class-based
  tests, function-level only, plain assertions, no `unittest`).

### 4. No other tests modified

Do NOT modify any other test file. Do NOT modify
`tests/dashboard/conftest.py` or `tests/conftest.py`. Do NOT modify
the project's `Makefile`, `pyproject.toml`, or `pytest.ini`.

### 5. Run the new test

After writing it, run:

```bash
uv run pytest tests/dashboard/test_i00066_oss_modal_styling.py -x -v
```

All four tests must PASS against the fix produced in S01. If a test
fails, investigate whether the test is wrong or whether S01's fix is
incomplete and report accordingly (the orchestrator will route a fix
cycle as needed — do not "fix" S01's CSS yourself).

Also confirm the broader unit test suite still passes:

```bash
make test-unit
```

## Project Conventions

Read `CLAUDE.md` and `tests/CLAUDE.md` for:
- Test framework choice (pytest), naming, organization.
- The rule about NEVER connecting tests to the live DB on port 5433
  — but for THIS incident the tests don't touch the DB at all.
- Test isolation, fixtures, and parameterization patterns.

## TDD Requirement

This is the RED-test step in the TDD loop. The reproduction tests
should FAIL on the pre-fix code and PASS once S01's CSS/template
edits are in place. Confirm both directions if you can (run against
the current worktree HEAD which already includes S01's changes; the
test should pass).

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift on the new test file.
2. `make typecheck` — must report zero errors involving the new file.
3. `make lint` — must report zero errors.

## Test Verification (NON-NEGOTIABLE)

1. The four new tests must pass.
2. `make test-unit` must report no regressions in the broader suite.
3. Do NOT report `tests_passed: true` unless ALL unit tests pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00066",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_i00066_oss_modal_styling.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "4 passed (this file), N passed total, 0 failed",
  "blockers": [],
  "notes": ""
}
```
