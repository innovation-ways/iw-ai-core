# CR-00021_S04_CodeReview_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. No `docker compose up/down/stop/kill/rm`. Read-only introspection fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (Desired Behavior, AC1–AC4)
- `ai-dev/active/CR-00021/reports/CR-00021_S03_Backend_report.md` — S03 implementation report
- `orch/daemon/migration_rebase.py` — the new module under review
- `tests/unit/daemon/test_migration_rebase.py` — the local unit tests S03 added
- `orch/daemon/migration_pipeline.py` — style reference that S03 must mirror
- `orch/db/safe_migrate.py` — style reference for `_write_migration_log`

## Output Files

- `ai-dev/active/CR-00021/reports/CR-00021_S04_CodeReview_report.md` — review report

## Context

Review S03's new `orch/daemon/migration_rebase.py`. The module must behave as the design describes, mirror `migration_pipeline.py`'s style, and produce correct `PendingMigrationLog` + `DaemonEvent` rows. Wiring into `merge_queue.py` is S05's scope — **not** in review here.

## Review Checklist

### 1. Module shape

- Module docstring present, names CR-00021, lists integration points (merge_queue, safe_migrate, models)?
- Public API limited to `run_pre_merge_rebase`, `RebaseResult`, `Rewrite`, and the three internal exceptions (which should NOT be `__all__`-exported)?
- No cross-layer imports — only `orch.config`, `orch.db.models`, stdlib, sqlalchemy, alembic.script.

### 2. `run_pre_merge_rebase` order of operations

- Preflight SHAs read BEFORE `git fetch`?
- `git fetch origin main` happens BEFORE reading `rev-parse origin/main`?
- DaemonEvent emitted **always** (including when rebase isn't needed — AC2 depends on this)?
- Rebase is a no-op when `worktree_base_sha == current_main_sha`?
- On rebase conflict: `git rebase --abort` runs even if abort itself fails?
- Non-added files (modified migrations) correctly ignored — `--diff-filter=A` used, not `--diff-filter=AM`?

### 3. Migration parsing

- Regex handles both `"..."` and `'...'` quote styles?
- Handles `down_revision = None` (no quotes) without crashing?
- Does NOT `importlib` or `ast.parse` the migration file (would re-execute arbitrary code; the design explicitly forbids this)?
- Ignores commented-out `down_revision = "..."` lines (match only at line start)?

### 4. Chain ordering

- Multi-file chain: the file whose `down_revision` is NOT the `revision` of another batch file is the root?
- Multiple roots or cycles → `RebaseResult(success=False, error_message=...)`, not a silent corruption?
- Single-file batch (most common) → chain root is that file, expected `down_revision = <main head>`?
- **`_latest_main_revision` excludes the batch's own files before running `ScriptDirectory`** — CRITICAL. If the implementation runs `ScriptDirectory` against the raw post-rebase `versions/` directory, it will either hit `MultipleHeadsError` (stale case — the exact bug this CR is supposed to prevent) or compute the batch's own file as the single head (self-reference after rewrite). Confirm the implementation copies only main-only files into a tmp dir (or equivalent approach that filters the batch's files out) before asking Alembic for the head.
- Tmp-directory clean-up on all exit paths (success, `RebaseChainError`, exception) — no leaked `cr21-main-head-*` dirs?
- Pre-existing multi-head on main (the main-only chain itself has > 1 head) produces a clear `RebaseChainError` mentioning "manual intervention" — NOT a silent fall-through or a wrong pick?

### 5. Rewriting

- `re.sub` on the `down_revision = ...` line preserves leading whitespace, quote style, trailing whitespace/comments?
- Quote style: if original was `'rev1'`, new value uses single quotes; if `"rev1"`, uses double quotes?
- File written via `Path.write_text(..., encoding="utf-8")` (no accidental line-ending mangling on WSL/Linux)?
- Writes ONLY the files that need rewriting (does not touch non-stale files)?

### 6. Commit handling

- `git add` stages only the rewritten files (not `git add -A`)?
- Commit message exactly matches the design: `"chore(migration-rebase): rewrite down_revision for <revs>"`?
- `--no-verify` is present (pre-commit hooks on the project might reject mid-pipeline writes)?
- Commit failure → `RebaseResult(success=False)` WITHOUT reverting the file edits (comment explains why)?

### 7. DB writes

- `_write_rebase_log` opens a fresh short-lived session (engine / sessionmaker / close / dispose)?
- Writes `PendingMigrationLog` with `phase='rebase'`, `direction='upgrade'`, `old_revision=<prev>`, `started_at=completed_at=now(UTC)`?
- Log-write failure is logged (not raised) — the rebase has already succeeded, and an audit-log failure must not fail the batch?
- DaemonEvent emission uses `event_metadata=` kwarg (SQLAlchemy reserves `metadata` — see CLAUDE.md gotcha)?

### 8. subprocess hygiene

- Every `subprocess.run` uses `shell=False`, `capture_output=True`, `text=True`, `check=False`, `timeout=<N>`?
- No `os.environ[]` pollution for git subprocess (inherit, do not set GIT_DIR / GIT_WORK_TREE)?
- Paths passed as `list[str]` args (no string interpolation that could enable shell injection)?

### 9. Error semantics (AC4 compliance)

- All three internal exceptions (GitCommandError, MigrationParseError, RebaseChainError) caught at the top of `run_pre_merge_rebase` and converted to `RebaseResult(success=False, ...)`?
- `error_message` always populated on failure paths, never an empty string?
- `rebased=False` on failure paths (branch wasn't successfully rebased)?

### 10. Unit tests (from S03)

- Cover AC1 (rewrite), AC2 (idempotent no-op), AC3 (multi-file chain), AC4 (rebase conflict)?
- Use `tmp_path` + a scratch git repo, NOT mocks of subprocess (mocks hide actual git behaviour)?
- Assert PendingMigrationLog rows are written (use a testcontainer or a lightweight sqlite session with the ORM — whichever matches project patterns)?
- Deterministic — no time-dependent or filesystem-order assumptions?

### 11. Project conventions

- Logger via `logging.getLogger(__name__)`?
- No unnecessary comments describing WHAT (only WHY comments allowed)?
- Types: `list[Rewrite]` / `str | None` (PEP 604), not `List[]` / `Optional[]`?
- Dataclass is `frozen=True`?
- Module-level `MIGRATIONS_SCRIPT_LOCATION`-style constants NOT used (we're operating on worktree paths, not the main repo)?

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — must pass
2. Run `make lint` / `make format` / `make typecheck` — must pass
3. Report accurately

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks ACs (conflict path doesn't abort rebase, DaemonEvent not always emitted, file corruption in rewrite, SQL injection / shell injection) |
| **HIGH** | Non-compliance with design (log row missing `old_revision`, commit message format wrong, silent failure paths, `event_metadata` gotcha ignored) |
| **MEDIUM (fixable)** | Style drift from migration_pipeline.py, missing subprocess timeout, error_message empty on a failure branch |
| **MEDIUM (suggestion)** | Naming nitpick, helper extraction could be clearer |
| **LOW** | Formatting / typing polish |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00021",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "design|subprocess|parsing|rewriting|db_write|error_handling|conventions|testing",
      "file": "orch/daemon/migration_rebase.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "unit X passed, 0 failed",
  "notes": ""
}
```
