# CR-00019_S05_Backend_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S05
**Agent**: backend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards — testcontainers and read-only docker commands only. No alembic upgrade/downgrade on the live DB.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — read Desired Behavior (selection → Prepare flow, new worker, awaiting-review), AC6, AC11, AC15
- `orch/cli/oss_commands.py` — CLI entry point; `prepare` command at line 198
- `dashboard/services/oss_service.py` — `_run_worktree` at lines 210-296, `run_job` at line 298, `enqueue_job`
- `dashboard/routers/oss.py` — `oss_prepare` at line 345, `_running_job_of_kind` helper
- `orch/daemon/batch_manager.py:333` — reference for the agent-worktree path scheme `{working_dir}/.worktrees/<name>`
- `orch/daemon/batch_manager.py:428` — reference for `_resolve_worktree_base_sha`
- `orch/daemon/project_registry.py:16,107` — `worktree_base` default `.worktrees`
- `orch/db/models.py` — updated ProjectOssJob with new columns (from S01)

## Output Files

- Modified `orch/cli/oss_commands.py`
- Modified `dashboard/services/oss_service.py`
- Modified `dashboard/routers/oss.py`
- `ai-dev/work/CR-00019/reports/CR-00019_S05_Backend_report.md`

## Context

S03 updated the skill. This step wires the new contract through the **dashboard worker and CLI**:

1. CLI `iw oss prepare --check <ID>` (repeatable, required).
2. `_run_worktree` places its worktree under `{project.working_dir}/.worktrees/oss-prep-<job_id>/` (not `/tmp/`), passes selected check IDs to the skill, and on clean exit: auto-commits, captures `base_sha`/`branch_name`/`commit_sha`/`files_changed_summary`, sets status to `awaiting_review`, and keeps the worktree.
3. `_running_job_of_kind` blocks new Prepare jobs while one is `running` OR `awaiting_review`.

S07 adds the accept/discard routes — you don't implement those here. But be aware the columns you populate in this step (`base_sha`, etc.) are what S07 reads.

## Requirements

### 1. CLI — `orch/cli/oss_commands.py`

At the `prepare` command (line 198):

- Add `@click.option("--check", "checks", multiple=True, required=True, help="Check ID to auto-fix. Repeat for multiple IDs.")`.
- Forward the option into `ctx.invoke(scan, project_id=project_id, mode="make_oss", json_output=False, checks=tuple(checks))` — and have the `scan` command accept a `checks` kwarg that passes it down to `run_scan` → `run_make_oss`.
- If `checks` is empty (should be prevented by `required=True`, but belt-and-braces), exit 2 with a clear message.

Inspect the current `scan` command to see how it invokes the scanner and add the `checks` parameter there too. The skill script already accepts `--check`; you just need to shell it through.

### 2. Worker rewrite — `dashboard/services/oss_service.py`

#### 2a. Move worktree location

Replace:

```python
worktree_path = Path(f"/tmp/oss-{uuid.uuid4()}")
```

with:

```python
from orch.daemon.project_registry import load_project_config  # or equivalent helper
worktrees_root = Path(project.working_dir) / ".worktrees"   # resolve project worktree_base if set
worktree_path = worktrees_root / f"oss-prep-{job_id}"
worktree_path.parent.mkdir(parents=True, exist_ok=True)
```

Check whether the project's iw config (in `orch/daemon/project_registry.py`) overrides `worktree_base`. If it does, honor it. Default is `.worktrees`.

#### 2b. Capture `base_sha` before the subprocess

`_run_worktree` is an `async def` (see `dashboard/services/oss_service.py:210`). Every subprocess in this function MUST use `asyncio.create_subprocess_exec` (matching the existing style for `_run_scan` / `_run_install`). **Do not use blocking `subprocess.run`** inside this coroutine — it stalls the event loop and is inconsistent with the surrounding code.

Resolve `main` HEAD in `project.repo_root` and write to the job row:

```python
proc = await asyncio.create_subprocess_exec(
    "git", "rev-parse", "main",
    cwd=str(project.repo_root),
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, _ = await proc.communicate()
base_sha = stdout.decode().strip() or None
```

Persist via `ProjectOssJob.base_sha` in the same session update that writes `worktree_path`.

Every subsequent git call in this step (the post-subprocess `git diff --cached`, commit, rev-parse HEAD, `diff --stat`, `worktree remove`) MUST also use `asyncio.create_subprocess_exec` and be `await`-ed.

#### 2c. Pass `--check` IDs to the skill

Read the selected checks from the job row or from a new parameter. Since the dashboard POST now receives `{"checks": [...]}` (see `dashboard/routers/oss.py`), store them on the job (you can piggyback on `stdout_tail` with a serialized JSON header, or — cleaner — add the checks to a transient per-job context dict in memory passed into `run_job`). Preferred: add a `checks: list[str]` param to `run_job` and `_run_worktree`, and have `enqueue_job` / the route pass them through.

Build the command:

```python
cmd = ["uv", "run", "iw", "oss", action, "--project", project.id]
for check_id in checks:
    cmd.extend(["--check", check_id])
```

#### 2d. On clean exit with staged changes — auto-commit and persist

After the subprocess exits with `exit_code == 0`:

1. Check whether there are staged changes in the worktree:
   ```python
   proc = await asyncio.create_subprocess_exec(
       "git", "diff", "--cached", "--numstat",
       cwd=str(worktree_path),
       stdout=asyncio.subprocess.PIPE,
       stderr=asyncio.subprocess.PIPE,
   )
   stdout, _ = await proc.communicate()
   has_changes = bool(stdout.decode().strip())
   ```
2. If `has_changes`:
   a. Commit: `git commit -m "chore: prepare for public OSS release"` inside the worktree. Use `-s` only if the repo has sign-off enforcement; match the existing convention (check `git config commit.gpgsign` — do NOT skip signing with `--no-gpg-sign` unless the user has configured that globally).
   b. Capture `commit_sha`: `git rev-parse HEAD` in the worktree.
   c. Capture `branch_name`: `iw-oss-publish/prep-<job_id>` (the skill creates this; verify by `git rev-parse --abbrev-ref HEAD`).
   d. Capture `files_changed_summary`: `git diff --stat <base_sha>..HEAD` (or `git diff --stat HEAD^..HEAD` if base_sha is unavailable).
   e. Update the job row: `status = ProjectOssJobStatus.awaiting_review`, `commit_sha = …`, `branch_name = …`, `files_changed_summary = …`. **Do NOT remove the worktree.** Do NOT set `completed_at` yet — that happens on accept/discard.
3. If NOT `has_changes`:
   - No changes means the selected checks couldn't produce any fixes. Set `status = complete` with `error_message = "No changes produced — selected checks had nothing to auto-fix"`. Remove the worktree (nothing to review).

#### 2e. On error exit — unchanged from today

- Remove the worktree via `git worktree remove --force`.
- Set `status = error`, populate `error_message`.
- Never leave a worktree behind for a failed run.

#### 2f. Branch naming (env-driven, mandatory)

The skill currently creates branch `iw-oss-publish/prep-YYYY-MM-DD`. Two prepares on the same day would collide. For this CR, the branch **MUST** be `iw-oss-publish/prep-<job_id>`, set via env var — there is no fallback to the date-based path.

Required wiring:

1. **Worker side** (`dashboard/services/oss_service.py`): when spawning the `uv run iw oss prepare` subprocess, pass `IW_OSS_PREP_BRANCH=iw-oss-publish/prep-<job_id>` in the process environment. Example:
   ```python
   env = {**os.environ, "IW_OSS_PREP_BRANCH": f"iw-oss-publish/prep-{job_id}"}
   proc = await asyncio.create_subprocess_exec(*cmd, env=env, ...)
   ```
2. **Skill side** (`skills/iw-oss-publish/scripts/scan.py`, around lines 195-196 where the branch name is constructed): read `os.environ["IW_OSS_PREP_BRANCH"]` and use it verbatim. If the env var is **unset or empty**, `run_make_oss` must `sys.exit(2)` with a clear stderr message — do NOT silently fall back to the date-based name. The CR assumes the dashboard worker is the only caller that enters make_oss mode; direct CLI callers must also export the env var.
3. **Mirror**: the same edit must land in `.claude/skills/iw-oss-publish/scripts/scan.py` (verify with `diff -rq skills/iw-oss-publish/ .claude/skills/iw-oss-publish/`).
4. **Job-row capture**: after the commit, `branch_name` is persisted as exactly `iw-oss-publish/prep-<job_id>` (the same value the worker passed in). No post-hoc `git rev-parse --abbrev-ref HEAD` rescue path — if the skill created a different branch for any reason, that is a bug to fix, not to paper over.

Document in the S05 report: confirm the env var is set in the worker, the skill reads it, and the skill exits non-zero when it's missing.

### 3. Concurrency gating — `dashboard/routers/oss.py`

Extend `_running_job_of_kind` (or introduce a new helper if cleaner):

```python
def _active_prepare_job(db: Session, project_id: str) -> ProjectOssJob | None:
    """Returns any Prepare job that's running OR awaiting_review."""
    return (
        db.query(ProjectOssJob)
        .filter(
            ProjectOssJob.project_id == project_id,
            ProjectOssJob.kind == ProjectOssJobKind.prepare,
            ProjectOssJob.status.in_([
                ProjectOssJobStatus.running,
                ProjectOssJobStatus.awaiting_review,
            ]),
        )
        .order_by(ProjectOssJob.id.desc())
        .first()
    )
```

At `oss_prepare` (`dashboard/routers/oss.py:345`):

- Replace the existing `_running_job_of_kind(...)` call with `_active_prepare_job(...)`.
- Craft the 409 detail:
  - If existing.status == running: `"Prepare job #{existing.id} is already running"` (as today).
  - If existing.status == awaiting_review: `"Prepare job #{existing.id} is awaiting review — accept or discard it first"`.

Also, the POST body for `/oss/prepare` now requires `{"checks": [...]}`. Parse it via a Pydantic model (or FastAPI `Body(...)`), validate non-empty, and pass the list through to `enqueue_job` / `run_job`.

### 4. Publish and install paths — DO NOT TOUCH

Verify your changes don't accidentally affect `publish` or `install` jobs. The awaiting-review state and the worktree-persist behavior apply **only** to `kind == prepare`. If `_run_worktree` is shared with `publish`, branch on kind; do not change publish's behavior.

## Project Conventions

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, and `orch/CLAUDE.md`. Key rules:
- Thin routers — business logic in `dashboard/services/`.
- `dependencies.get_db()` session; never open a new engine from a router.
- `postgresql+psycopg://` URL scheme (not psycopg2).
- No docker commands from dashboard code.
- `playwright-cli` not `agent-browser` for any browser checks (n/a for this step but keep it in mind).

## TDD Requirement

Primary test coverage for this step lives in S11. For this step:

1. **RED**: Write targeted unit tests for:
   - `_active_prepare_job` returns the right job in each status combination.
   - CLI `prepare` rejects a call with no `--check`.
   - `_run_worktree`'s code path for "clean exit with staged changes" sets status=awaiting_review and populates the new columns (use a mock subprocess + a real git-init'd tmp repo).
   - `_run_worktree`'s "clean exit, no changes" path sets status=complete and removes the worktree.
2. **GREEN**: Implement.
3. **REFACTOR**.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean.
4. Your new unit tests pass.
5. No new ruff or mypy warnings.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/oss_commands.py",
    "dashboard/services/oss_service.py",
    "dashboard/routers/oss.py",
    "skills/iw-oss-publish/scripts/scan.py (env-driven branch name)",
    ".claude/skills/iw-oss-publish/scripts/scan.py (mirror)",
    "tests/unit/test_cr_00019_worker.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Branch naming source (env vs. date) — document which was chosen and why."
}
```
