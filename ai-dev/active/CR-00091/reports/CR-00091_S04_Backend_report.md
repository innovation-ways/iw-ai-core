# CR-00091 S04 Backend Report

## What was done
- Added the CR-00091 migration-generation convention to `CLAUDE.md` Critical Rules.
- Added the same convention note to the `db/migrations/` entry in `orch/CLAUDE.md`.
- Inserted the migration convention blockquote immediately before migration-check guidance in:
  - `skills/iw-new-cr/SKILL.md`
  - `skills/iw-new-feature/SKILL.md`
  - `skills/iw-new-incident/SKILL.md`
- Applied the same updates to mirrored skill files under `.claude/skills/`.
- Added migration-generation note to `ai-dev/templates/Implementation_Prompt_Template.md` near existing alembic generation guidance.
- Ran `uv run iw sync-skills` (all skills reported as project overrides/skipped in this worktree).

## Files changed
- `CLAUDE.md`
- `orch/CLAUDE.md`
- `skills/iw-new-cr/SKILL.md`
- `skills/iw-new-feature/SKILL.md`
- `skills/iw-new-incident/SKILL.md`
- `.claude/skills/iw-new-cr/SKILL.md`
- `.claude/skills/iw-new-feature/SKILL.md`
- `.claude/skills/iw-new-incident/SKILL.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`

## Test results
- Not applicable (documentation-only step).
- Preflight run:
  - `make lint` ✅

## Issues / observations
- `uv run iw sync-skills` reported all skills as project overrides and skipped copy; mirror files were updated directly to keep master+mirror in sync for commit.
