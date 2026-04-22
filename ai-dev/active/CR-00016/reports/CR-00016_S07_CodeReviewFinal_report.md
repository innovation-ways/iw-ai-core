# CR-00016 S07 — Code Review Final Report

## What was done

Cross-layer final review verifying end-to-end AC satisfaction and sibling-repo propagation documentation.

## Files changed

All files are unstaged pending commit (in worktree, not yet committed):

| File | Action |
|------|--------|
| `docs/IW_AI_Core_Agent_Constraints.md` | Created (untracked) |
| `docs/IW_AI_Core_DB_Setup.md` | Created (untracked, from CR-00015) |
| `ai-dev/templates/*.md` (11 files) | Modified — Docker rule added |
| `.claude/skills/iw-workflow/SKILL.md` | Modified — Global agent constraints section added |
| `skills/iw-workflow/SKILL.md` | Modified — Global agent constraints section added |
| `CLAUDE.md` | Modified — Critical Rules bullet added |
| `orch/CLAUDE.md` | Modified — Critical Rules bullet added |
| `dashboard/CLAUDE.md` | Modified — Critical Rules bullet added |
| `executor/CLAUDE.md` | Modified — Critical Rules bullet added |
| `tests/CLAUDE.md` | Modified — Critical Rules bullet added + testcontainer exception note |
| `tests/integration/test_agent_constraints_coverage.py` | Created (untracked) |

## Acceptance Criteria Verification

### AC1 (policy doc authoritative) — PASS
`docs/IW_AI_Core_Agent_Constraints.md` exists. It contains R1 verbatim, is structured with R2 reserved, and has an "Adding rules" section that explains how to extend with new rules. All 5 CLAUDE.md files link to it.

### AC2 (every template has the marker) — PASS
All 11 templates verified with grep; each contains `⛔ Docker is off-limits` exactly once. Rule text is byte-for-byte identical across all 11 files (extracted and diffed).

### AC3 (every CLAUDE.md has the rule + link) — PASS
All 5 CLAUDE.md files (root, orch/, dashboard/, executor/, tests/) contain a Critical Rules bullet with "docker" keyword and a link to `docs/IW_AI_Core_Agent_Constraints.md`.

### AC4 (iw-workflow surfaces the rule) — PASS
`.claude/skills/iw-workflow/SKILL.md` has a "Global agent constraints" section (lines 12–25) that:
- Names the policy doc path
- Explicitly states "⛔ Docker is off-limits" rule applies to every agent
- Provides a bullet summary of the prohibition list
- Notes the three allowed exceptions

The `skills/iw-workflow/SKILL.md` master copy is also updated.

### AC5 (grep test catches drift) — PASS
- All 19 test cases PASS on current state
- Mutation test 1: removed marker from `Feature_Design_Template.md` → test fails with `AssertionError: ai-dev/templates/Feature_Design_Template.md is missing the Docker rule marker ('⛔ Docker is off-limits')` — correct failure
- Mutation test 2: removed marker from `Implementation_Prompt_Template.md` → test fails with correct message — consistent failure mode across files
- Test correctly identifies the offending file by name in the failure message

### AC6 (no regression) — PARTIAL (pre-existing lint errors)
The lint errors found (`ARG001` in `orch/cli/item_commands.py:593` and `E501` in `tests/integration/test_code_qa_routes.py:226`) are pre-existing on main and not caused by CR-00016. Verified by running ruff on CR-00016 files only → All checks passed.

CR-00014 and CR-00015 worktree files are not modified by this branch.

## Rule Text Drift Audit — PASS
Extracted the Docker rule block from `Feature_Design_Template.md`, `CodeReview_Prompt_Template.md`, and `Implementation_Prompt_Template.md`. Diffed byte-for-byte — all three are identical. No drift.

## Link Integrity — PASS
All internal links to `docs/IW_AI_Core_Agent_Constraints.md` resolve:
- All 5 CLAUDE.md files link to it
- `docs/IW_AI_Core_DB_Setup.md` links to it
- The policy doc links to `docs/IW_AI_Core_DB_Setup.md`

No broken outbound links in the policy doc.

## Future-Proofing — PASS
The policy doc's "Adding rules" section (lines 54–60) specifies:
- New rules need an ID (R2, R3, ...)
- Unique marker phrase for the grep test
- Must link from every touch-point (templates + CLAUDE.md files)

Clear enough for a future CR to add R2 (e.g. "never modify /opt") following the same pattern.

## Orchestrator Behavioral Sanity — PASS
Grep'd `orch/daemon/` for preprocessing that could strip `##` sections:
- Found no stripping/preprocessing of prompt sections
- The `strip()` calls found are for PID file reading, merge error messages, and output formatting — none touch template content
- Template files are read directly and injected as prompt text without transformation

The `## ⛔ Docker is off-limits` section in templates will render in full in agent prompts.

## Sibling-Repo Propagation List

The following files must be propagated to IW-AI-DEV and InnoForge (or any other sibling repos running IW AI Core):

| File path | Sync action | Notes |
|---|---|---|
| `docs/IW_AI_Core_Agent_Constraints.md` | **Copy verbatim** | Universal rule — applies to every IW AI Core deployment. No adaptation needed. |
| `ai-dev/templates/CR_Design_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/Feature_Design_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/Issue_Design_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/CodeReview_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/CodeReview_FIX_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/CodeReview_Final_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/QualityValidation_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `ai-dev/templates/QVBrowser_Prompt_Template.md` | Copy verbatim | Project-agnostic template |
| `.claude/skills/iw-workflow/SKILL.md` | **Merge** | Sibling repos may have diverged. Apply the "Global agent constraints" section (lines 12–25) as a new section; preserve any existing repo-specific content before/after. |
| `skills/iw-workflow/SKILL.md` | **Merge** | Same as above — master copy sync. |
| `CLAUDE.md` (root) | **Adapt** | Each sibling repo has its own CLAUDE.md. Add the Critical Rules bullet about Docker (verbatim bullet text). Do not copy the entire file — just add the bullet in the Critical Rules section. |
| `orch/CLAUDE.md` | **Adapt** (if present) | Only applicable if sibling has an `orch/` subdirectory with its own CLAUDE.md. Add bullet. |
| `dashboard/CLAUDE.md` | **Adapt** (if present) | Only applicable if sibling has a `dashboard/` subdirectory with its own CLAUDE.md. Add bullet. |
| `executor/CLAUDE.md` | **Adapt** (if present) | Only applicable if sibling has an `executor/` subdirectory with its own CLAUDE.md. Add bullet. |
| `tests/CLAUDE.md` | **Adapt** (if present) | Only applicable if sibling has a `tests/` subdirectory with its own CLAUDE.md. Add bullet with testcontainer exception note. |
| `tests/integration/test_agent_constraints_coverage.py` | **Copy verbatim** | The grep test is project-agnostic; copy to sibling's `tests/integration/` directory. |
| `docs/IW_AI_Core_DB_Setup.md` | **Copy verbatim** | Contains the incident reference that motivates R1. Universal context. |

**Do NOT copy**: `ai-dev/active/CR-00016/` (work-item-specific, not template infrastructure).

## Findings

| Severity | File | Issue | Fix applied |
|---|---|---|---|
| — | — | No critical/high issues found | — |

## Test Summary

```
uv run pytest tests/integration/test_agent_constraints_coverage.py -v
19 passed, 5 warnings (pre-existing pytest mark warnings only)
```

Lint on CR-00016 files: `All checks passed!`
Pre-existing lint errors on main: `ARG001` + `E501` (not from CR-00016)

## Notes

- Worktree had an un-stashed stash (`stash@{0}`) that was holding all CR-00016 implementation changes. These have been popped and are now visible as unstaged modifications. The changes are complete.
- The `make check` failure is entirely attributable to pre-existing lint errors on main, not to any CR-00016 change.
- The branch `agent/CR-00016-agent-prompt-hardening-docker-` is at the same commit as `main` (both `db54e3f`) — the design package was committed but the implementation was in an un-stashed stash. Now restored as unstaged work.