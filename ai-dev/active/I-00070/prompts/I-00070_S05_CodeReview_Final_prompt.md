# I-00070_S05_CodeReview_Final_prompt

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — Design document
- `ai-dev/active/I-00070/reports/I-00070_S01_Frontend_report.md`
- `ai-dev/active/I-00070/reports/I-00070_S02_CodeReview_Frontend_report.md`
- `ai-dev/active/I-00070/reports/I-00070_S03_Tests_report.md`
- `ai-dev/active/I-00070/reports/I-00070_S04_CodeReview_Tests_report.md`
- All files listed in the manifest's `scope.allowed_paths`

## Output Files

- `ai-dev/active/I-00070/reports/I-00070_S05_CodeReview_Final_report.md` — Global review verdict

## Context

You are the final cross-cutting reviewer for I-00070. Your job is to verify the WHOLE fix package integrates end-to-end — not to re-do the per-step reviews (S02, S04 already passed those).

## Global Review Checklist

1. **End-to-end correctness**: starting from a clean clone, render the execution-report fragment, click the button (in your head — read the rendered HTML), trace through the helper, into the success / fallback branches, into the UI feedback. Does this whole flow now work for both `localhost` and `iw-dev-01`?
2. **Reproduction test exercises the bug**: the server-side test asserts the buggy pattern is gone AND the fallback wiring is in. The Playwright test simulates the non-secure-context exactly. Both would FAIL on the pre-fix code (verify by mentally substituting back the original `onclick`).
3. **All 7 callsites migrated**: run `grep -rn "navigator.clipboard.writeText" dashboard/` and paste the output in your report. The ONLY hit must be inside `dashboard/static/clipboard.js`.
4. **No other clipboard users regressed**: search the repo for any other `clipboard` API usage you might have missed (`grep -rn "navigator.clipboard\b" dashboard/ tests/ | grep -v "clipboard.js"`). If there are matches, they must either go through the new helper or have a documented reason to stay direct.
5. **OSS page UX is consistent**: the OSS page no longer has dual UI feedback (helper's "Copied" + page's "✓") — only one is in effect.
6. **`base.html` load order**: confirm the script tag is positioned so `iwClipboard.copy(...)` is available before any inline `<script>` that uses it executes on click.
7. **All gates pass**: `make test-unit`, `make test-integration`, `make lint`, `make format-check`, `make typecheck`, `make security-sast`, `make arch-check` all pass on the merged worktree.
8. **CLAUDE.md updated**: the new "Clipboard buttons" subsection is present in `dashboard/CLAUDE.md` and references the helper.
9. **Functional doc accurate**: `I-00070_Functional.md` describes the user-visible behaviour the implementation actually delivers.
10. **Scope compliance**: every file modified is listed in `workflow-manifest.json:scope.allowed_paths`. No surprise edits.

## Verdict

```
Verdict: PASS | FIX_REQUIRED
```

If `FIX_REQUIRED`, list the cross-cutting issues that need a fix cycle. Be specific about which step's owner should address each issue.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00070",
  "verdict": "pass|fix_required",
  "scope_compliance": "ok|violation",
  "findings": [
    {"severity": "high|med|low", "owner_step": "S0X", "file": "path:line", "issue": "...", "fix": "..."}
  ],
  "test_summary": "X passed, 0 failed across all suites",
  "notes": ""
}
```
