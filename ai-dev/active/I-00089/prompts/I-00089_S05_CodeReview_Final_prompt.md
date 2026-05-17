# I-00089_S05_CodeReview_Final_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT run docker compose / kill / stop / restart. Read-only
`docker ps` / `docker logs` is allowed. This step is review-only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp. Not needed for this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00089 --json`.
- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- design doc with AC1, AC2, AC3.
- `ai-dev/active/I-00089/I-00089_Functional.md` -- functional spec.
- `ai-dev/active/I-00089/reports/I-00089_S01_Frontend_report.md`
- `ai-dev/active/I-00089/reports/I-00089_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/I-00089/reports/I-00089_S03_Tests_report.md`
- `ai-dev/active/I-00089/reports/I-00089_S04_CodeReview_Tests_report.md`
- `dashboard/templates/chat_assistant/panel.html` -- as modified
- `dashboard/static/chat_assistant/chat.css` -- as modified
- `tests/dashboard/test_chat_assistant_header.py` -- as written
- `git diff main --stat` -- summary of all changes
- `git diff main -- dashboard/templates/chat_assistant/ dashboard/static/chat_assistant/ tests/dashboard/test_chat_assistant_header.py` -- exact diff

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_S05_CodeReview_Final_report.md` -- global review report

## Context

You are running the global cross-agent review for I-00089. Earlier per-agent reviews (S02 for the fix, S04 for the tests) covered each step in isolation. Your job is to verify the work hangs together as a coherent fix package: every AC is traceable to a concrete code change AND to a passing test, scope is honoured, no unrelated files leaked into the diff, and the JS/keyboard/nav paths are still intact.

## Review Checklist

### Acceptance criteria traceability

For each AC in the design doc, confirm:

- [ ] **AC1 — Bug A — collapsed-state stray button is gone**
  - Code change: `panel.html` inline `<style>` block includes `#chat-assistant-collapse-btn` in the `[data-collapsed="true"]` `display:none` selector group.
  - Test: `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_a_collapse_button_hidden_when_collapsed` asserts the selector chain.
- [ ] **AC2 — Bug B — expanded-state collapse button is discoverable**
  - Code change: `panel.html` `<button id="chat-assistant-collapse-btn">` carries a `title` attribute AND a distinguishing class marker.
  - Test: `tests/dashboard/test_chat_assistant_header.py::test_i00089_bug_b_collapse_button_has_discoverable_affordance` asserts both.
- [ ] **AC3 — Regression test exists**
  - The two tests above are present, run targeted, and S03's report shows them passing.

### Reproduction test correctness

Re-verify the rule from S04 (the reproduction tests would fail against pre-fix code):

- [ ] Mentally remove S01's `<style>` block change (drop the `#chat-assistant-collapse-btn` line from the selector list) — `test_i00089_bug_a_*` would now fail because the regex `re.search(r'#chat-assistant-panel\[data-collapsed="true"\][^{]*#chat-assistant-collapse-btn', html, re.DOTALL)` returns None.
- [ ] Mentally remove S01's title + class-marker additions to the button — `test_i00089_bug_b_*` would now fail because the `title="..."` regex / class-marker assertion no longer matches.
- [ ] Neither test is a permissive shape-check that would pass against pre-fix HTML.

### Scope adherence

- [ ] `git diff main --name-only` matches the manifest's `scope.allowed_paths`:
  - `dashboard/templates/chat_assistant/panel.html`
  - `dashboard/static/chat_assistant/chat.css` (only if S01 added the supporting CSS rule)
  - `tests/dashboard/test_chat_assistant_header.py`
  - plus the design / report / prompt files under `ai-dev/active/I-00089/**`.
- [ ] No changes outside that list. Any other modified file is a scope violation — flag as CRITICAL.

### Behaviour preservation

- [ ] `dashboard/static/chat_assistant/chat.js` is byte-identical to main (no JS changes).
- [ ] The Ctrl+/ keybinding still works (handler at `chat.js:937-942` is untouched).
- [ ] The nav-bar toggle (`#chat-assistant-nav-toggle`, wired at `chat.js:965-968`) still works.
- [ ] The expand rail (`#chat-assistant-expand-rail`) is still the collapsed-state affordance.
- [ ] The `aria-label="Collapse AI Assistant panel (Ctrl+/)"` is preserved exactly on the collapse button.

### Cross-page sanity

- [ ] CSS rules added in this fix are all scoped under `#chat-assistant-panel` (no global selectors).
- [ ] If S01 chose Variant B (Tailwind utilities), those utility classes exist in the prebuilt `dashboard/static/styles.css` — `grep` for each new class. If a utility class is missing, the fix needs either `make css` to be run OR a fallback to Variant A (custom class + plain CSS in `chat.css`).

### Pre-flight gates and previous reviews

- [ ] S01 / S03 reports both show `preflight.format`, `typecheck`, `lint` as `ok` / `fixed` / justified-`skipped`.
- [ ] S02 and S04 reports both have empty CRITICAL/HIGH findings tables (or any flagged items were addressed in subsequent commits).

## Findings Format

Produce `ai-dev/active/I-00089/reports/I-00089_S05_CodeReview_Final_report.md`:

```markdown
# I-00089 S05 CodeReview Final — Report

## Summary

{pass / partial / fail and reason}

## Acceptance Criteria Traceability

| AC | Code change | Test coverage | Status |
|----|-------------|---------------|--------|
| AC1 | panel.html `<style>` ext. | test_i00089_bug_a_* | pass |
| AC2 | panel.html button title + class | test_i00089_bug_b_* | pass |
| AC3 | tests/dashboard/test_chat_assistant_header.py | targeted run 2 passed | pass |

## Cross-step Findings

| Severity | Area | Finding | File:line | Required Fix |
|----------|------|---------|-----------|--------------|

## Scope adherence

| File | In allowed_paths? | Notes |
|------|--------------------|-------|

## Decision

- `complete` if every AC is traceable and no CRITICAL/HIGH cross-step findings exist.
```

Then:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00089/reports/I-00089_S05_CodeReview_Final_report.md
```

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00089",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00089/reports/I-00089_S05_CodeReview_Final_report.md"
  ],
  "preflight": {
    "format": "skipped:review-only",
    "typecheck": "skipped:review-only",
    "lint": "skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "skipped: global review step",
  "tdd_red_evidence": "n/a — review step",
  "findings_count": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blockers": [],
  "notes": ""
}
```
