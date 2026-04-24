# CR-00019_S07_API_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step**: S07
**Agent**: api-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md` — read AC7, AC8, AC9, AC10, AC14, the Accept/Discard sections under Desired Behavior
- `dashboard/routers/oss.py` — existing OSS routes (scan, prepare, publish, install, stream)
- `dashboard/services/oss_service.py` — post-S05 state, has new awaiting-review lifecycle
- `dashboard/routers/worktrees.py` — current worktree enumerator
- `orch/db/models.py` — ProjectOssJob with new columns

## Output Files

- Modified `dashboard/routers/oss.py`
- New service helpers in `dashboard/services/oss_service.py` (or a new file `dashboard/services/oss_review.py` if the existing one is getting large)
- Modified `dashboard/routers/worktrees.py`
- `ai-dev/work/CR-00019/reports/CR-00019_S07_API_report.md`

## Context

S05 made Prepare produce an `awaiting_review` state. This step adds the **two routes** that let the user finalize that state, plus surfaces OSS-prep worktrees on the `/system/worktrees` page.

## Requirements

### 1. POST `/project/{project_id}/oss/jobs/{job_id}/accept`

Route handler `oss_accept`:

1. Load project via `get_project_or_404`.
2. Load the `ProjectOssJob` by (project_id, job_id). 404 if not found.
3. If `job.kind != prepare` → 400 `{"detail": "Only prepare jobs can be accepted"}`.
4. If `job.status != awaiting_review` → 409 `{"detail": "Job #N is in status X — only awaiting_review can be accepted"}`.
5. Delegate to a service helper `accept_oss_prepare(db, project, job)` that:
   a. Resolves current `main` HEAD in `project.repo_root`.
   b. If current `main` sha ≠ `job.base_sha` → raise a typed error (`MainMovedError`). Route catches and returns 409 with `{"detail": "main has advanced since Prepare ran — discard this job and re-run Prepare"}`.
   c. From `project.repo_root`, runs `git merge --squash <job.branch_name>`. Capture the process result; if non-zero, raise a typed error; route returns 500 with the first 1 KB of stderr.
   d. Commits: `git commit -m "chore: prepare for public OSS release (oss-prep-job-<job.id>)"`. If the commit fails (clean index — nothing to merge because squash already replayed), raise + route returns 500.

      **Hook / signing behavior**: do NOT pass `--no-verify` and do NOT pass `--no-gpg-sign`. Inherit whatever `commit.gpgsign` / pre-commit hook config the project repo has. If a pre-commit hook or GPG signing step fails during accept, treat the same as any other git failure (set job to `error`, surface stderr in `error_message`, return 500, leave worktree + branch for inspection). Rationale: this matches S05's in-worktree commit handling — accept must not be more permissive than Prepare.
   e. `git branch -D <job.branch_name>` — if it fails with "branch not found", log warn and continue (idempotent safety).
   f. `git worktree remove --force <job.worktree_path>` — if the path doesn't exist, log warn and continue.
   g. Updates job row: `status = complete`, `completed_at = now()`.
6. Returns 200 JSON `{"status": "complete", "files_changed": <count>}` where `<count>` is parsed from the `files_changed_summary` column (simple line-count will do; 0 acceptable for the edge case of empty diff).

**Do not hold the DB session open during the git subprocesses.** Use the dependency-injected session only to read job state + commit the final status update; the long-running git ops happen in between. If you need to ensure no other writer changes the row mid-operation, use a `with_for_update()` query before the subprocess block, and release it after the final commit.

**Error recovery**: if step c or d fails, the job row should be moved to `status = error` with `error_message = <first 1 KB of stderr>`, and the route returns 500. The worktree and branch must NOT be removed on error — operator needs them to investigate.

### 2. POST `/project/{project_id}/oss/jobs/{job_id}/discard`

Route handler `oss_discard`:

1. Load project, load job (same guards as accept).
2. If `job.status != awaiting_review` → 409 with the status diagnostic.
3. Delegate to `discard_oss_prepare(db, project, job)`:
   a. `git worktree remove --force <job.worktree_path>` — if missing, log warn + continue.
   b. `git branch -D <job.branch_name>` — if missing, log warn + continue.
   c. Update job row: `status = discarded`, `completed_at = now()`.
4. Returns 200 JSON `{"status": "discarded"}`.

**Idempotency**: calling discard twice is allowed — the second call finds the job in `discarded` status and returns 409 `"Job is already discarded"`. Acceptable (the user saw it work the first time). If you want **true** idempotency (second call returns 200 with status=discarded), flip the gate: only 409 for statuses that are neither awaiting_review nor discarded. Document your choice in the report.

### 3. Surface OSS-prep worktrees on `/system/worktrees`

Inspect `dashboard/routers/worktrees.py`. The enumerator scans agent worktrees in `{working_dir}/.worktrees/`. For this CR:

- Extend the scan to detect worktrees whose directory name starts with `oss-prep-` and treat them as OSS-prep worktrees.
- Render with a distinct badge (e.g. `OSS prep`) in the existing table.
- If you can resolve a link back to the owning project's OSS tab (`/project/{project_id}/oss`), make the row clickable or add a tooltip with the path.
- If the owning project is ambiguous (e.g. same `.worktrees/` dir is shared across registered projects), don't guess — just label them with their parent repo's project_id as resolved by `projects.toml`.

Do not change the existing dirty-worktree badge logic for agent worktrees.

### 4. Service helpers

Create two module-level functions in `dashboard/services/oss_service.py` (or a new `oss_review.py`):

```python
def accept_oss_prepare(db: Session, project: Project, job: ProjectOssJob) -> dict: ...
def discard_oss_prepare(db: Session, project: Project, job: ProjectOssJob) -> dict: ...
```

Plus a typed `class MainMovedError(Exception)` raised by accept when base_sha drift is detected.

### 5. Logging

Every git invocation logs: command + cwd + return code + first 256 bytes of stderr on non-zero. This is vital for the awaiting-review lifecycle — when a merge fails, operators need to see exactly what happened.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key rules:
- Thin router; service does the work.
- `get_db()` dependency for sessions.
- No docker commands. No alembic.
- FastAPI return types: `Response(status_code=200, content=json.dumps(...), media_type="application/json")` matches the existing OSS routes (see `oss_scan` for the pattern).

## TDD Requirement

1. **RED**: Write route-level tests (FastAPI TestClient against testcontainer PG):
   - Accept happy path (mocked git subprocesses) → status=complete, final commit message includes "(oss-prep-job-N)".
   - Accept with moved main → 409.
   - Accept on wrong status (e.g. `complete`) → 409.
   - Discard happy path → status=discarded, worktree-remove + branch-delete called.
   - Discard when worktree path doesn't exist → still 200, log warn.
   - Second discard → 409 "already discarded".
   - `/system/worktrees` includes OSS-prep rows with the right badge.
2. **GREEN**: Implement.
3. **REFACTOR**.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean.
4. Your new tests pass (unit and route-level integration, testcontainer).

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "api-impl",
  "work_item": "CR-00019",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/oss.py",
    "dashboard/services/oss_service.py (or oss_review.py)",
    "dashboard/routers/worktrees.py",
    "tests/integration/test_cr_00019_accept_discard.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Document idempotency choice for discard (second-call 200 vs 409)."
}
```
