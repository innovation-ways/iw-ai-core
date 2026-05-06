# I-00072_S02_CodeReview_Backend_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed: testcontainers from pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. This step is review-only — do not run alembic at all.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00072 --json` (canonical).
- `ai-dev/active/I-00072/I-00072_Issue_Design.md` — Design document (Root Cause Analysis + Affected Components are the spec).
- `ai-dev/active/I-00072/reports/I-00072_S01_Backend_report.md` — S01 implementation report.
- All files in S01's `files_changed`: `orch/daemon/merge_queue.py`, `orch/cli/merge_queue_commands.py`, `dashboard/routers/actions.py`.

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_S02_CodeReview_Backend_report.md` — Review report.

## Context

You are reviewing the backend fix for **I-00072**. S01 was supposed to align the CLI's retry filter with the dashboard's, by extracting a shared `OPERATOR_RECOVERABLE_MERGE_STATUSES` constant in `orch/daemon/merge_queue.py` and importing it from both surfaces.

Your job is to verify the alignment is real, complete, and would survive being looked at by a second engineer in six months.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the changed files:

```bash
make lint
make format-check
```

If either reports NEW violations on the files in S01's `files_changed`, classify each as a **CRITICAL** finding with `"category": "conventions"`, the offending `file`/`line`, and the exact rule code/message. Do not auto-fix; only report.

If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Shared constant is in the right place and shape

- Is `OPERATOR_RECOVERABLE_MERGE_STATUSES` defined in `orch/daemon/merge_queue.py` at module scope?
- Is it a `frozenset[BatchItemStatus]` (not `set`, not `list`, not `tuple`) — so callers cannot mutate it?
- Does it contain **exactly four** members: `merge_failed`, `migration_invalid`, `migration_rebase_failed`, `migration_rolled_back`? If anything else (e.g., `failed`) is in the frozenset, that is a **CRITICAL** finding — the legacy `failed` path must be a separate code branch, not a member of the recoverable set.
- Is there a one-line comment explaining its purpose and referencing CR-00028? If absent, MEDIUM (fixable).

### 2. CLI / dashboard parity — no orphan local copies

This is the headline concern. Search both files for any remnant local definition:

```bash
grep -n "_retryable\|_ALLOWED_RETRY_STATUSES" orch/ dashboard/
```

- The only occurrences should be the **import** of `OPERATOR_RECOVERABLE_MERGE_STATUSES` and its usage in `BatchItem.status.in_(...)` clauses.
- If `orch/cli/merge_queue_commands.py` still has a local `_retryable` tuple, that's a **CRITICAL** finding — the parity is fake.
- If `dashboard/routers/actions.py` still has a local `_ALLOWED_RETRY_STATUSES` set, same — **CRITICAL**.
- If the CLI imports the constant but never uses it, **CRITICAL** — dead alignment.

### 3. Legacy back-compat path (CLI side)

The dashboard already accepts pre-CR-00028 `BatchItemStatus.failed` rows whose notes start with `"Merge failed"` (`dashboard/routers/actions.py:947-972`). S01 was supposed to mirror that into the CLI.

- Does the CLI try the new constant first, then fall back to the legacy lookup?
- Does the legacy lookup require both `status == BatchItemStatus.failed` **AND** `(notes or "").startswith("Merge failed")`? If either condition is missing, **CRITICAL**.
- When a `failed` row is found but the notes do NOT start with `"Merge failed"` (e.g., a setup-phase failure), does the CLI refuse with a clear error and non-zero exit? If a setup failure can be retried as a merge, that is a **CRITICAL** behavioural regression.

### 4. Audit, side effects, and exit codes preserved

- BatchItem.status flips from the recoverable status → `BatchItemStatus.completed`.
- WorkItem (if it was set to `failed` by `_revert_work_item`) flips back to `WorkItemStatus.completed`.
- A `merge_retry_requested` `DaemonEvent` is written with `event_metadata={"batch_item_id": …, "worktree_path": …}`. Note the field is `event_metadata` in Python (DB column is still `metadata` — see `orch/CLAUDE.md`).
- JSON-mode and human-mode output unchanged for the happy path.
- Exit codes unchanged: 0 on success; the existing `EXIT_UNKNOWN` for blocking errors.

### 5. No accidental scope expansion

S01 was scoped to ~3 files and a small diff. Anything beyond that is a yellow flag:

- New helper modules / refactored functions: **MEDIUM (suggestion)** at minimum, **HIGH** if it materially expands the surface area.
- Touching `abandon_merge`, `process_merge_queue`, the cascade logic, or any state machine: **CRITICAL** — out of scope. Open a separate ticket if needed.
- Touching tests: **CRITICAL** — that's S03's job; S01 must not pre-empt the failing test.

### 6. Project conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Specific items to verify:

- SQLAlchemy 2.0 `select()` style (already used).
- `from sqlalchemy import select` import position — the existing CLI function does it inside the function body to keep CLI startup fast; preserve that or note an explicit reason for moving it.
- The new `from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES` line should not pull the entire merge-queue module into CLI startup graph — verify there's no circular import. If `merge_queue.py` already imports from `orch.cli.*`, this is a **CRITICAL** finding (circular import will surface as runtime ImportError on first use).
- `BatchItemStatus` is already exported from `orch.db.models` — re-imports of it should be consolidated, not duplicated.

### 7. Security

- No hardcoded secrets, credentials, or API keys.
- The legacy `notes.startswith("Merge failed")` check operates on data we wrote ourselves; no untrusted input. OK.
- No SQL injection risk — all filtering goes through SQLAlchemy bound expressions.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `make test-unit` — must pass.
2. Report results accurately. The S03 reproduction test does NOT exist yet — that's correct; do not flag its absence.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks parity, missing constant member, circular import, legacy path missing, scope creep into tests | Must fix before merge |
| **HIGH** | Significant logic gap, exit-code regression, missing audit event | Must fix before merge |
| **MEDIUM (fixable)** | Missing constant comment, stale local copies, lint violation | Fix in fix cycle |
| **MEDIUM (suggestion)** | Refactoring opportunity not pursued | Optional |
| **LOW** | Style nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00072",
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

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM-fixable findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM-fixable.
