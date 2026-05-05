# I-00065_S03_Tests_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Same policy as the rest of this work item — no `docker compose up/down`,
no `docker kill/stop/rm/restart`, no volume/system prunes. Testcontainers
from pytest fixtures are allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does not involve migrations. Do not run any state-changing
alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00065 --json`.
- `ai-dev/active/I-00065/I-00065_Issue_Design.md` -- Design document (see "Test to Reproduce" section)
- `ai-dev/active/I-00065/reports/I-00065_S01_Frontend_report.md` -- S01 implementation report
- `dashboard/templates/chat/panel.html`, `dashboard/static/chat/panel.js` -- the fixed files
- `tests/CLAUDE.md` -- dashboard test conventions
- `tests/dashboard/` -- existing dashboard test layout for naming + fixture patterns

## Output Files

- `tests/dashboard/test_chat_panel_template.py` -- new (Bug 1 reproduction + regression)
- `tests/dashboard/test_chat_panel_empty_state.py` -- new (Bug 2 reproduction + regression)
- `ai-dev/active/I-00065/reports/I-00065_S03_Tests_report.md` -- Step report

## Context

You are writing the regression test coverage for **I-00065**. The S01 frontend fix is already in place; your job is to encode both bugs as failing-before / passing-after tests so they cannot silently come back.

Read the design's "Test to Reproduce" section for the contract — both tests must FAIL against the pre-fix code (revert mentally to confirm) and PASS against the current fixed code.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

Apply that lesson here:

- BAD: `assert "chat-new-btn" in PANEL_HTML` (only checks the button still exists — does NOT prove it's hidden in the collapsed state).
- GOOD: `assert '#chat-panel[data-collapsed="true"] #chat-new-btn' in style_block` (semantic — verifies the specific selector clause that hides it).
- BAD: `assert "remove" in showEmptyState_body` (matches any random `.remove()` call).
- GOOD: assert that the function looks up `#chat-empty-state` via `getElementById('chat-empty-state')` (or `querySelector('#chat-empty-state')`) AND that `.remove()` is called on the result before the new element is inserted.

## Requirements

### 1. `tests/dashboard/test_chat_panel_template.py` (Bug 1)

Create a new test file that asserts the rendered `dashboard/templates/chat/panel.html`'s top `<style>` block hides `#chat-new-btn` when `#chat-panel` is in `data-collapsed="true"` state.

Recommended approach (Python-only, no browser needed): read the file, locate the `<style>` block, and assert the literal substring `#chat-panel[data-collapsed="true"] #chat-new-btn` is present and grouped with the other `data-collapsed="true"` selectors.

Stronger optional check: parse the selector list and assert the set `{#chat-context-label, #chat-messages, #chat-scroll-to-bottom-wrap, #chat-composer, #chat-collapse-btn, #chat-new-btn}` is a subset of the IDs hidden when collapsed.

If you also want a rendering-level test, you may use `dashboard.app.create_app()` + `TestClient` to render the project Code page and use `BeautifulSoup` (already in the test dev dependencies) to confirm the element selector exists in the served `<style>` block. This is optional — the file-level assertion is sufficient for regression protection.

Test name (REQUIRED): `test_i00065_new_button_hidden_when_collapsed`.

### 2. `tests/dashboard/test_chat_panel_empty_state.py` (Bug 2)

Create a new test file that asserts the `showEmptyState` function in `dashboard/static/chat/panel.js` removes any pre-existing `#chat-empty-state` element before inserting a new one.

Approach: read `dashboard/static/chat/panel.js` as text, locate the `showEmptyState` function body, and assert:

1. The function references the existing `#chat-empty-state` element by ID (`getElementById('chat-empty-state')` or `querySelector('#chat-empty-state')`).
2. `.remove()` is called somewhere in the body (the call site must be inside `showEmptyState`, not anywhere else in the file — slice the function body before checking).
3. The lookup happens BEFORE the insertion (`messages.insertBefore(empty, anchor)` or equivalent). You can verify ordering by recording the byte offsets of the two patterns within the sliced function body.

Test name (REQUIRED): `test_i00065_show_empty_state_removes_existing_before_insert`.

Bonus (optional but encouraged): a second test that asserts `showEmptyState` cannot leave more than one `#chat-empty-state` in the DOM. The simplest mechanism is a textual check that the function body contains a guard pattern matching one of:

- `if (existingEmpty) existingEmpty.remove();`
- `if (existing) existing.remove();`
- `existingEmpty?.remove();`

Choose whichever pattern S01 actually used and assert that idiom.

### 3. Sanity-check the design doc's snippets

The design's "Test to Reproduce" section contains illustrative test bodies. You may use them as a starting point but must adapt them to:

- Match `tests/CLAUDE.md` conventions (file naming, fixture style, no live DB).
- Be deterministic (no relative file paths that depend on CWD — use `pathlib.Path(__file__).resolve().parents[2] / "dashboard" / "..."`).
- Pass `make lint` (ruff) and `make typecheck` (mypy).

### 4. Hard scope limits

This incident's `scope.allowed_paths` allows you to touch ONLY these files:

- `dashboard/templates/chat/panel.html` (S01 already touched)
- `dashboard/static/chat/panel.js` (S01 already touched)
- `tests/dashboard/test_chat_panel_template.py` (yours to create)
- `tests/dashboard/test_chat_panel_empty_state.py` (yours to create)

Do NOT touch any other file. Do NOT add new test fixtures elsewhere. Do NOT modify `tests/conftest.py`.

## Project Conventions

Read `tests/CLAUDE.md` for the dashboard test layout, fixture rules, and the "NEVER connect to live DB" rule. Both new tests are pure file-content assertions and need no DB or testcontainer — that's fine and preferred.

## TDD Requirement

The S01 fix is already in place. Your tests must:

1. **RED check**: confirm mentally (or by `git show HEAD~1`) that the test would fail against the pre-fix code.
2. **GREEN check**: run the test against the current code and confirm it passes.

Do NOT skip the RED check.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting drift on the new test files.
2. `make typecheck` — zero mypy errors in the new files.
3. `make lint` — zero ruff errors in the new files.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-frontend` (or directly `uv run pytest tests/dashboard/test_chat_panel_template.py tests/dashboard/test_chat_panel_empty_state.py -v`) and confirm both new tests PASS.
2. Run `make test-unit` to ensure no other test regressed.
3. Do NOT report `tests_passed: true` unless every dashboard test passes with zero failures.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/test_chat_panel_template.py",
    "tests/dashboard/test_chat_panel_empty_state.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
