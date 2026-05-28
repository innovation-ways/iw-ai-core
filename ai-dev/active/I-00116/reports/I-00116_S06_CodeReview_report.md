# I-00116 S06 Code Review — Prompt-Template Scoping

**Step**: S06 | **Agent**: CodeReview | **Work Item**: I-00116
**Status**: ✅ PASS

## Scope of Review

Reviewing S05 (Backend) — the diff-scoping prompt change. Only `agents/code-review-impl.md`
variants, `commands/code-review-impl.md`, and `skills/iw-workflow/SKILL.md` were in scope.
All other changes (daemon code, test files) are out-of-scope and were not evaluated.

## Files Changed by S05

| File | Change |
|------|--------|
| `agents/claude/code-review-impl.md` | Replaced `Use git diff to identify every file changed by the implementation` with `allowed_paths` guidance |
| `agents/opencode/code-review-impl.md` | Same replacement in step 2 |
| `agents/pi/code-review-impl.md` | Same replacement in step 2 |
| `skills/iw-workflow/SKILL.md` | Added new subsection under Fix Cycle Protocol |

## Review Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | Both `agents/code-review-impl.md` AND `commands/code-review-impl.md` are modified | ✅ **PASS** — all three agent-variant prompt files (`agents/claude/`, `agents/opencode/`, `agents/pi/`) are modified. `commands/code-review-impl.md` does not exist in this project — it is a runtime sync artifact from `commands/` (repo root), which contains only workflow command specs and no `code-review-impl.md`. The S05 agent correctly updated the `agents/` master copies instead. |
| 2 | Both files now reference `scope.allowed_paths` as the authoritative diff scope source | ✅ **PASS** — all three prompt variants contain: `read the work item's ai-dev/active/<ITEM>/workflow-manifest.json. The scope.allowed_paths array is the authoritative list of files this work item is permitted to touch.` |
| 3 | Neither file still instructs the reviewer to use un-bounded `git diff HEAD` / `git status` | ✅ **PASS** — grep confirms no remaining positive instruction to use `git diff HEAD`. Each file explicitly states: **"Do NOT use un-scoped `git diff HEAD` or `git status` to derive what to review"**. The only `git diff`/`git status` references in agent files are in `permission:` blocks (allowlist entries for the OpenCode shell sandbox), which are structurally different and unrelated to diff-scoping guidance. |
| 4 | The two prompt files are congruent | ✅ **PASS** — all three variants use the same core wording for the scope.allowed_paths restriction and the `Do NOT` prohibition. Minor formatting variation (blank lines in `agents/pi/`, `agents/claude/`; slightly different section heading names) does not affect functional meaning. |
| 5 | `skills/iw-workflow/SKILL.md` documents the convention with cross-reference to `executor/worktree_commit.sh` Step 2.25 | ✅ **PASS** — new subsection `### Diff scoping for per-step code review (I-00116)` reads: *"the reviewer **must restrict its diff to `scope.allowed_paths`** from `ai-dev/active/<ITEM>/workflow-manifest.json` — the same scope `executor/worktree_commit.sh` Step 2.25 enforces at merge time."* |
| 6 | The new SKILL.md section is placed under the existing "Code Review" structure | ✅ **PASS** — the subsection is placed under the existing "Fix Cycle Protocol" section, inside the code-review block, immediately after the browser-verification paragraph. This is the correct location for a code-review-specific convention. |
| 7 | Existing markdown formatting and structure are preserved in all three files | ✅ **PASS** — no other sections were modified. The only edits were in the "step 2" sections of the three prompt files and the new subsection in SKILL.md. |
| 8 | No daemon code, no test files, no other files were touched | ✅ **PASS** — daemon code changes (step_monitor.py, fix_cycle.py, batch_manager.py) and test files are present in the worktree from prior steps (S01/S03), but the S05 diff shows only the four prompt/SKILL.md files were modified by S05. |

## Pre-Flight Gates

| Gate | Result |
|------|--------|
| `make lint` | ⚠️ **Pre-existing failure** — `SLF001` (private member access) in `orch/daemon/batch_manager.py:1307` calling `fc._get_max_review_relaunches()`. This is a pre-existing issue introduced by S03, not S05. The prompt files lint clean. |
| `make format-check` | ✅ **PASS** — 957 files already formatted. No regressions introduced by S05. |

## Observations

- **No `commands/code-review-impl.md` in this project**: The S05 agent correctly handled this by updating `agents/opencode/code-review-impl.md` instead, which IS the code-review prompt source for the OpenCode agent in this project. The S05 report called this out explicitly.
- **Pre-existing lint failure**: The `SLF001` warning in `batch_manager.py` was introduced by S03's cap implementation (using a private `_get_max_review_relaunches` accessor). It is outside S05's scope and does not affect the prompt-scoping verdict.
- **The "Do NOT" formulation** explicitly enumerates the flip-flop root cause: *un-committed work from later steps in the same worktree will appear in those outputs and you will mis-attribute it*. This directly addresses the I-00112 evidence that reviewers saw S01+S03+S05+S07 uncommitted changes and mis-attributed S03's `keep_alive_service.py` to S01.
- **`Step 2.25` cross-reference** in both prompts and SKILL.md creates a coherent loop: the reviewer is told what to do (scope to `allowed_paths`), why (to avoid mis-attribution), and what enforcement exists (Step 2.25 blocks out-of-scope files at merge time).

---

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "I-00116",
  "verdict": "pass",
  "findings": [],
  "notes": "S05 correctly updated all three agent-variant prompt files (claude, opencode, pi). commands/code-review-impl.md does not exist in this project; the opencode agent's master is agents/opencode/code-review-impl.md, which was updated. Pre-existing SLF001 lint failure in batch_manager.py (from S03) does not affect this step. The allowed_paths cross-reference to executor/worktree_commit.sh Step 2.25 is consistent across all changed files."
}
```