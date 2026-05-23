# CR-00079 S01 Backend Report

## Step Summary

**Work Item**: CR-00079 — Generate smaller, single-concern workflow steps in the design-creation skills
**Step**: S01
**Agent**: backend-impl
**Status**: ✅ Complete

## What Was Done

Added the canonical step-granularity rule and a step-sizing checklist to all four affected skills, and added a one-line pointer to the rule in all three design-doc templates.

### Changes to `skills/iw-workflow/SKILL.md`

- Bumped version `2.1.0 → 2.3.0`
- Added a new `## Step Granularity Rule (Canonical)` section immediately after the manifest-schema block (the natural location for step-definition guidance), containing:
  - A precise rule: one cohesive concern per step (≈ one module or closely-related file group)
  - Explicit statement that multi-concern work is split across multiple steps
  - Explicit statement that many small steps are preferred over one large step (the primary failure mode)
  - Explicit statement that docs / skill / plan updates ride-along with code changes get their own step

### Changes to the three design-creation skills

Each skill received:

- Version bumped `2.2.0 → 2.3.0`
- A `### Step-Size Guidance` subsection inserted at the point where the author drafts the plan/manifest:
  - `iw-new-feature`: before the "Implementation Plan Structure" example
  - `iw-new-incident`: before the "Fix Plan Structure" example
  - `iw-new-cr`: inside Step 6 before the manifest generation block

Each subsection contains:
- A one-line reference to the canonical rule in `iw-workflow`
- The four-item checklist (unrelated areas / too many sub-deliverables / ride-along docs / multi-module run)

### Changes to `templates/design/`

Added a one-line blockquote pointer to the rule in the "Agents and Execution Order" table header in:
- `templates/design/Feature_Design_Template.md`
- `templates/design/Issue_Design_Template.md`
- `templates/design/CR_Design_Template.md`

## Files Changed

| File | Action |
|------|--------|
| `skills/iw-workflow/SKILL.md` | Modified (+ canonical rule section, version bump) |
| `skills/iw-new-feature/SKILL.md` | Modified (+ step-size guidance, version bump) |
| `skills/iw-new-incident/SKILL.md` | Modified (+ step-size guidance, version bump) |
| `skills/iw-new-cr/SKILL.md` | Modified (+ step-size guidance, version bump) |
| `.claude/skills/iw-new-feature/SKILL.md` | Synced (byte-identical to master) |
| `.claude/skills/iw-new-incident/SKILL.md` | Synced (byte-identical to master) |
| `.claude/skills/iw-new-cr/SKILL.md` | Synced (byte-identical to master) |
| `.claude/skills/iw-workflow/SKILL.md` | Synced (byte-identical to master) |
| `templates/design/Feature_Design_Template.md` | Modified (+ one-line pointer) |
| `templates/design/Issue_Design_Template.md` | Modified (+ one-line pointer) |
| `templates/design/CR_Design_Template.md` | Modified (+ one-line pointer) |
| `ai-dev/templates/Feature_Design_Template.md` | Synced (byte-identical to master) |
| `ai-dev/templates/Issue_Design_Template.md` | Synced (byte-identical to master) |
| `ai-dev/templates/CR_Design_Template.md` | Synced (byte-identical to master) |

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ ok — all 849 files already formatted |
| `make lint` | ✅ ok — all checks passed |
| `make typecheck` | ⏭️ skipped: markdown-only change, no Python surface |
| `diff -q` (4 skill files) | ✅ All 4 skill files byte-identical to `.claude/skills/` copies |
| `diff -q` (3 template files) | ✅ All 3 template files byte-identical to `ai-dev/templates/` copies |

## Verification

Re-read every edited file. Each contains:
- The canonical rule with the four concrete bullet points
- The four-item step-sizing checklist
- Consistent wording across all three design-creation skills (referencing `iw-workflow` as the single source of truth)

## Notes

### ⚠️ OPERATOR FOLLOW-UP REQUIRED: Sibling-repo propagation

Per `CLAUDE.md`'s skill-sync rule, the four edited `iw-*` skills must also be propagated to the IW-AI-DEV and InnoForge repos after this CR merges. This worktree is isolated and cannot write outside it. The operator must:

1. After this CR's squash-merge lands on `main`, copy the four updated `SKILL.md` files to the same relative paths in IW-AI-DEV and InnoForge.
2. Run `iw sync-skills` in those repos to update the `.claude/skills/` copies there.

### Template sync note

`uv run iw sync-templates` reported "0 updated" for all 4 projects (including iw-ai-core) even though the three template files had been modified. This appears to be because the sync command reads project repo roots from the live database (port 5433), and the iw-ai-core project's `repo_root` entry may point to the main checkout rather than this worktree. The three affected `ai-dev/templates/` files were updated manually via `cp` to ensure byte-identity, which was verified with `diff -q`.

### Markdown-only change

No Python, SQL, or Jinja2 code was modified. The QV gates (unit-tests, integration-tests, etc.) run against the unmodified production code and cannot be affected by this diff.