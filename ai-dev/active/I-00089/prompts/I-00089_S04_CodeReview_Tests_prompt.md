# I-00089_S04_CodeReview_Tests_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT run docker compose / kill / stop / restart commands. Read-only
`docker ps` / `docker logs` is allowed. This step is review-only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp. Not needed for this step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00089 --json` for current step + previous-step report paths.
- `ai-dev/active/I-00089/I-00089_Issue_Design.md` -- design doc
- `ai-dev/active/I-00089/reports/I-00089_S01_Frontend_report.md` -- S01 report (especially which variant was chosen)
- `ai-dev/active/I-00089/reports/I-00089_S03_Tests_report.md` -- S03 report
- `tests/dashboard/test_chat_assistant_header.py` -- as written by S03
- `dashboard/templates/chat_assistant/panel.html` -- as modified by S01 (the test must accept this)
- `CLAUDE.md` and `dashboard/CLAUDE.md` -- project conventions

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_S04_CodeReview_Tests_report.md` -- Review report

## Context

You are reviewing S03's reproduction + regression tests for I-00089. Verify the tests genuinely catch the bug (i.e. would have failed pre-fix) and are not just shape checks that always pass.

## Review Checklist

### Test placement

- [ ] File is at `tests/dashboard/test_chat_assistant_header.py` (NOT under `tests/unit/` or `tests/integration/` — only `tests/dashboard/conftest.py` re-exports the `db_session` / `test_project` fixtures from `tests/integration/conftest.py`).
- [ ] The file defines its own inline `client` fixture that overrides `get_db` to use the test `db_session` — same canonical pattern as `tests/dashboard/test_chat_panel_default_collapsed.py:25-42`. There is NO project-wide `client` fixture in `tests/dashboard/conftest.py`; relying on one would fail collection with `fixture 'client' not found`.

### Semantic correctness (CRITICAL — I003 lesson)

For EACH assertion in the file, ask: "Could this assertion pass against the pre-fix HTML?" If yes, it is a shape check and must be replaced.

- [ ] **Bug A assertion** matches the specific selector chain that the fix introduces — e.g. `re.search(r'#chat-assistant-panel\[data-collapsed="true"\][^{]*#chat-assistant-collapse-btn', html, re.DOTALL)`. A bare `"chat-assistant-collapse-btn" in html` would always pass (the button still exists in the DOM) — flag as CRITICAL if present.
- [ ] **Bug B `title` assertion** uses a word-boundary-anchored regex (`re.search(r'\btitle="[^"]+"', button_tag)`) or equivalent — NOT a bare `"title" in button_tag` substring (which matches the letters "title" anywhere, including inside the `aria-label` attribute name).
- [ ] **Bug B class-marker assertion** targets EXACTLY the variant S01 chose (read S01's report `notes` field). The assertion must be tight — e.g. `"chat-assistant-collapse-btn-distinct" in classes` (split on whitespace), NOT `"distinct" in button_tag` (substring search).
- [ ] **Element-scoped match for the button**: tests use a regex like `re.search(r'<button[^>]*id="chat-assistant-collapse-btn"[^>]*>', html)` to extract the opening tag and assert on its contents — they do NOT do bare substring search across the whole page (which can match `chat-assistant-collapse-btn` inside the served `chat.js` source).

### Test isolation and stability

- [ ] No reliance on global state, environment variables, or session ordering.
- [ ] Tests don't depend on Tailwind class names that may change with future template restyles unless those classes are explicitly part of the fix's contract.
- [ ] No `time.sleep`, no network calls.

### Test results

- [ ] S03's report shows `tests_passed: true` with `2 passed, 0 failed`.
- [ ] The targeted run (`uv run pytest tests/dashboard/test_chat_assistant_header.py -v --no-cov`) is the ONLY pytest command in S03's notes — no `make test-integration`, no `make test-unit`.

### RED reasoning

- [ ] S03's `tdd_red_evidence` is `n/a — dedicated coverage step (tests-impl); RED reproduced at incident intake via playwright-cli (see ai-dev/active/I-00089/evidences/pre/)` or equivalent. Per the skill, `tests-impl` is exempt from the runtime-RED requirement; RED was established in incident intake.

### Pre-flight gate sanity

- [ ] S03's `preflight.format` / `typecheck` / `lint` are all `ok` / `fixed` / a justified `skipped:<reason>`.

## Findings Format

Produce `ai-dev/active/I-00089/reports/I-00089_S04_CodeReview_Tests_report.md`:

```markdown
# I-00089 S04 CodeReview Tests — Report

## Summary

{pass / partial / fail and reason}

## Findings

| Severity | Area | Finding | File:line | Required Fix |
|----------|------|---------|-----------|--------------|

## Acceptance Criteria Traceability

| AC | Covered by | Status |
|----|------------|--------|
| AC3 | tests/dashboard/test_chat_assistant_header.py — 2 reproduction tests | pass / fail |

## Decision

- `complete` if no CRITICAL or HIGH findings.
- `partial` if CRITICAL/HIGH findings exist.
```

Then:

```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/I-00089/reports/I-00089_S04_CodeReview_Tests_report.md
```

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00089",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/I-00089/reports/I-00089_S04_CodeReview_Tests_report.md"
  ],
  "preflight": {
    "format": "skipped:review-only",
    "typecheck": "skipped:review-only",
    "lint": "skipped:review-only"
  },
  "tests_passed": true,
  "test_summary": "skipped: review step",
  "tdd_red_evidence": "n/a — review step",
  "findings_count": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blockers": [],
  "notes": ""
}
```
