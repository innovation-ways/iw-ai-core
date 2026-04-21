# I-00033_S05_CodeReview_Final_prompt

**Work Item**: I-00033 — Code view layout bugs
**Step**: S05
**Agent**: code-review-final-impl
**Scope**: Global cross-agent review — S01 + S03 as an integrated whole

---

## Input Files

- `ai-dev/active/I-00033/I-00033_Issue_Design.md` — Design document (all ACs)
- `ai-dev/active/I-00033/reports/I-00033_S01_Frontend_report.md`
- `ai-dev/active/I-00033/reports/I-00033_S02_CodeReview_report.md` (must be `pass` — otherwise fix-cycle runs first)
- `ai-dev/active/I-00033/reports/I-00033_S03_Tests_report.md`
- `ai-dev/active/I-00033/reports/I-00033_S04_CodeReview_report.md` (must be `pass`)
- All S01 and S03 files (listed in their respective reports)

## Output Files

- Report: `ai-dev/active/I-00033/reports/I-00033_S05_CodeReview_Final_report.md`

## Review Focus

Per-agent reviews (S02, S04) already verified each step in isolation. Your job is the **integration view** — does S01 + S03 together satisfy the design document's acceptance criteria?

### Integration

- [ ] The Jinja render test (Test 1 in `tests/dashboard/test_code_layout_fixes.py`) asserts EXACTLY the `data-dismiss-job-id` attribute format that S01's `code_job_report.html` produces. No off-by-one between test and template.
- [ ] Same for `data-project-id`, `aria-label`, and the localStorage key format.
- [ ] The Jinja render test for `code_architecture_view.html` checks `h-full overflow-y-auto` on the exact element S01 modified. If S01 moved scroll to the `.p-8` body instead of the root card, the test must match.
- [ ] The browser test's "scroll container ancestry walk" finds the exact element S01 designated as the scroll container.
- [ ] The browser test's `--chat-width` check reads from `document.documentElement`, matching where S01 writes it.

### AC coverage

Walk through every AC in the design doc's "Acceptance Criteria" section and map to the test that proves it:

- [ ] AC1 (banner dismissible + per-job-id persistence) → render test 1 + browser test 1.
- [ ] AC2 (scrollbar inside card) → render tests 2 and 3 + browser test 2.
- [ ] AC3 (chat collapse reclaims space) → browser test 3.
- [ ] AC4 (regression tests exist) → the new test files themselves.
- [ ] AC5 (no mobile regressions) → verify S01's changes are all gated by `lg:` breakpoints OR are JS-only (applyCollapsedState is no-op below 1024px because the collapse button is `hidden lg:inline-flex`). If any change affects mobile, there MUST be either a test or an explicit note.

Report any AC that is NOT covered by a test as a critical finding.

### Contract stability

- [ ] `--chat-width` has exactly TWO writers after S01: `applyCollapsedState` and the resize handler. No third writer was added. The design doc records this contract.
- [ ] `iw_chat_width` in localStorage is still a number-as-string in the 320..480 range — S01 did not introduce a new format.
- [ ] `iw_code_lastrun_dismissed:<project_id>` is the agreed key format — S01's script and S03's test both use the same format (no mismatch like `iw_code_lastrun_dismiss` vs `iw_code_lastrun_dismissed`).

### Scope discipline

- [ ] S01 did NOT touch `dashboard/routers/code_ui.py`. Server-side behavior (the 1-hour window) is unchanged.
- [ ] S01 did NOT touch any file outside the five listed in its prompt (plus optionally the extracted `static/code/last_run_banner.js`).
- [ ] S01 did NOT introduce dynamic Tailwind class construction anywhere.
- [ ] S01 did NOT refactor unrelated code in the touched files.
- [ ] S03 did NOT modify production code — only created new test files (and optionally `conftest.py`).

### No leaked changes

- [ ] `git diff --stat main..HEAD` (or the equivalent for the worktree) shows changes only in:
  - `dashboard/templates/fragments/code_job_report.html`
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/fragments/code_architecture_view.html`
  - `dashboard/static/chat/panel.js`
  - `dashboard/templates/chat/panel.html`
  - Optionally: `dashboard/static/code/last_run_banner.js` (new)
  - `tests/dashboard/test_code_layout_fixes.py` (new)
  - `tests/dashboard/browser/test_code_layout_fixes.py` (new)
  - Optionally: `tests/dashboard/browser/conftest.py` (new or modified)
- [ ] No other files changed. Any other diff entry is a potential scope leak — report as medium severity unless the reason is documented in S01 or S03's report.

### End-to-end run

- [ ] `make lint` — clean.
- [ ] `make test-unit` — all pass. The three new render tests are under `tests/dashboard/` which is part of the unit run.
- [ ] `uv run pytest tests/dashboard/test_code_layout_fixes.py -v` — 3 passed.
- [ ] `uv run pytest tests/dashboard/browser/test_code_layout_fixes.py -m browser -v` — 3 passed (or documented-skip with a concrete environmental reason).

## Verdict

Emit one of:

- `pass` — zero critical, zero high findings; all ACs are covered; end-to-end test run is green.
- `fail` — one or more critical or high findings OR an uncovered AC OR a failing test. List each with `file:line` and remediation.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00033",
  "verdict": "pass|fail",
  "findings": [
    {"severity": "critical|high|medium|low|info", "file": "path:line", "issue": "...", "remediation": "..."}
  ],
  "ac_coverage": {
    "AC1": "covered by <test>",
    "AC2": "covered by <test>",
    "AC3": "covered by <test>",
    "AC4": "covered by <test>",
    "AC5": "covered by <test or note>"
  },
  "notes": "Summary of final review."
}
```
