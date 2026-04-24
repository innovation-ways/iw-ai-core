# CR-00019_S06_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S05 (backend-impl — CLI, worker, concurrency)
**Review Step**: S06

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards. No docker mutation, no live-DB alembic.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S05_Backend_report.md`
- All files listed in S05's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S06_CodeReview_report.md`

## Context

You are reviewing S05: CLI flag, worker rewrite, and concurrency gating.

## Review Checklist

### 1. Worktree location

- Is the worktree created under `{project.working_dir}/.worktrees/oss-prep-<job_id>/`?
- Is the `worktree_base` override from project config honored (not hardcoded `.worktrees`)?
- Is `/tmp/` completely gone from the code path?

### 2. `base_sha` capture

- Is `base_sha` captured from `main` (via `git rev-parse main`) in the project repo root **before** the subprocess fires?
- Is it written to the job row early (so a crash mid-run doesn't leave the column NULL)?

### 3. Clean-exit awaiting-review path

- Does the worker check for staged changes (`git diff --cached --numstat`) after the subprocess returns zero?
- On "has changes":
  - Commit is made inside the worktree with the expected message.
  - `commit_sha`, `branch_name`, `files_changed_summary` are populated from real git output (not hardcoded / placeholder).
  - Status transitions to `awaiting_review`.
  - Worktree is **NOT** removed.
- On "no changes": status=complete with a clear message; worktree IS removed.

### 4. Error-exit path

- On `exit_code != 0`, worktree is force-removed as today, status=error with a descriptive `error_message`.
- No orphaned worktrees possible.

### 5. Branch naming (env-driven, mandatory)

- The worker sets `IW_OSS_PREP_BRANCH=iw-oss-publish/prep-<job_id>` in the subprocess environment. Grep the worker changes to confirm the env var is built from `job_id` and passed into `asyncio.create_subprocess_exec`.
- The skill (`skills/iw-oss-publish/scripts/scan.py`) reads `os.environ["IW_OSS_PREP_BRANCH"]` and uses it verbatim.
- When `IW_OSS_PREP_BRANCH` is unset or empty in make_oss mode, the skill exits non-zero with a clear stderr message — flag as HIGH if a silent date-based fallback remains.
- The persisted `ProjectOssJob.branch_name` column value equals the env var the worker passed in (no post-hoc rescue via `git rev-parse --abbrev-ref HEAD`).
- Mirror check: `diff -rq skills/iw-oss-publish/scripts/scan.py .claude/skills/iw-oss-publish/scripts/scan.py` is empty. Flag CRITICAL if not.

### 5b. Async subprocess style

- Every git call inside `_run_worktree` uses `asyncio.create_subprocess_exec` + `await proc.communicate()`. Flag any blocking `subprocess.run` in the async function body as HIGH — it stalls the event loop and breaks S11's test mocks that assume async.

### 6. Concurrency gating

- `_active_prepare_job` (or whatever name the author chose) returns a job when one is in `running` OR `awaiting_review`.
- The 409 detail string differentiates "already running" vs "awaiting review — accept or discard".
- No race condition: the query and the `enqueue_job` insert are correctly sequenced (ideally inside a single DB transaction or with `FOR UPDATE` on the projects row).

### 7. CLI contract

- `iw oss prepare --check <ID>` works, repeatable, required ≥1.
- `iw oss prepare --project X` with no `--check` exits non-zero with a clear message.
- The scan command passes `checks` through to `run_make_oss`.

### 8. Route JSON body

- `POST /project/{id}/oss/prepare` parses the JSON body via a Pydantic model (or validated `Body(...)`).
- Empty checks list → 400 with a clear error.
- Body is forwarded through `enqueue_job` / `run_job` to the worker.

### 9. Publish / install are untouched

- Verify no shared helper silently applied the new awaiting-review behavior to `publish` or `install`. Grep for `kind == prepare` branches — if a shared function lacks that branching, flag it.

### 10. Project conventions

- Thin router (business logic in service).
- Session handling via `get_db()`.
- Typing correct (`list[str] | None`).
- No docker commands.
- No new dependencies introduced without justification.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean.
4. Re-run S05's tests — pass.

## Severity Levels

Standard (see S02). Orphaned-worktree risk → CRITICAL. Publish path regression → CRITICAL. Race in concurrency gating → HIGH. Missing branch-naming determinism → HIGH.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
