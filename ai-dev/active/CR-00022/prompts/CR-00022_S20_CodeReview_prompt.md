# CR-00022_S20_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S19 (Phase F — cleanup)
**Review Step**: S20
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S19 report
- Repo-wide grep targets per checklist

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S20_CodeReview_report.md`

## Review Checklist

### 1. No residual references to old flow

```bash
grep -rn "make_oss\|oss prepare\|oss publish\|iw-oss-publish/prep\|_prep_branch_name\|_run_worktree\|WORKTREE_KINDS\|discard_job" \
  --exclude-dir=ai-dev --exclude-dir=.git --exclude-dir=evidences \
  .
```

ANY hit outside `ai-dev/active/CR-00022/` is a HIGH finding. The historical reports in this CR's directory may legitimately mention these strings.

### 2. Worktree / branch cleanup

```bash
git worktree list --porcelain | grep -i oss-      # expect empty
git branch --list 'iw-oss-publish*' 'iw-oss-publish/prep-*'   # expect empty
ls .git/worktrees/oss-* 2>/dev/null                # expect "No such file"
```

Any remaining oss-prefixed worktree or branch is a finding.

### 3. Skill / docs consistency

- `skills/iw-oss-publish/SKILL.md` no longer mentions `make_oss` / `publish` / "Three Modes"?
- `references/modes.md` reflects the new flow (scan + fix only)?
- `docs/IW_AI_Core_CLI_Spec.md` lists `iw oss fix`, no `prepare` / `publish`?
- `docs/IW_AI_Core_Architecture.md` updated where OSS is described?

### 4. Conditional deletes

- `oss_install_modal.html` — kept or deleted? Justification in the S19 report? If deleted, no template includes it (`grep -rn oss_install_modal dashboard/`)?

### 5. Tests still green

```bash
make test-unit
```

Quick smoke — full integration runs in QV gates.

### 6. No accidental deletions

- `git status` shows no unintended file removals?
- `dashboard/utils/oss_copy.py` retained as fallback (DOMAIN_CONTEXT + SEVERITY_IMPACT still imported by routers)?

## Output Report

Findings + verdict + step-done/fail.
