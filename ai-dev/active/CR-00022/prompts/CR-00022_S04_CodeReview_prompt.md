# CR-00022_S04_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S03 (backend-impl — Phase A code removal)
**Review Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Same rules as other prompts. Full policy in `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design + S03 report + every file listed in S03's `files_changed`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S04_CodeReview_report.md`

## Review Checklist

### 1. Completeness of removal

- `WORKTREE_KINDS`, `_run_worktree`, `_prep_branch_name`, `_git_commit_info`, `discard_job` all gone from `dashboard/services/oss_service.py`?
- No remaining call site references those symbols (grep entire repo)?
- `cancel_job` no longer references `worktree_path`?
- `oss_prepare` and `oss_publish` route handlers removed from `dashboard/routers/oss.py`?
- `prepare` and `publish` Click commands removed from `orch/cli/oss_commands.py`?
- No remaining `subprocess` call invokes `git worktree add|remove` or `git branch -D` in OSS code paths?

Use grep extensively:
```bash
grep -rn "WORKTREE_KIND\|_run_worktree\|_prep_branch\|discard_job\|iw-oss-publish/prep" \
  dashboard/ orch/ skills/iw-oss-publish/scripts/ tests/
grep -rn "oss_prepare\|oss_publish\|/oss/prepare\|/oss/publish\|oss prepare\|oss publish" \
  dashboard/ orch/ tests/ docs/
```

Anything found should either be in a test file (S17 will update) or be flagged as a residue to fix.

### 2. `run_job` dispatch correctness

- After removal, does `run_job` route `kind=fix` to a `_run_fix(...)` placeholder that raises `NotImplementedError("Phase C")`?
- Does it still correctly handle `scan` and `install` paths?
- No fall-through to the deleted `WORKTREE_KINDS` branch?

### 3. SKILL.md rewrite

- No mention of `make_oss`, `publish`, or branch creation?
- Constraints section names "MUST NOT switch branches under any circumstances"?
- Per-finding fix section present?
- Original sections (Prerequisites, Project Configuration, Report Template) preserved where still valid?

### 4. Scanner mode handling

- `run_scan` defends against unsupported modes with a clear `ValueError`?
- No remaining import/use of `OssScanMode.make_oss` or `.publish`?

### 5. Forward-compat hooks

- Is `_run_fix` placeholder present so S07 can replace it cleanly?
- Is `oss_commands.py` ready for S07 to add `fix` subcommand without restructure?

### 6. Project conventions

- Routers stay thin, no business logic moved into them?
- Follows `dashboard/CLAUDE.md` (htmx fragments, fragment templates don't extend base.html — N/A here, no template changes)?
- No backwards-compatibility shims (per project rule: don't preserve `_var = None` placeholders for removed symbols)?

### 7. Tests that should be broken

S03's report should list these as expected to fail until S17:
- `test_oss_cli.py`
- `test_oss_dashboard_routes.py`
- `test_oss_persistence.py`
- `test_oss_scanner.py`
- `test_oss_dashboard_service.py`

Cross-check the report against `make test-unit` / `make test-integration -k oss` output. Any test failing for an unexpected reason is a finding.

## Output Report

One section per checklist item, severity per finding, explicit verdict.

End with `iw step-done` or `iw step-fail`.
