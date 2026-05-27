# I-00116_S05_Backend_prompt

**Work Item**: I-00116
**Step**: S05
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration.

## Scope (`allowed_paths`)

You MAY only modify:

- `agents/code-review-impl.md`
- `commands/code-review-impl.md`
- `skills/iw-workflow/SKILL.md`

NO daemon code, no tests. This step is purely a prompt + documentation update.

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design** (read §"Root Cause Analysis" sub-bug 2 + "Fix Plan" S05): `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **The master prompt files** you will edit (read first, understand structure)
- `executor/worktree_commit.sh` — Step 2.25 enforces `allowed_paths` at merge time. Your prompt change should align reviewer scope with what `worktree_commit.sh` already enforces, so the reviewer's perception matches the merge-time enforcement.

## Output Files

- `agents/code-review-impl.md` (modified)
- `commands/code-review-impl.md` (modified)
- `skills/iw-workflow/SKILL.md` (modified)
- Step report: `ai-dev/active/I-00116/reports/I-00116_S05_Backend_report.md`

## Context

When a code-review agent is re-launched (because some downstream step's fix cycle finished), it sees a `git diff HEAD` that contains un-committed changes from later steps in the workflow. The reviewer then mis-attributes those changes to the step it's reviewing. In I-00112, this caused S02 to verdict `pass` on its first run (only saw S01 work) and `fail` on its second run (saw S01+S03+S05+S07 work and blamed S01 for S03's backend changes). The fix-cycle that followed reverted S03's correct backend work.

The fix is structural: tell the reviewer that "the files YOU are responsible for" are exactly the globs in `scope.allowed_paths` for the step being reviewed — not the un-bounded `git diff HEAD`. This is the same scope `executor/worktree_commit.sh` enforces at merge time.

## Requirements

### 1. Modify the master review prompt — `agents/code-review-impl.md`

Locate the section that instructs the reviewer how to identify "files changed by this step" (or equivalent). Replace any guidance to use `git diff HEAD` / `git status` un-bounded with explicit `scope.allowed_paths` guidance:

> **Files you review**: read the work item's `ai-dev/active/<ITEM>/workflow-manifest.json`. The `scope.allowed_paths` array is the authoritative list of files this work item is permitted to touch. For your per-step review, restrict your diff inspection to files matching the step-specific subset (declared in the step's prompt under "Scope (`allowed_paths`)") AND only consider lines added/modified since the previous committed boundary for that step.
>
> **Do NOT** use un-scoped `git diff HEAD` or `git status` to derive what to review — un-committed work from later steps in the same worktree will appear in those outputs and you will mis-attribute it. The merge-time enforcement in `executor/worktree_commit.sh` Step 2.25 rejects any file outside `allowed_paths`, so anything you see outside that scope is either (a) someone else's step's work (ignore it), or (b) a scope violation by the step you're reviewing (CRITICAL finding).

Preserve any project-specific conventions and existing formatting; only replace the diff-scoping guidance.

### 2. Apply the same change to `commands/code-review-impl.md`

This is the daemon-synced copy. Both files must be congruent — any drift will be caught at the next `iw sync-agents` run.

### 3. Document the convention in `skills/iw-workflow/SKILL.md`

Add a short subsection under the "Code Review" section (or equivalent — read the file's structure first). Title: `### Diff scoping for per-step code review (I-00116)`. Content: 2–4 sentences pointing to the manifest's `scope.allowed_paths` as authoritative, and cross-referencing `executor/worktree_commit.sh`'s Step 2.25 enforcement.

### 4. RED → GREEN

S07 owns `tests/unit/test_review_prompt_scope.py`. RED reasoning for your report:

> "Pre-fix the master prompts at `agents/code-review-impl.md` and `commands/code-review-impl.md` contain no reference to `scope.allowed_paths`. The S07 prompt-scope test will fail because `assert 'allowed_paths' in prompt_text` returns False."

### 5. Post-edit gate (MANDATORY)

```bash
make format-check
make lint
```

If `make lint` includes a markdown linter and it fires on your edits, fix the lint before exit.

## Constraints

- Touch ONLY the three named files.
- Do NOT touch any daemon code.
- Do NOT touch any test files.
- Preserve the existing markdown structure and style of each file.
- Both master prompt files (`agents/...` and `commands/...`) MUST receive identical guidance.

## Step Done Contract

Your report MUST contain:
```json
{"step": "S05", "agent": "Backend", "work_item": "I-00116",
 "files_changed": ["agents/code-review-impl.md", "commands/code-review-impl.md", "skills/iw-workflow/SKILL.md"],
 "tdd_red_evidence": "...",
 "post_edit_gates": {"make format-check": "pass", "make lint": "pass"},
 "notes": "..."}
```

After writing the report, call `iw step-done S05 --report ai-dev/active/I-00116/reports/I-00116_S05_Backend_report.md`. **DO NOT exit without calling `iw step-done`.**
