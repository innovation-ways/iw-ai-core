# I-00062_S02_CodeReview_Database_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step Being Reviewed**: S01 (Database)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection (`docker ps`, `docker inspect`, `docker logs`) and
`./ai-core.sh` / `make` targets are allowed. Testcontainer fixtures
spawned by pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB on port 5433. `alembic history/current/show` is allowed (read-only).
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- For runtime step state, prefer `uv run iw item-status I-00062 --json`.
- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document
- `ai-dev/active/I-00062/reports/I-00062_S01_Database_report.md` — S01 report
- All files listed in the S01 report's `files_changed`:
  - `orch/db/models.py`
  - `orch/db/migrations/versions/<id>_i_00062_add_worktree_db_credentials.py`

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S02_CodeReview_report.md` — review report

## Context

S01 added four columns (`worktree_db_host`, `worktree_db_name`,
`worktree_db_user`, `worktree_db_password`) to `BatchItem` and the
corresponding alembic migration. Verify the changes are correct,
reversible, and comply with project conventions.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files listed in S01's `files_changed`:

```bash
make lint
make format
```

If either reports NEW violations on the changed files, classify each as
**CRITICAL** with `"category": "conventions"`. If a tool is unavailable,
STOP and raise a blocker.

## Review Checklist (I-00062-specific)

### 1. ORM model changes (orch/db/models.py)

- All four columns are nullable (`nullable=True` / `Mapped[str | None]`).
  Non-nullable would break existing rows with no compose stack.
- Type is `Text`, not `String`, matching the existing `worktree_compose_path`
  column on the same model.
- Columns are placed **immediately after** `worktree_compose_path` so they
  read as a contiguous worktree-stack metadata block.
- No new indexes, constraints, or relationships added — these are pure
  metadata columns.
- No accidental edits to other tables, models, or unrelated columns.

### 2. Migration file (orch/db/migrations/versions/...)

- `revision` is a fresh 12-char hex (NOT a hand-picked memorable string).
- `down_revision` is **exactly** `"4876b3246ff2"`. Reject if it points
  anywhere else.
- File name follows `<revision_id>_i_00062_add_worktree_db_credentials.py`.
- `upgrade()` adds all four columns via `op.add_column()`.
- `downgrade()` drops all four columns in **reverse order** of additions.
- `nullable=True` on every `sa.Column(...)` in `upgrade()`.
- No data migration / backfill — purely structural.
- No `op.create_index`, `op.create_unique_constraint`, etc. added.

### 3. Alembic chain integrity

Run `cd .` and `uv run alembic history --verbose` (read-only). Confirm:
- The new revision is present at the head.
- There is exactly **one head** (no branching).
- The chain `4876b3246ff2 → <new>` is linear.

### 4. Project conventions

Read `orch/CLAUDE.md` and `CLAUDE.md`. Confirm:
- SQLAlchemy 2.0 `Mapped[]` declarative style is used.
- No psycopg2 references (psycopg v3 only).
- The migration's docstring includes the Issue ID (`I-00062`) and a
  one-line summary.

### 5. NO live-DB writes

Verify the S01 report does NOT claim to have run `alembic upgrade head`,
`alembic downgrade`, `alembic stamp`, or `make db-migrate` against the
live orch DB. If S01's `notes` or log mentions any such call, classify
as **CRITICAL** with `"category": "architecture"` — the agent violated
the migration policy.

### 6. Testcontainer round-trip evidence

The S01 report should include evidence that `make test-integration` (or
a focused testcontainer migration round-trip) confirms upgrade then
downgrade work cleanly. Missing evidence is **HIGH** severity.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and confirm no regressions. Report results
accurately.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Migration broken, live-DB write attempted, downgrade not reversible | Must fix |
| **HIGH** | Missing testcontainer evidence, wrong down_revision, non-nullable column | Must fix |
| **MEDIUM (fixable)** | Convention drift, column ordering, missing docstring | Should fix |
| **MEDIUM (suggestion)** | Better naming, additional cross-check | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00062",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM (fixable) findings.
