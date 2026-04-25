# CR-00022_S03_Backend_prompt

**Work Item**: CR-00022 -- OSS Compliance redesign
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same rules. Read-only `docker ps/inspect/logs` only.

## ⛔ Migrations: agents generate, daemon applies

This step does not introduce a migration. Do NOT modify migration files written in S01.

## Input Files

- `ai-dev/active/CR-00022/CR-00022_CR_Design.md`
- `ai-dev/active/CR-00022/reports/CR-00022_S01_Database_report.md`
- `dashboard/services/oss_service.py` (current)
- `dashboard/routers/oss.py` (current)
- `orch/cli/oss_commands.py` (current)
- `orch/oss/scanner.py` (current)
- `skills/iw-oss-publish/SKILL.md` (current)

## Output Files

- Modified: `dashboard/services/oss_service.py`, `dashboard/routers/oss.py`, `orch/cli/oss_commands.py`, `orch/oss/scanner.py`, `skills/iw-oss-publish/SKILL.md`
- `ai-dev/active/CR-00022/reports/CR-00022_S03_Backend_report.md`

## Context

This is the **Phase A code-removal** step. With S01 having pruned the schema, this step rips out every code path that produced or consumed prepare/publish data. The deletions are the load-bearing change of this CR — every byte removed eliminates a way for the dashboard to switch the user's branch unexpectedly.

Read the design document and `dashboard/CLAUDE.md` + `orch/CLAUDE.md` first.

## Requirements

### 1. `dashboard/services/oss_service.py`

Remove these symbols entirely:
- `WORKTREE_KINDS` constant (line ~45)
- `_prep_branch_name(job_id)` (line ~232)
- `_git_head_sha(repo_root)` (line ~237) — also remove if no other caller; otherwise leave
- `_git_commit_info(repo_root, branch_name, base_sha)` (line ~258)
- `_run_worktree(project, job_id, kind, session_factory)` (line ~300)
- `discard_job(session, job_id)` (line ~531)

Update `run_job(session_factory, job_id)` (line ~417) to remove the `elif job.kind in WORKTREE_KINDS: ... _run_worktree(...)` branch. After removal, the kind-dispatch should be: `scan` → `_run_scan`, `install` → `_run_install`, `fix` → new `_run_fix(project, job_id, session_factory, check_id)` placeholder that raises `NotImplementedError("Phase C")`. S07 implements `_run_fix`.

Update `cancel_job(session, job_id)` (line ~474) to remove the `worktree_path` cleanup branch (~line 506-528).

Update the module docstring (line 1) to drop "throwaway worktrees for prepare/publish".

### 2. `dashboard/routers/oss.py`

Remove these route handlers:
- `oss_prepare` (line ~345)
- `oss_publish` (line ~380)

Keep `oss_scan`, `oss_install`, `oss_enable`, `oss_disable`, `oss_status_frame`, `oss_tools`, `oss_stream`, and `oss_page`.

In `oss_page`: the `recent_jobs` query and the findings rendering stay as-is for now (S11 rewrites the template). Remove any references to prepare/publish in branch logic if present.

### 3. `orch/cli/oss_commands.py`

Remove these commands entirely:
- `prepare` (line ~198)
- `publish` (line ~206)

Update `scan` command (line ~94):
- Remove the `--mode` option's `make_oss` and `publish` choices: `type=click.Choice(["scan"])` (or remove `--mode` if only one value remains; prefer keep for forward-compat).
- Update the docstring.

Update the module docstring (line 1) to drop "prepare, publish".

Note: S07 will add a new `fix` subcommand. Do not add it here.

### 4. `orch/oss/scanner.py`

Update `run_scan` to drop `mode` parameter handling that produced `make_oss` / `publish` scans. The function signature can keep `mode` defaulting to `"scan"` for forward-compat but should validate `mode == "scan"` and raise `ValueError(f"Unsupported scan mode: {mode}")` otherwise. This is defensive — the CLI no longer passes anything else, but external callers might.

### 5. `skills/iw-oss-publish/SKILL.md`

Rewrite the SKILL.md so:
- Remove the "Three Modes" table — only `scan` (default) and `fix` (per-finding, future) are documented.
- Remove the `make_oss` and `publish` mode sections.
- Add a "Per-finding fix" section explaining: invocation is `python3 .claude/skills/iw-oss-publish/scripts/scan.py` for full scan; per-finding fixes are run via `uv run iw oss fix <CHECK_ID> [--apply]` (this CLI lands in S07).
- Update the constraints section: drop the rules about not committing in `make_oss`, not auto-applying `gh` settings in `publish`. Replace with: "MUST NOT execute git operations beyond `status` / `rev-parse`. MUST NOT switch branches under any circumstances."
- Update the modes/exit-codes table accordingly.

Keep the prerequisites, project configuration, report template sections (they remain valid for `scan`).

### 6. Skill scripts

If `skills/iw-oss-publish/scripts/scan.py` accepts a `--mode` flag with `make_oss`/`publish` values, simplify it to scan-only (validate any provided value as `scan`, error otherwise). Do NOT delete the scan.py script — it remains the orchestrator.

If `skills/iw-oss-publish/references/modes.md` has dedicated `make_oss` / `publish` sections, mark them for deletion in S19 (do not delete now to avoid noise on the review of S03).

### 7. Tests left intentionally broken

The following will fail after S03 — that is expected; S17 fixes them:
- `tests/integration/test_oss_cli.py` (asserts `prepare`/`publish` subcommands)
- `tests/integration/test_oss_dashboard_routes.py` (asserts `/oss/prepare`, `/oss/publish` routes)
- `tests/integration/test_oss_persistence.py` (asserts `make_oss` mode)
- `tests/integration/test_oss_scanner.py` (parametrised over modes)
- `tests/integration/test_oss_dashboard_service.py` (worktree provisioning assertions)

List them in the report so S04 can confirm scope.

### 8. Manual verification

After your changes, run:

```bash
make lint
uv run python -c "from dashboard.services.oss_service import enqueue_job, run_job"   # import-time sanity
uv run python -c "from orch.cli.oss_commands import oss; print([c.name for c in oss.commands.values()])"
# Expect: ['install', 'scan', 'enable', 'disable', 'status']  (no prepare/publish)
```

## Project Conventions

Follow `dashboard/CLAUDE.md` (thin routers, sync SQLAlchemy via `dependencies.get_db()`, htmx fragments don't extend `base.html`) and `orch/CLAUDE.md` (CLI groups, sync session). Do not add error handling for scenarios that can't happen — trust the type system; only validate at boundaries.

## Output / Report

Write the step report listing:
- Files modified (paths + summary of removals + line counts)
- Symbols removed
- Behaviour change for each public surface (CLI, dashboard route)
- Tests now failing (paths)
- Manual verification results

End with `iw step-done` or `iw step-fail`.
