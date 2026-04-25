# CR-00022_S19_Backend_prompt

**Work Item**: CR-00022
**Step**: S19
**Agent**: backend-impl (Phase F — cleanup)

---

## ⛔ Docker / Migrations off-limits

Standard rules. Note: this step **does** delete `.git/worktrees/oss-*` directories — that is a `git worktree remove` / filesystem rmdir operation, NOT a docker operation, and is allowed. It also **does** delete `refs/heads/iw-oss-publish` via `git branch -D` — allowed for cleanup of local refs ONLY in this scoped step. Do not delete any other branch.

## Input Files

- Design (§ Phase F)
- All implementation reports S03..S15

## Output Files

- Deleted: `dashboard/templates/fragments/oss_domain_card.html`
- Deleted (only if confirmed unused after S03/S11): `dashboard/templates/fragments/oss_install_modal.html` (per design Notes — keep if `install` flow stays)
- Modified: `skills/iw-oss-publish/SKILL.md` (final pass — should already be done in S03; confirm)
- Deleted: `skills/iw-oss-publish/references/history_rewrite.md`
- Deleted: `skills/iw-oss-publish/references/fix_recipes.md` (the markdown notes file — NOT the new Python `orch/oss/fix_recipes/` package)
- Modified: `skills/iw-oss-publish/references/modes.md` (drop make_oss + publish sections; keep scan + new fix sections)
- Modified: `skills/iw-oss-publish/references/checks.md` (no scope changes; verify still accurate)
- Modified: `dashboard/utils/oss_copy.py` — remove unused `STATUS_COPY` keys for `make_oss`/`publish` if any; keep DOMAIN_CONTEXT and SEVERITY_IMPACT as fallbacks
- Updated: `docs/IW_AI_Core_Architecture.md` (or wherever OSS module is documented) to reflect new flow
- Local cleanup (one-time housekeeping, see §3): `.git/worktrees/oss-*`, `refs/heads/iw-oss-publish`
- `ai-dev/active/CR-00022/reports/CR-00022_S19_Backend_report.md`

## Context

S03 removed the live code paths; S19 removes the dead documentation, references, and on-disk debris from prior runs. After this step there should be zero remaining mentions of `make_oss`, `publish`, `prep-` branches, or `/tmp/oss-*` worktrees anywhere outside the `evidences/pre/` directory and historical reports.

## Requirements

### 1. Delete dead templates

```bash
git rm dashboard/templates/fragments/oss_domain_card.html
# Conditional — see design Notes:
# git rm dashboard/templates/fragments/oss_install_modal.html  # only if install flow folded
```

If `oss_install_modal.html` is referenced anywhere (`grep -rn oss_install_modal dashboard/`), keep it. Document the decision in the report.

### 2. Skill scope cleanup

```bash
git rm skills/iw-oss-publish/references/history_rewrite.md
git rm skills/iw-oss-publish/references/fix_recipes.md
```

Edit `skills/iw-oss-publish/references/modes.md`:
- Remove the `make_oss` mode section (entire heading + content).
- Remove the `publish` mode section.
- Add a "Per-finding fix" section explaining the new CLI: `uv run iw oss fix <CHECK_ID> [--apply]`.
- Update the comparison table at the top.

Re-confirm `SKILL.md` matches the new shape (S03 should have done the rewrite; verify no leftover references to make_oss/publish).

### 3. Clean local debris

The repo has these stale artifacts from prior prepare/publish runs:

```bash
# 8 worktree directories
ls .git/worktrees/oss-*

# 1 ref
git branch --list iw-oss-publish
```

Clean both:

```bash
# Worktrees — use git worktree remove for each (idempotent)
for wt in .git/worktrees/oss-*; do
  name=$(basename "$wt")
  git worktree remove --force "$name" 2>/dev/null || true
  # Some entries may not have an actual checkout dir, fall back to plain rm
  rm -rf "$wt"
done
git worktree prune

# Branch
git branch -D iw-oss-publish 2>/dev/null || true
```

After cleanup:

```bash
git worktree list --porcelain | grep -i oss-      # expect empty
git branch --list 'iw-oss-publish*' 'iw-oss-publish/prep-*'   # expect empty
ls .git/worktrees/oss-* 2>/dev/null                # expect "No such file"
```

### 4. Doc updates

Search for any docs that reference the old flow:

```bash
grep -rn "make_oss\|oss publish\|iw-oss-publish/prep\|prepare branch" docs/ skills/iw-oss-publish/
```

Update all hits. Specifically:
- `docs/IW_AI_Core_Architecture.md` — if it describes the OSS module, refresh.
- `docs/IW_AI_Core_CLI_Spec.md` — drop `iw oss prepare` and `iw oss publish` entries; add `iw oss fix`.
- `docs/IW_AI_Core_Dashboard_Design.md` — refresh OSS view section.

### 5. Final repo-wide grep

After all cleanups:

```bash
grep -rn "make_oss\|oss prepare\|oss publish\|iw-oss-publish/prep\|_prep_branch_name\|_run_worktree\|WORKTREE_KINDS\|discard_job" \
  --exclude-dir=ai-dev --exclude-dir=.git --exclude-dir=evidences \
  .
```

The only remaining hits should be inside `ai-dev/active/CR-00022/` (this CR's own design + prompts + reports — historical record). Anything else is a residue to fix.

### 6. Verification

```bash
make lint
make test-unit
git status --short
git worktree list --porcelain
git branch --list iw-oss-publish
```

## Project Conventions

- Use `git rm` for tracked-file deletions so the index updates.
- Use plain `rm` for untracked / `.git/`-internal cleanup.
- Document any decisions where the cleanup was conservative (e.g., kept `oss_install_modal.html` because still referenced).

## Output / Report

Report contains:
- Files deleted (with `git rm` confirmation)
- Files modified (skill references, docs)
- Local debris cleanup commands run with output
- Final grep output proving no residual references outside `ai-dev/`
- Open items if any (e.g., docs that need follow-up CR)

End with `iw step-done` / `iw step-fail`.
