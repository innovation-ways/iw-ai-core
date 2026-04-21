# I-00033_S04_CodeReview_prompt

**Work Item**: I-00033 — Code view layout bugs
**Step**: S04
**Agent**: code-review-impl
**Reviews**: S03 (tests-impl)

---

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` — Design document
- `ai-dev/active/I-00033/reports/I-00033_S03_Tests_report.md` — S03 report
- `tests/dashboard/test_code_layout_fixes.py` — new render tests
- `tests/dashboard/browser/test_code_layout_fixes.py` — new browser smoke
- `tests/dashboard/browser/conftest.py` — if S03 created/modified it
- `tests/dashboard/browser/test_chat_panel_smoke.py` — reference for fixture pattern
- `tests/CLAUDE.md` — testing rules

## Output Files

- Report: `ai-dev/active/I-00033/reports/I-00033_S04_CodeReview_report.md`

## Review Checklist

### Semantic correctness (MUST enforce — I003 lesson)

- [ ] Every assertion checks a SPECIFIC value, not just presence or truthiness.
- [ ] `data-dismiss-job-id="12345"` assertion includes the literal `=` and specific value — not just `"data-dismiss-job-id" in html`.
- [ ] `--chat-width` assertion checks the exact string `"48px"` — not just that the variable exists.
- [ ] `overflow-y-auto` absence check is scoped to the specific element (`#code-content-root`) — not a page-wide `"overflow-y-auto" not in html`.
- [ ] Architecture card scroll check requires BOTH `overflow-y-auto` AND `h-full` — missing `h-full` is a high-severity finding (without it, no scrollbar appears).

### RED-phase verification

- [ ] S03's report documents RED phase — either via `git stash` method or read-git-history trace.
- [ ] If RED was not actually observed (e.g., the agent skipped this), mark as a high-severity finding; a test that was never shown to fail cannot be trusted to catch the bug reliably.

### Fixture hygiene

- [ ] Browser tests use the existing `dashboard_server` / `playwright_session` fixtures from `test_chat_panel_smoke.py` (or extract to conftest and import from both files).
- [ ] No duplicated Uvicorn boot logic.
- [ ] localStorage is cleared between tests (autouse teardown or module-scoped teardown).
- [ ] If S03 added a CodeIndexJob seed fixture to make `last_completed_job` truthy, verify the seed uses the existing ORM models (no raw SQL), uses the testcontainer's session, and cleans up on teardown.

### Browser test discipline

- [ ] Uses `playwright-cli` exclusively — no `chromium.launch()`, no `agent-browser`, no `playwright install`.
- [ ] `@pytest.mark.browser` is applied (either module-level or per-test).
- [ ] Snapshot is called before every click/fill to read current refs (the chat panel test does this — verify the pattern is followed).
- [ ] No hardcoded URL — uses the `dashboard_server` fixture's base URL.

### Test readability

- [ ] Each test has a docstring naming the specific bug it reproduces and linking back to I-00033.
- [ ] Failure messages are informative — a maintainer reading a red test should know immediately why it failed (e.g., `f"Expected --chat-width=48px on collapse, got {val!r} (I-00033 bug 3)"`).

### No violations of tests/CLAUDE.md

- [ ] No `importlib.reload(orch.config)`.
- [ ] No direct connection to port 5433.
- [ ] No mocking of the DB in integration tests.
- [ ] No appending to tracked config files (no writes to `projects.toml`, `.env`, etc.).

### Coverage of the three bugs

- [ ] Bug 1 (banner dismissal) has a render test AND a browser test.
- [ ] Bug 2 (scroll container) has a render test AND a browser test.
- [ ] Bug 3 (chat collapse) has a render test OR a browser test (it's a runtime-JS bug, so a browser test is sufficient — but the `--chat-width` CSS var contract could also have a unit-level sanity check if desired; not required).
- [ ] All three bugs are covered by at least one test that FAILS against pre-S01 code.

## Verdict

Emit one of:

- `pass` — zero critical, zero high findings.
- `fail` — one or more critical or high findings. List each with `file:line` and a concrete remediation.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00033",
  "reviews_step": "S03",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "critical|high|medium|low|info", "file": "path:line", "issue": "...", "remediation": "..."}
  ],
  "notes": "Summary of review."
}
```
