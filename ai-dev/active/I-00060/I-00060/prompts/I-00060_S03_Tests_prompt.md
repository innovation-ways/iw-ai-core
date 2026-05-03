# I-00060_S03_Tests_prompt

**Work Item**: I-00060 -- Code chat — pin user message on Enter and tighten empty Assistant bubble
**Step**: S03
**Agent**: Tests (tests-impl)

---

## ⛔ Docker is off-limits

Same restrictions as previous steps. See
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No DB changes in scope. Tests must NOT run live alembic commands; the
test suite uses testcontainers via `tests/conftest.py`.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00060 --json`.
- `ai-dev/active/I-00060/I-00060_Issue_Design.md` (read the "Test to Reproduce" section)
- `ai-dev/active/I-00060/reports/I-00060_S01_Frontend_report.md`
- `ai-dev/active/I-00060/reports/I-00060_S02_CodeReview_report.md`
- Existing browser tests under `tests/dashboard/browser/` — `conftest.py`, `test_chat_panel_smoke.py`, `test_chat_mermaid.py` are the established pattern. New tests for I-00060 MUST live in this lane and use the `-m browser` marker.
- `tests/conftest.py` and `tests/CLAUDE.md`
- `dashboard/static/chat/composer.js` and `dashboard/static/chat/render.js` (post-fix)

## Output Files

- New test file(s) (the agent decides the path; see below)
- `ai-dev/active/I-00060/reports/I-00060_S03_Tests_report.md`

## Context

You are writing the reproduction + regression tests for I-00060. The two
bugs are pure browser-layout / scroll behaviours and are not meaningfully
testable in pure unit tests. Your tests must therefore exercise a real
browser via `playwright-cli`.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty)
and passed. But the bug was NOT fixed. Tests must verify SPECIFIC VALUES.
Translated to this layout-bug context:

- BAD: `assert page.querySelector('article[data-role="assistant"]')` — only
  checks the bubble exists, not that its size is correct.
- BAD: `assert send_button_clicked` — only checks a click event fired, not
  that the chat scrolled.
- GOOD: assert specific numeric / geometric facts:
  - `bubble.getBoundingClientRect().height <= 48` for the empty bubble.
  - The user bubble's `.bottom` is `<=` the messages container's `.bottom`
    after submit (i.e. it is actually visible inside the scroll viewport).
- GOOD: assert specific layout state, not just that an event fired or a
  function was called.

If your test passes when the fix is reverted, your test is wrong. Verify
this explicitly: revert S01, run the test, confirm RED, re-apply S01,
confirm GREEN. Document this in your report.

## Requirements

### 1. Reproduction tests (RED → GREEN)

Add browser-driven tests that assert AC1 and AC2 from the design doc.
Approximate structure (adapt to existing `tests/dashboard/` patterns —
read what's there before inventing a new harness):

```python
# tests/dashboard/browser/test_chat_scroll_i00060.py  (matches existing browser-test convention)

def test_i00060_repro_submit_scrolls_user_bubble_into_view(...):
    """AC1: After Enter, the just-typed user bubble must be visible inside
    the #chat-messages container — even when the conversation already
    overflowed and the user was scrolled up.
    Reverting S01 must make this test FAIL."""
    # Arrange: open Code page with index built, expand chat, send 8+
    # warmup questions to force overflow, scroll #chat-messages to top.
    # Act: type a new question and click #chat-send.
    # Assert (semantic correctness):
    #   user_rect.bottom <= container_rect.bottom
    #   user_rect.top    >= container_rect.top
    ...

def test_i00060_repro_empty_assistant_bubble_compact(...):
    """AC2: The empty assistant bubble (pre-stream) must render <= 48px tall.
    Reverting S01 must make this test FAIL."""
    # Arrange: open Code page, expand chat.
    # Act: type a question and submit. IMMEDIATELY (before the SSE stream
    #      delivers the first token) measure the bubble height.
    # Assert (semantic correctness):
    #   article = last <article data-role="assistant">
    #   article.getBoundingClientRect().height <= 48
    ...
```

### 2. Regression tests (AC3 + AC5)

Add tests that pin behaviours we want to keep:

- **AC3**: while streaming, follow-scroll is conditional. Send a message,
  wait for the stream to start, manually scroll up, verify the container
  does NOT auto-scroll back down. Then click the floating
  `#chat-scroll-to-bottom` button and verify it does scroll.
- **AC5**: send a question that triggers citations (or use a fixture);
  verify the citation popover still opens. Verify mermaid rendering
  still works on a known mermaid-emitting question (or use a fixture).
- **Phase strip growing the bubble is OK**: when a phase event arrives
  with text ("Looking up related code…"), the bubble may grow above 48px
  — that's expected and must NOT regress to a bug. Add a positive test
  that confirms the bubble grows once phase text appears.

### 3. Verify RED→GREEN

In your S03 report, document the RED→GREEN proof:

1. Stash or revert S01's changes locally (e.g. `git stash`).
2. Run the new tests — confirm the AC1 and AC2 reproduction tests FAIL
   with assertion messages that match the bug.
3. Restore S01 — confirm all new tests PASS.
4. Capture the failing-output snippets in the report so reviewers can
   verify the test would have caught the bug.

### 4. Choose the right harness

- The project's established browser-test lane is `tests/dashboard/browser/`
  with the `-m browser` marker, a module-scoped uvicorn fixture, and a
  `playwright-cli` session fixture (see
  `tests/dashboard/browser/conftest.py`). Add the new tests to this lane.
- Reuse the existing fixture(s) — do NOT introduce `agent-browser`,
  `chromium.launch()`, or `npx playwright install`.
- The new tests run via `uv run pytest tests/dashboard/browser/ -m browser -v`.
  These browser tests are NOT part of `make test-unit` /
  `make test-integration`. The orchestrator's S11 qv-browser step
  exercises the same behaviour end-to-end against the isolated stack;
  the pytest browser tests provide a developer-runnable regression
  layer.
- Tests should read `$IW_BROWSER_BASE_URL` when set (orchestrator
  context); the existing `tests/dashboard/browser/conftest.py` already
  spins up its own dashboard for local runs — match that pattern.

### 5. Do NOT add unrelated tests

- No tests for citation logic itself, sources panel rendering details,
  or RAG backend behaviour. Stay strictly within the I-00060 scope.

## Project Conventions

Read `tests/CLAUDE.md` and `CLAUDE.md`. Match the project's pytest fixture
style, naming (`test_iNNNNN_…`), and `make` lane choices.

## TDD Requirement

The reproduction tests above ARE the TDD RED phase. They must be:

1. **RED first**: written and confirmed to fail against pre-S01 code.
2. **GREEN after**: passing with S01's fix applied.

Do not mark this step complete unless you have explicit RED→GREEN
evidence in the report.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. **`make format`** — auto-fix formatting drift.
2. **`make typecheck`** — zero errors in files you touched.
3. **`make lint`** — zero errors.

## Test Verification (NON-NEGOTIABLE)

1. Run the new browser tests:
   `uv run pytest tests/dashboard/browser/ -m browser -v`
   The new I-00060 cases must PASS, and the rest of the browser lane
   must remain green.
2. Run `make test-unit` to confirm no regressions in the broader suite.
3. Run `make lint`.
4. Confirm in the report that the new I-00060 tests FAIL when S01 is
   reverted (RED→GREEN proof).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00060",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/dashboard/browser/test_chat_scroll_i00060.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X new passed, 0 failed; pre-S01 RED confirmed for AC1 and AC2",
  "red_to_green_evidence": "Brief description of the failing-output you observed when reverting S01 — included in full in the report.",
  "blockers": [],
  "notes": ""
}
```
