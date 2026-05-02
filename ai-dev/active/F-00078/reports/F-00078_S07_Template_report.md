# F-00078 S07 Template Report

**Step**: S07 (template-impl)
**Work Item**: F-00078 -- Per-project self-assessment step with copy-paste fix prompts
**Date**: 2026-05-02

## What Was Done

### 1. Migrated `skills/iw-item-analyze/SKILL.md` to OpenCode-compatible

- Removed `allowed-tools:` and `argument-hint:` frontmatter fields (CC-only)
- Added `compatibility: opencode` per the OpenCode guide's example
- Replaced all `$ARGUMENTS` references with `$IW_ITEM_ID` env var
- Added **Phase 0.5 — Inventory log sizes**: instructs agents to use `tail -500`, `head -200`, `grep -E` for logs > 1 MB
- **Phase 3 — Output** changed from chat-only to two-file output:
  - `ai-dev/work/<ID>/reports/<ID>_self_assess_report.md` — narrative
  - `ai-dev/work/<ID>/reports/<ID>_self_assess_findings.json` — structured JSON with `bottom_line`, `coverage_notes`, and `findings[]` array
- Added constraints for: atomic writes, `target` field (`"iw-ai-core"` or `"project"`), `paste_prompt` one-liner, `coverage_notes` for log-size honesty, read-only boundary
- Bumped version to `1.1.0`

### 2. Updated three design skills for conditional self_assess injection

Each of `skills/iw-new-feature/SKILL.md`, `skills/iw-new-cr/SKILL.md`, `skills/iw-new-incident/SKILL.md` now has:

- A **Sub-step: Check project self_assess flag** section before manifest generation
- Reads `projects.toml` via `python3 -c "import tomllib..."` + `uv run iw current-project`
- If `self_assess = true`: injects `self-assess-impl` step immediately before the first `qv-gate` step
- Generates `prompts/{ID}_S{NN}_SelfAssess_prompt.md` by copying from `ai-dev/templates/SelfAssess_Prompt_Template.md`
- Added the deterministic injection constraint: "MUST inject the self_assess step iff the project's `projects.toml` has `self_assess = true`. Determinism is required (Invariant 6 in F-00078)."

### 3. Created `templates/design/SelfAssess_Prompt_Template.md`

New prompt template following the Implementation_Prompt_Template structure:
- Docker / Migration prohibition headers
- Input: `$IW_ITEM_ID` env var, worktree logs dir, item reports dir
- Output: `_self_assess_report.md` + `_self_assess_findings.json`
- Instructs agent to **use the `iw-item-analyze` skill** (not re-implement inline)
- Documents soft-step semantics (failure does NOT block merge)
- Includes Subagent Result Contract with `{ID}` and `{NN}` placeholders

### 3b. Extended canonical agent table in `skills/iw-workflow/SKILL.md`

- Added `| SelfAssess | self-assess-impl |` to the Agent Mapping table
- Placed after `Template` and before `CodeReview_*` (implementation agents grouped together)
- Added soft-step documentation paragraph after the table

### 4. Synced to `.claude/skills/` and `ai-dev/templates/`

- All five modified `skills/*/SKILL.md` files copied to `.claude/skills/<name>/SKILL.md`
- `SelfAssess_Prompt_Template.md` copied to `ai-dev/templates/SelfAssess_Prompt_Template.md`
- All copies are byte-identical to their masters (sync invariant verified by new unit tests)

### 5. TDD test: `tests/unit/test_skill_files.py`

New test file covering:
- `iw-item-analyze` has no `allowed-tools`/`argument-hint`, uses `$IW_ITEM_ID`, references `_self_assess_findings.json`, has `compatibility: opencode`, has Phase 0.5
- `SelfAssess_Prompt_Template.md` exists with `{ID}` and `{NN}` placeholders and mentions `iw-item-analyze`
- `iw-workflow` SKILL.md has `self-assess-impl` in table and documents soft-step behavior
- All three design skills mention `self-assess-impl` and `projects.toml`
- Sync byte-identicity: `skills/` master == `.claude/skills/` synced copy for all 5 skills
- `ai-dev/templates/SelfAssess_Prompt_Template.md` matches master

**Result**: 25 passed, 0 failed

## Files Changed

| File | Change |
|------|--------|
| `skills/iw-item-analyze/SKILL.md` | Migrated to OpenCode-compatible + new output contract |
| `skills/iw-new-feature/SKILL.md` | Added conditional self_assess injection |
| `skills/iw-new-cr/SKILL.md` | Added conditional self_assess injection |
| `skills/iw-new-incident/SKILL.md` | Added conditional self_assess injection |
| `skills/iw-workflow/SKILL.md` | Added SelfAssess row + soft-step docs |
| `templates/design/SelfAssess_Prompt_Template.md` | NEW |
| `.claude/skills/iw-item-analyze/SKILL.md` | Synced copy |
| `.claude/skills/iw-new-feature/SKILL.md` | Synced copy |
| `.claude/skills/iw-new-cr/SKILL.md` | Synced copy |
| `.claude/skills/iw-new-incident/SKILL.md` | Synced copy |
| `.claude/skills/iw-workflow/SKILL.md` | Synced copy |
| `ai-dev/templates/SelfAssess_Prompt_Template.md` | Synced copy |
| `tests/unit/test_skill_files.py` | NEW TDD tests |

## Pre-flight Results

- `make format`: skipped (Python files already formatted; ruff format touched only unrelated orch/ files)
- `make typecheck`: ok (0 errors in 214 source files)
- `make lint`: ok (All checks passed)

## Test Results

```
uv run pytest tests/unit/test_skill_files.py -v
======================== 25 passed, 1 warning in 6.04s =========================
```

## Sync Notes

- The `iw skills sync` and `iw sync-templates` commands (defined in `orch/cli/skills_commands.py`) copy masters to `.claude/skills/` and `ai-dev/templates/` respectively
- **Byte-identical copies**: Verified by `test_skills_sync_is_byte_identical` and `test_ai_dev_templates_self_assess_matches_master`
- The sync command should ideally run as part of merge pipeline so that when F-00078 merges, downstream worktrees get the updated skills automatically. However, `iw skills sync` is currently a manual/dev command — the design relies on the daemon/worktree bootstrap to pick up skills from `skills/` master via `iw sync-skills` per `skills/` → `.claude/skills/` direction.

## Blockers

None.

## Observations

- The test file path calculation (`parents[2]`) resolves correctly to `.worktrees/F-00078`
- The `make format` failure on `orch/cli/step_commands.py` and `orch/daemon/batch_manager.py` is pre-existing (not caused by this step) — those files were re-formatted by a prior step
- The soft-step documentation in `iw-workflow` SKILL.md explicitly documents the "no fix cycles" and "coerced to completed" semantics for `self-assess-impl`
