# F-00062_S04_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute docker / docker-compose state-changing commands. The S03 module legitimately invokes them — your job is to review that the invocations are correct and tightly scoped, NOT to run them yourself. Read-only `docker ps|inspect|logs` allowed for verification. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

S03 modifies `safe_migrate.py` to relax `AgentContextForbiddenError` for per-worktree DB. Your review MUST verify: the relax is gated on BOTH `IW_CORE_PER_WORKTREE_DB=true` AND a URL that points at the per-worktree DB (NOT 5433); the live orch DB protection on 5433 is unchanged regardless of flag values. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc, S01–S03 reports
- `orch/daemon/worktree_compose.py` (new)
- `orch/db/safe_migrate.py` (modified)
- `tests/unit/daemon/test_worktree_compose.py` (new — new file in existing `tests/unit/daemon/` subdirectory established by `test_migration_rebase.py`)
- `tests/unit/test_safe_migrate.py` (modified — extended in place; this repo has NO `tests/unit/db/` subdirectory)
- `orch/daemon/browser_env.py` — the reference pattern S03 mirrors

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S04_CodeReview_report.md`

## Context

You are reviewing the new `worktree_compose.py` module and the `safe_migrate` relax. Both are critical: the module owns docker subprocess calls (security/blast-radius surface) and the safe_migrate change touches an existing security boundary (Invariant #3).

## Review Checklist

### 1. Subprocess safety (docker invocations)
- Every `docker` call uses `subprocess.run(args=[...], shell=False, check=False, timeout=...)` — NO `shell=True`, NO `os.system`, NO unparameterized command construction
- `args=` is a literal list; `batch_item_id` and other dynamic values are passed as separate list elements (not string-interpolated)
- `compose_project_name` is sanitized (lowercase, dash-separated) and matches docker's project-name rules
- All subprocess calls have an explicit `timeout=` (suggested: 60s for `up`, 30s for `down`, 10s for `port`/`ps`, 300s+ for seed since `pg_dump` can be slow)

### 2. Idempotency
- `up()` is safe to call twice in a row on the same `batch_item_id` (second call is either a no-op or a `down`+`up` recreate — design doc Invariant #6 says all-NULL or all-set; verify the behavior matches)
- `down()` succeeds when nothing is running (returns True, no exception)
- `render_compose()` overwrites prior render without error
- `rewrite_env()` is idempotent — running twice with the same inputs produces the same `.env`

### 3. Failure paths
- `up()` failures (docker error, port discovery error, seed failure) call `down()` to clean up partial state
- Seed-script non-zero exit returns `UpResult(success=False, ...)` with stderr_tail populated
- `assert_gitignore_safe` raises clearly on missing `.env` or `.iw/` lines (AC8 wording)
- All errors emit a `DaemonEvent` with `success=False` and a useful metadata payload

### 4. `safe_migrate.py` relax
- The relax checks `IW_CORE_PER_WORKTREE_DB=true` AND URL→per-worktree-DB
- Live 5433 protection is independent of any flag — verify by reading the guard logic
- `test_blocks_against_orch_db_even_with_per_worktree_flag` exists and passes
- The detection of "URL points at per-worktree DB" is robust (host=localhost, port matches `IW_CORE_DB_PORT` env)

### 5. No secrets in logs
- Search `worktree_compose.py` for any `logger.*(...)` or `print(...)` that includes raw `.env` content, `os.environ`, or values from `[env_passthrough]`
- Stderr capture truncates and DOES NOT echo lines that look like `KEY=VALUE` with secret-shaped keys (be defensive — at minimum redact common patterns: `*PASSWORD*`, `*TOKEN*`, `*SECRET*`, `*KEY*` other than IW_CORE_*)

### 6. Module shape vs `browser_env.py`
- Module docstring matches the style of `browser_env.py`
- Public functions have type hints and docstrings
- Dataclasses are `frozen=True` where state shouldn't change post-construction
- Imports are organized (stdlib, third-party, project) per ruff defaults

### 7. Coverage of S03's listed unit tests
- All ten tests from S03's "TDD Requirement" exist and pass
- Tests use `tmp_path` for filesystem fixtures, mock subprocess where needed
- No real docker invocations in these unit tests (those are S11's integration scope)

### 8. Project conventions
- Sync code only (no async)
- psycopg v3 if SQL touched
- `Mapped[]` SQLAlchemy 2.0 if ORM touched (S03 shouldn't touch ORM but verify)

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — all pass
2. Run `make lint` and `make quality`
3. Read `worktree_compose.py` end-to-end and trace each public function

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | safe_migrate relax allows operations on 5433; subprocess shell=True; secrets in logs |
| HIGH | Missing timeout on docker call; idempotency violation that could leave zombie containers; missing failure cleanup |
| MEDIUM_FIXABLE | Missing test from required list; weak error message; unsafe-looking but not exploitable code |
| MEDIUM_SUGGESTION | Refactor opportunity; clearer naming |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
