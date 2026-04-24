# CR-00019_S08_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S07 (api-impl — accept/discard routes, worktrees surface)
**Review Step**: S08

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S07_API_report.md`
- All files listed in S07's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S08_CodeReview_report.md`

## Context

You are reviewing S07: accept/discard routes and worktree surfacing.

## Review Checklist

### 1. Moved-main detection

- Is `base_sha` compared against **current** main HEAD (not against the worktree's HEAD or a cached value)?
- Is the 409 error message clear and actionable ("discard this job and re-run Prepare")?
- On drift, is the worktree **untouched** (the user may want to inspect it before discarding)?

### 2. Squash-merge semantics

- Command used: `git merge --squash <branch>` followed by `git commit -m "chore: prepare for public OSS release (oss-prep-job-<N>)"` — not `git merge --no-ff` or plain merge.
- `cwd` is the project repo root (not the worktree).
- The final commit message interpolates the job ID correctly.
- If the squash would produce an empty commit (branch already merged), the handler fails cleanly instead of creating an empty commit.

### 3. Error recovery

- On mid-operation git failure (e.g. merge conflict), the job moves to `status = error` with `error_message` populated; worktree + branch remain so the operator can investigate.
- The route returns 500, not 200.

### 4. Discard idempotency

- The author made a clear decision (209 on repeat vs. true idempotence) and documented it. Either choice is acceptable if consistent. Flag if the decision is ambiguous in the code / report.
- `worktree remove --force` and `branch -D` both tolerate "already missing" without crashing the request.

### 5. DB session handling

- No long-running git subprocess holds the DB session open.
- The row is guarded against concurrent writers (e.g. `with_for_update()` or a single-UPDATE status transition with status-aware WHERE clause).

### 6. Worktrees page

- OSS-prep worktrees appear with a distinct badge.
- Agent-worktree rendering is unchanged.
- No N+1 query (scan one `.worktrees/` directory, don't issue a git call per entry).

### 7. Logging

- Every git invocation is logged with command + cwd + return code + stderr tail.
- No secrets leaked (repo_root paths OK; auth tokens are never in play here).

### 8. API shape

- 200 responses return plain JSON: `{"status": "complete", ...}` / `{"status": "discarded"}`.
- 409 / 400 / 500 responses have meaningful `detail` strings.
- The route paths match the design doc exactly:
  - `POST /project/{project_id}/oss/jobs/{job_id}/accept`
  - `POST /project/{project_id}/oss/jobs/{job_id}/discard`
- No breaking change to other OSS routes.

### 9. Conventions

- Thin router (services do the work).
- Typed exceptions (`MainMovedError`) caught in the route, not inside the service.
- `Body(...)` / Pydantic model if any request body exists (accept/discard are empty POSTs; fine).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make lint` — clean.
3. `uv run mypy orch/ dashboard/` — clean.
4. Re-run S07's route-level integration tests — all pass.

## Severity Levels

Standard. Accept leaves the repo in a broken state on partial failure → CRITICAL. Missing moved-main check → CRITICAL. Missing worktree-idempotency on discard → HIGH.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
