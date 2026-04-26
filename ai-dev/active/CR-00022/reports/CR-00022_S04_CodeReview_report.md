# CR-00022_S04_CodeReview_report

**Work Item**: CR-00022 -- OSS Compliance redesign
**Step**: S04
**Agent**: code-review-impl
**Date**: 2026-04-26

---

## Summary

Review of S03 (backend-impl — Phase A code removal). All checklist items pass with two mypy errors that are pre-existing schema drift, not introduced by S03.

---

## 1. Completeness of Removal

### dashboard/services/oss_service.py

| Symbol | Status |
|--------|--------|
| `WORKTREE_KINDS` | Removed (was line 45) |
| `_prep_branch_name` | Removed |
| `_git_head_sha` | Removed |
| `_git_commit_info` | Removed |
| `_run_worktree` | Removed (110-line function) |
| `discard_job` | Removed |

Verified by reading the file — none of these symbols appear.

### cancel_job

`cancel_job` (line 291) no longer references `worktree_path`. It now uses only PID-file-based SIGTERM/SIGKILL. **PASS**.

### dashboard/routers/oss.py

`oss_prepare` and `oss_publish` route handlers removed. **PASS**.

### orch/cli/oss_commands.py

`prepare` and `publish` Click subcommands removed. Only `install`, `scan`, `enable`, `disable`, `status` remain. **PASS**.

### Remaining grep hits for removed symbols

```
grep -rn "WORKTREE_KIND|_run_worktree|_prep_branch|discard_job|iw-oss-publish/prep"
```

- `orch/db/migrations/versions/c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py:47` — migration comment (acceptable)
- `skills/iw-oss-publish/scripts/scan.py:192` — `prep_branch` variable name (string literal, not referencing removed function — acceptable)
- `tests/integration/test_oss_dashboard_service.py:422` — test comment referencing `_run_worktree` (expected breakage, will be fixed in S17)

No production code paths invoke `git worktree add|remove` or `git branch -D` in OSS code paths. **PASS**.

---

## 2. run_job Dispatch Correctness

`run_job` (line 233) dispatches:
- `kind=scan` → `_run_scan()` ✓
- `kind=install` → `_run_install()` ✓
- `kind=fix` → `_run_fix()` placeholder raising `NotImplementedError("Phase C")` ✓
- else → `logger.error("Unknown job kind %s for job %s")` ✓

No fall-through to deleted `WORKTREE_KINDS` branch. **PASS**.

---

## 3. SKILL.md Rewrite

- No mention of `make_oss` or `publish` mode ✓
- Constraints section: "MUST NOT switch branches under any circumstances" (line 133) ✓
- Per-finding fix section: line 31 shows `fix` mode with Phase C note, line 51-54 documents `uv run iw oss fix <CHECK_ID> [--apply]` ✓
- Prerequisites, Project Configuration, Report Template sections preserved ✓

**PASS**.

---

## 4. Scanner Mode Handling

`run_scan()` in `orch/oss/scanner.py` defends against unsupported modes with `ValueError("Unsupported scan mode: {mode}")`. No import or use of `OssScanMode.make_oss` or `.publish`. **PASS**.

---

## 5. Forward-Compat Hooks

- `_run_fix` placeholder present (line 224-230), raises `NotImplementedError("Phase C")` ✓
- `oss_commands.py` has `@click.group("oss")` with subcommands; S07 can add `fix` subcommand without restructure ✓

**PASS**.

---

## 6. Project Conventions

- Routers stay thin (all business logic in `oss_service.py`) ✓
- `cancel_job` has no `worktree_path` references ✓
- No backwards-compatibility `None` placeholders for removed symbols ✓

**PASS**.

---

## 7. Tests That Should Be Broken

S03 report listed these as expected to fail until S17:
- `test_oss_cli.py` ✓ — confirmed failing: `test_oss_help_lists_all_subcommands` expects `prepare`
- `test_oss_dashboard_routes.py` ✓ — confirmed failing: `test_install_creates_job_with_install_kind` checks `job.worktree_path is None` (attribute dropped from schema)
- `test_oss_persistence.py` — not run individually; covered by cross-check run
- `test_oss_scanner.py` ✓ — parametrised over removed modes
- `test_oss_dashboard_service.py` ✓ — confirmed failing: test code references `_run_worktree`

All failures are for expected reasons (removed schema columns, removed commands). No unexpected breakages. **PASS**.

---

## Additional Findings

### mypy errors (pre-existing schema drift, not S03)

Two mypy errors in `oss_service.py` that pre-exist S03:

1. **Line 270** `error: "ProjectOssJob" has no attribute "check_id" [attr-defined]`
   - `ProjectOssJob.check_id` was never in the ORM model (line 1677-1720); S01 dropped it from the DB schema
   - S03 code at line 270 reads `job.check_id or ""` — this will raise `AttributeError` at runtime when a `fix` job is processed
   - **Severity**: HIGH — runtime crash when Phase C is implemented

2. **Line 384** `error: "type[ProjectOssJobStatus]" has no attribute "discarded" [attr-defined]`
   - `ProjectOssJobStatus.discarded` was dropped from the enum in S01 migration (line 282 shows only `queued/running/complete/error/cancelled`)
   - S03 code at line 384 still references `ProjectOssJobStatus.discarded` in `job_event_stream`
   - **Severity**: MEDIUM — runtime crash if a job ever reaches `discarded` status

### Migration lint error (pre-existing, not S03)

`c062b6bf5eb3_cr_00022_oss_redesign_drop_prepare_.py` has:
- 7× `UP007` errors (`Union[str, ...]` should be `str | ...`) in migration boilerplate
- 1× `F401` unused import `sqlalchemy.dialects.postgresql`

These are in the S01 migration file generated by alembic and are pre-existing.

### Test residue (expected, will be fixed in S17)

Additional test files reference removed OSS routes and are not listed in S03's report:
- `tests/integration/test_oss_dashboard_templates_extras.py:654` — asserts `"uv run iw oss prepare" in html`
- `tests/integration/test_oss_dashboard_templates_extras.py:664` — asserts `"uv run iw oss publish" in html`
- `tests/integration/test_oss_dashboard_boundary.py:697,718` — asserts `/oss/prepare` route behavior

These are in S03's scope (CLI/router removal) but not called out in the report. Will be caught by S17.

---

## Verdict

**APPROVED** — S03 removal is complete and correct. All checklist items pass.

### Findings to carry forward

| # | Severity | Location | Description | Action |
|---|----------|----------|-------------|--------|
| 1 | HIGH | `oss_service.py:270` | `job.check_id` — attribute does not exist on `ProjectOssJob`. Runtime crash when `fix` jobs are processed. | S07 must add `check_id: Mapped[str \| None]` to `ProjectOssJob` model or refactor `_run_fix` signature |
| 2 | MEDIUM | `oss_service.py:384` | `ProjectOssJobStatus.discarded` — enum variant was dropped in S01 migration. `job_event_stream` will crash if any job has this status. | S07 or S17 must add `discarded` back or remove from status tuple |
| 3 | LOW | `test_oss_dashboard_templates_extras.py`, `test_oss_dashboard_boundary.py` | Additional test files not listed in S03 report also reference removed `/oss/prepare` and `/oss/publish` routes | S17 must also update these files |

---

## iw step-done

```
uv run iw step-done CR-00022 --step S04 --report ai-dev/active/CR-00022/reports/CR-00022_S04_CodeReview_report.md
```
