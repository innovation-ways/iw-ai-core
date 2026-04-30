# F-00075_S08_CodeReview_Final_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S08
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits / Migrations off-limits

(Same policy as in S01.)

## Input Files

- `ai-dev/active/F-00075/F-00075_Feature_Design.md`
- All step reports: `F-00075_S01_Backend_report.md` through `F-00075_S07_Tests_report.md`.
- All implementation files (current state):
  - `orch/llm_usage.py`
  - `dashboard/routers/usage.py`
  - `dashboard/templates/fragments/llm_usage_footer.html`
  - `tests/unit/test_llm_usage.py`
  - `tests/fixtures/minimax_remains.json`
  - `.env.example` if modified.
- Pre-evidence: `ai-dev/active/F-00075/evidences/pre/F-00075-before-fragment.html`

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S08_CodeReview_Final_report.md`

## Context

Cross-layer global review. Verify backend + API + frontend + tests integrate correctly and match the design doc end-to-end.

## Requirements — Final Review Checklist

### Acceptance criteria coverage

For each AC1..AC7 in the design doc, identify the test(s) that prove it and any code path that implements it. Flag any AC that has no corresponding test.

### Cross-layer wiring

- [ ] `_minimax_usage()` returns `{"block_pct", "block_reset", "used", "total"}` on success and `{"block_pct": 0, "block_reset": None}` on failure (without `used`/`total`).
- [ ] `dashboard/routers/usage.py` uses `.get()` for the optional fields so the failure-path dict does not raise `KeyError`.
- [ ] `dashboard/templates/fragments/llm_usage_footer.html` renders correctly in both branches:
  - Success: bar shows the real %, label shows the reset countdown, tooltip shows `used / total`.
  - Failure: bar shows 0%, label shows `5h` literal, no `"None / None"` tooltip text appears.
- [ ] When the user has neither `IW_MINIMAX_API_KEY` set nor `~/.local/share/opencode/auth.json`, the dashboard renders 0% with no exception — confirmed by tests.

### SQLite removal

- [ ] Run `grep -rnE 'sqlite3|_OPENCODE_DB|_FIVE_H_MS|_MINIMAX_5H_LIMIT|IW_MINIMAX_5H_LIMIT|opencode\.db' orch/ dashboard/` and confirm zero matches in the changed area. Document the command and result in your report.
- [ ] No reference to the deleted constants in `tests/unit/test_llm_usage.py` either.
- [ ] If `.env.example` previously documented `IW_MINIMAX_5H_LIMIT`, it has been removed.

### No regression to Claude

- [ ] Diff `orch/llm_usage.py` against `main` for the Claude region. The Claude functions (`_claude_usage`, `_run_ccusage`, `_block_start`, `_sum_jsonl_tokens`) and constants (`_CLAUDE_5H_LIMIT`, `_CLAUDE_WEEKLY_LIMIT`, `_CLAUDE_BLOCK_ANCHOR_MIN`) must be byte-identical, **unless** a `_format_reset` helper was extracted and Claude was migrated to use it (in which case verify the produced reset string is exactly the same as before for representative inputs).
- [ ] Claude bars in `llm_usage_footer.html` are unchanged.
- [ ] No new fields required by the Claude template branch.

### Test quality

- [ ] All Boundary Behavior rows from the design doc map to a test (run through every row).
- [ ] All Invariants from the design doc map to a test.
- [ ] No flaky tests: no real network, no real filesystem reads of the user's home, deterministic clock manipulation.
- [ ] Fixture file contains no secrets.

### Quality gates

- [ ] `make lint` passes.
- [ ] `make format` is clean (no diff after running).
- [ ] `make typecheck` passes.
- [ ] `make test-unit` passes.
- [ ] `make allure-integration` passes (or noted as not applicable; the design doc says integration is optional for this feature).

### Manual smoke

- [ ] `uv run python -c "from orch.llm_usage import _minimax_usage; print(_minimax_usage())"` returns a sensible dict in your worktree (either real numbers if the auth.json/env path is set, or `{0, None}` cleanly).
- [ ] If a dashboard is reachable in the worktree, `curl -s $IW_BROWSER_BASE_URL/api/usage/llm/fragment` returns valid HTML containing the MiniMax label.

## Output

Write `F-00075_S08_CodeReview_Final_report.md` containing:

- A pass/fail line per checklist item above.
- A traceability table: AC → tests → implementation files.
- A list of cross-layer findings with severity.
- Final recommendation: `approve` or `request_changes`.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "F-00075",
  "completion_status": "complete",
  "review_outcome": "approve|request_changes",
  "findings": [],
  "tests_passed": true,
  "notes": ""
}
```
