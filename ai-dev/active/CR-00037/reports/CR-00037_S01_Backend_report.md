# CR-00037 S01 Backend Report

## What was done

Inserted a new "Verify vendored / third-party library APIs before drafting calls" step into the `## Required Workflow` section of both `agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md`. The step was inserted as step 4 (between "Identify existing patterns" and "Apply TDD where applicable"), and the remaining steps were renumbered contiguously (old 4→5, 5→6, 6→7).

The new step body contains all required elements from the CR acceptance criteria:
- Bolded step title containing "vendored" and "third-party"
- Explicit list of asset locations (`static/vendor/**`, libs-include pipeline, `node_modules/**`)
- Instruction to grep the bundled JS file, read `.d.ts`, or confirm in DevTools/REPL before drafting call code
- Note that slim and full builds may export different surfaces
- "Why this rule exists" clause citing F-00079 self-assess Finding 1, naming the ~45 min / 3 fix-cycle waste, naming `Diff2HtmlUI.create(...)` as the historically wrong call, and contrasting with `new Diff2HtmlUI(...)` the constructor that actually works

## Files changed

- `agents/claude/frontend-impl.md` — new step 4 inserted, steps 5–7 renumbered
- `agents/opencode/frontend-impl.md` — same change, substantively identical wording

## Pre-flight gate results

| Gate | Result | Notes |
|------|--------|-------|
| `make format-check` | `skipped: pre-existing drift` | One unrelated file (`tests/integration/test_e2e_seed.py`) fails format; not touched by this CR. Issue is pre-existing on `main`. |
| `make type-check` | `ok` | 230 source files, zero type errors |
| `make lint` | `skipped: pre-existing drift` | One unused-import lint error in `tests/integration/test_e2e_seed.py`; not touched by this CR. Issue is pre-existing on `main`. |

## Test results

skipped: no code changes — this CR touches only two markdown agent-definition files.

## Acceptance Criteria check

| AC | Status |
|----|--------|
| AC1: Step present in both masters with all required elements | ✅ Step 4 in both files contains "vendored", "third-party", grep/.d.ts/DevTools instruction, slim-vs-full builds warning, and F-00079 motivation clause |
| AC2: No `.create(` factory form recommended | ✅ The step cites `Diff2HtmlUI.create(...)` only as the historically wrong call; it never recommends any `.create()` factory form |
| AC3: Sync surfaces NOT edited | ✅ `.claude/agents/` and `.opencode/agents/` are untouched |
| AC4: No collateral changes | ✅ Diff shows only the new step insertion and sequential renumbering; no frontmatter, Mission, Safety Constraints, or other sections altered |

## Blockers or concerns

None. Pre-existing lint/format drift on `main` (unrelated to this CR's scope) was observed in both `format-check` and `lint` gates. These are not introduced by this CR and should be handled separately.

## Notes

- F-00079 self-assess report was not accessible (archived as `.tar.zst`); the motivating incident details (Diff2HtmlUI.create vs new Diff2HtmlUI, slim bundle) were sourced from the CR-00037 design doc and the F-00079 Feature Design doc.
- Did NOT run `iw sync-agents` — post-merge concern only.
- Did NOT edit any sync-surface copies under `.claude/agents/` or `.opencode/agents/`.
