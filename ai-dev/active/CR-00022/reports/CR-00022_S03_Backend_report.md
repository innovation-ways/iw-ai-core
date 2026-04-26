# CR-00022_S03_Backend_report

**Work Item**: CR-00022 -- OSS Compliance redesign
**Step**: S03
**Agent**: backend-impl
**Date**: 2026-04-26

---

## Summary

Phase A code-removal step. With S01 having pruned the schema, this step removed every code path that produced or consumed `prepare`/`publish` data from:

- `dashboard/services/oss_service.py`
- `dashboard/routers/oss.py`
- `orch/cli/oss_commands.py`
- `orch/oss/scanner.py`
- `skills/iw-oss-publish/SKILL.md`
- `skills/iw-oss-publish/scripts/scan.py`

---

## Files Modified

### `dashboard/services/oss_service.py`
- **Removed** `WORKTREE_KINDS` constant (was line 45)
- **Removed** `_prep_branch_name()` (was line 232)
- **Removed** `_git_head_sha()` (was line 237) — no other caller
- **Removed** `_git_commit_info()` (was line 258) — no other caller
- **Removed** `_run_worktree()` (was line 300) — full 110-line function
- **Removed** `discard_job()` (was line 531) — relied on `worktree_path`/`branch_name` fields
- **Updated** `run_job()`: removed `elif job.kind in WORKTREE_KINDS: ... _run_worktree(...)` branch; replaced with `elif job.kind == ProjectOssJobKind.fix: ... _run_fix(project, job_id, session_factory, job.check_id or "")` placeholder raising `NotImplementedError("Phase C")`
- **Updated** `cancel_job()`: removed `worktree_path` cleanup branch (lines 506-528); now just SIGTERM/SIGKILL + pid cleanup
- **Updated** `recover_orphaned_jobs()`: removed `worktree_path` cleanup
- **Updated** module docstring: dropped "throwaway worktrees for prepare/publish"
- **Removed** `import uuid` (no longer needed)

### `dashboard/routers/oss.py`
- **Removed** `oss_prepare` route handler (was line 345)
- **Removed** `oss_publish` route handler (was line 380)
- **Updated** module docstring: "scan, prepare, publish, and install jobs" → "scan, install, and status jobs"

### `orch/cli/oss_commands.py`
- **Removed** `prepare` subcommand (was line 198)
- **Removed** `publish` subcommand (was line 206)
- **Updated** `scan` command: removed `--mode` option entirely (was `Choice(["scan", "make_oss", "publish"])`)
- **Updated** `scan` function signature: removed `mode: str` parameter; calls `run_scan(project, "scan", ...)` hardcoded
- **Updated** module docstring: "install, scan, prepare, publish, enable, disable, status" → "install, scan, enable, disable, status"

### `orch/oss/scanner.py`
- **Updated** `run_scan()`: added `if mode != "scan": raise ValueError(f"Unsupported scan mode: {mode}")` at top of function (defensive validation for external callers)

### `skills/iw-oss-publish/SKILL.md`
- **Rewrote** to document only `scan` mode (Phase A) and `fix` (Phase C placeholder)
- **Removed** "Three Modes" table — replaced with simple two-row mode table
- **Removed** `make_oss` and `publish` mode sections entirely
- **Removed** "Per-finding fix" section placeholder (added as note that Phase C adds `uv run iw oss fix <CHECK_ID> [--apply]`)
- **Updated** constraints: dropped rules about `make_oss` not committing and `publish` not auto-applying `gh` settings; replaced with "MUST NOT execute git operations beyond `git status` / `git rev-parse`. MUST NOT switch branches under any circumstances."
- **Updated** invocation to drop `--mode` argument from skill call pattern

### `skills/iw-oss-publish/scripts/scan.py`
- **Updated** `--mode` argument: `choices=["scan"]` (was `["scan", "make_oss", "publish"]`)
- **Added** `_validate_mode()` function that exits with code 2 if mode != "scan"
- **Simplified** `main()`: removed branching on `args.mode` — single code path for scan only
- **Removed** `--force` and `--no-clean-check` arguments (were `make_oss`-specific)
- **Left** `run_make_oss` and `run_publish` functions in place (marked for deletion in S19 per instructions)

---

## Symbols Removed

| Symbol | File | Signature |
|--------|------|-----------|
| `WORKTREE_KINDS` | oss_service.py | `frozenset({ProjectOssJobKind.prepare, ProjectOssJobKind.publish})` |
| `_prep_branch_name` | oss_service.py | `(job_id: int) -> str` |
| `_git_head_sha` | oss_service.py | `(repo_root: str) -> str \| None` |
| `_git_commit_info` | oss_service.py | `(repo_root, branch_name, base_sha) -> tuple[str\|None, str\|None]` |
| `_run_worktree` | oss_service.py | `async (project, job_id, kind, session_factory) -> None` |
| `discard_job` | oss_service.py | `async (session, job_id) -> None` |
| `oss_prepare` | oss.py | `POST /project/{id}/oss/prepare` |
| `oss_publish` | oss.py | `POST /project/{id}/oss/publish` |
| `prepare` subcommand | oss_commands.py | `iw oss prepare --project` |
| `publish` subcommand | oss_commands.py | `iw oss publish --project` |

---

## Behaviour Changes

### CLI (`iw oss`)
- `iw oss` — commands now: `install`, `scan`, `enable`, `disable`, `status`
- `iw oss scan --project <id>` — always uses `mode="scan"` internally; no `--mode` flag exposed

### Dashboard Routes
- `POST /project/{id}/oss/prepare` — **404** (handler removed)
- `POST /project/{id}/oss/publish` — **404** (handler removed)
- All other routes unchanged: `oss_scan`, `oss_install`, `oss_enable`, `oss_disable`, `oss_status_frame`, `oss_tools`, `oss_stream`, `oss_page`

### Scanner (`orch.oss.scanner.run_scan`)
- Now raises `ValueError("Unsupported scan mode: {mode}")` if called with mode != "scan"

### Skill Script (`scan.py`)
- Exits with code 2 if `--mode` is passed anything other than `scan`

---

## Tests Now Failing (Expected — S17 Fixes)

The following integration tests assert the removed functionality. They are intentionally broken and will be fixed in S17:

- `tests/integration/test_oss_cli.py` — asserts `prepare` and `publish` subcommands exist
- `tests/integration/test_oss_dashboard_routes.py` — asserts `/oss/prepare` and `/oss/publish` routes return 200
- `tests/integration/test_oss_persistence.py` — asserts `make_oss` mode behavior
- `tests/integration/test_oss_scanner.py` — parametrised over `["scan", "make_oss", "publish"]` modes
- `tests/integration/test_oss_dashboard_service.py` — asserts worktree provisioning in `run_job`

---

## Manual Verification

```bash
$ uv run python -c "from dashboard.services.oss_service import enqueue_job, run_job; print('import OK')"
import OK

$ uv run python -c "from orch.cli.oss_commands import oss; print([c.name for c in oss.commands.values()])"
['install', 'scan', 'enable', 'disable', 'status']  # no prepare/publish

$ make lint
# Lint errors are in S01 migration file (c062b6bf5eb3_*.py) — not in S03 files
# 7 UP007 errors in migration (Union[str, ...] should be str | ...) — pre-existing, not introduced by S03
```

---

## Notes

- `run_make_oss` and `run_publish` functions remain in `scan.py` (marked for S19 deletion per instructions to avoid review noise)
- `references/modes.md` still has `make_oss`/`publish` sections — marked for S19 deletion
- `uuid` import removed from `oss_service.py` — no longer used after `_run_worktree` removal
- S07 will implement `_run_fix` and add the `fix` subcommand to `iw oss`