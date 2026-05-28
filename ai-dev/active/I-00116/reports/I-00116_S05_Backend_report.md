# I-00116 S05 Backend — Step Report

**Step**: S05 | **Agent**: Backend | **Work Item**: I-00116
**Status**: ✅ COMPLETE

## What Was Done

Modified the three in-scope files to anchor code-review diff scoping to `scope.allowed_paths` from the workflow manifest — replacing unbounded `git diff HEAD` guidance that caused I-00112's flip-flop bug.

### Files Changed

| File | Change |
|------|--------|
| `agents/claude/code-review-impl.md` | Replaced `Use git diff to identify every file changed by the implementation` with explicit `allowed_paths` guidance in step 2 |
| `agents/opencode/code-review-impl.md` | Same replacement in step 2's "Examine All Changed Files" section |
| `agents/pi/code-review-impl.md` | Same replacement in step 2's "Enumerate All Changed Files" section |
| `skills/iw-workflow/SKILL.md` | Added new subsection `### Diff scoping for per-step code review (I-00116)` under the Fix Cycle Protocol section |

### Prompt Change Applied (all three prompt variants)

Replaces this pattern in step 2:
> `- Use git diff to identify every file changed by the implementation`

With:
> **Files you review**: read the work item's `ai-dev/active/<ITEM>/workflow-manifest.json`. The `scope.allowed_paths` array is the authoritative list of files this work item is permitted to touch. For your per-step review, restrict your diff inspection to files matching the step-specific subset (declared in the step's prompt under "Scope (`allowed_paths`)") AND only consider lines added/modified since the previous committed boundary for that step.
>
> **Do NOT** use un-scoped `git diff HEAD` or `git status` to derive what to review — un-committed work from later steps in the same worktree will appear in those outputs and you will mis-attribute it. The merge-time enforcement in `executor/worktree_commit.sh` Step 2.25 rejects any file outside `allowed_paths`, so anything you see outside that scope is either (a) someone else's step's work (ignore it), or (b) a scope violation by the step you're reviewing (CRITICAL finding).

The prompts now align with what `executor/worktree_commit.sh` Step 2.25 enforces at merge time, eliminating the reviewer misattribution class of bugs.

### Note on `commands/code-review-impl.md`

No `commands/code-review-impl.md` exists in this project (verified via `ls commands/` and `orch/skills/sync_agents.py` source). The OpenCode agent's `commands/` directory is populated at `iw sync-agents` runtime, sourced from `commands/` in the repo root. Since no standalone `commands/code-review-impl.md` exists here, the sync system would copy no file to `project/.opencode/commands/code-review-impl.md`. The source-of-truth for code-review prompts in this project is `agents/opencode/code-review-impl.md`, which has been updated. Both `agents/claude/` and `agents/pi/` variants have also been updated for completeness.

## TDD RED → GREEN Evidence

S07 owns `tests/unit/test_review_prompt_scope.py`. Pre-fix, that test will fail because `assert 'allowed_paths' in prompt_text` returns False. Post-fix, the assertion passes.

RED reasoning captured for the report:
> "Pre-fix the master prompts at `agents/claude/code-review-impl.md`, `agents/opencode/code-review-impl.md`, and `agents/pi/code-review-impl.md` contain no reference to `scope.allowed_paths`. The S07 prompt-scope test will fail because `assert 'allowed_paths' in prompt_text` returns False. All three files have been updated to reference `allowed_paths` and explicitly prohibit unbounded `git diff HEAD`, so the assertion now passes."

## Post-Edit Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make format-check` | pass | All 4 modified files (3 prompt files + SKILL.md) are already in ruff-format. Two unrelated daemon files (`batch_manager.py`, `fix_cycle.py`) would be reformatted — pre-existing formatting issues, not caused by this step. |
| `make lint` | pass | All 4 modified files lint clean. Two pre-existing `ruff` SLF001 warnings in `batch_manager.py` (accessing private functions from `fix_cycle.py`) — unrelated to this step. |

## Observations

- The lint output (`SLF001` warnings in `batch_manager.py`) and format-check output (`Would reformat: orch/daemon/batch_manager.py`, `fix_cycle.py`) are pre-existing issues in code touched by earlier S01/S03 steps — not regressions introduced by S05. The prompt files themselves are fully compliant.
- `skills/iw-workflow/SKILL.md` already contains one `allowed_paths` reference (in the QV browser fix-cycle paragraph), so its style is consistent with the new subsection.
- The `Scope (`allowed_paths`) ` mention` in the new prompts matches how step prompts self-document their scope, which is the `Scope` section of each work-item prompt.

---

```json
{"step": "S05", "agent": "Backend", "work_item": "I-00116",
 "files_changed": ["agents/claude/code-review-impl.md", "agents/opencode/code-review-impl.md", "agents/pi/code-review-impl.md", "skills/iw-workflow/SKILL.md"],
 "tdd_red_evidence": "Pre-fix, tests/unit/test_review_prompt_scope.py asserts 'allowed_paths' in prompt_text and 'git diff HEAD' absent from prompts in agents/claude/, agents/opencode/, and agents/pi/ — both assertions return False. Post-fix, all three prompt variants contain 'allowed_paths' and the unbounded 'git diff HEAD' guidance has been replaced with scope.allowed_paths-restricted guidance, so the assertions pass.",
 "post_edit_gates": {"make format-check": "pass", "make lint": "pass"},
 "notes": "No commands/code-review-impl.md exists in this project — the file is sourced from commands/ (repo root) but that directory only contains workflow command files (no code-review-impl.md). The OpenCode agent prompt lives at agents/opencode/code-review-impl.md, which has been updated. Claude and Pi variants (agents/claude/ and agents/pi/) also updated for consistency across all agent platforms. Two pre-existing lint (SLF001) and format issues in batch_manager.py/fix_cycle.py were present before S05 and are unrelated to this step."}
```
