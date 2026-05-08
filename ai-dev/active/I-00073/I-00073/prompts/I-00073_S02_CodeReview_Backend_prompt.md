# I-00073_S02_CodeReview_Backend_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
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

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orch DB.
Read-only commands (`alembic history`, `alembic current`, `alembic show`) are fine.

This incident MUST NOT add or modify migrations — if you find S01 created or
modified anything under `orch/db/migrations/versions/`, that is an automatic
**CRITICAL** finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00073 --json`.
- `ai-dev/active/I-00073/I-00073_Issue_Design.md` — Design document
- `ai-dev/active/I-00073/reports/I-00073_S01_Backend_report.md` — S01 implementation report
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00073/reports/I-00073_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the Backend implementation in S01 for **I-00073**.

The fix narrows the SQL projection on every agent-facing CLI read of `StepRun`, `WorkItem`, and `WorkflowStep` so that adding columns to those tables in a worktree does not break `iw step-done` / `iw step-fail` / etc. against the live orchestration DB.

Read the design document for the full callsite enumeration in the Root Cause Analysis section. Then read S01's report and every file it changed.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run these on the files in S01's `files_changed`:

```bash
make lint
make format
```

If either reports NEW violations in changed files (versus `main`), classify each as a **CRITICAL** finding with `"category": "conventions"`, `"file"`, `"line"`, and the exact violation code/message. Do not fix them yourself.

## Review Checklist

### 1. Architecture Compliance

- Confirm the fix lives entirely in `orch/cli/step_commands.py`, `orch/cli/item_commands.py`, and `docs/IW_AI_Core_Agent_Constraints.md`. Any change under `orch/daemon/`, `orch/db/`, `orch/db/migrations/versions/`, or any other directory is an automatic **CRITICAL** finding (see AC3 of the design — daemon is intentionally untouched).
- Confirm no migration file was added or modified.
- Confirm the fix does not introduce any `try/except UndefinedColumn` fallback (option (b) of the design — explicitly rejected).

### 2. Callsite Coverage

Walk the design's Root Cause Analysis table and confirm every listed callsite was patched. The table covers TWO shapes — Shape A (`select(Model).where(...)`) and Shape B (`session.get(Model, key)`). Both must be rewritten to be column-projected. For each callsite:
- Open the file at the listed line.
- For Shape A: confirm the `select(Model)` is now column-projected (via `load_only(...)` or explicit column list).
- For Shape B (`session.get(WorkItem, ...)`): confirm it has been rewritten as `session.execute(select(WorkItem).options(load_only(...)).where(...)).scalar_one_or_none()`. **If any `session.get(WorkItem, ...)` from the RCA table remains as-is, that is a CRITICAL finding** — `session.get` emits a full-column SELECT on identity-map miss and re-introduces the bug.
- Confirm the projected column set includes every attribute that any caller of the loaded entity reads or writes downstream — read the full enclosing function, not just the SELECT line.

Specifically verify these shape-B callsites in `orch/cli/item_commands.py` were rewritten (lines per RCA): 249, 416, 542, 605, 718, 854.

Specifically verify these shape-A WorkflowStep callsites in `orch/cli/step_commands.py` were rewritten: 141 (`_get_workflow_step` helper — cascades to many commands), 622, 730.

If a callsite from the Root Cause table is unpatched, that is a **CRITICAL** finding (`category: completeness`).

If the projected column set is missing a column the caller actually uses, that is a **CRITICAL** finding (`category: code_quality`) — it would cause an `AttributeError` or detached-attribute load at runtime.

### 3. Pinned Column Set Quality

- Is the pinned column set defined as a module-level constant (or two — one per relevant model)?
- Is it named in a way that makes its purpose obvious (`_STEP_RUN_CLI_COLUMNS` or similar)?
- Does it use `Mapped` attribute references rather than string column names? (References are safer — they fail at import time if the attribute is renamed.)

Style nits → MEDIUM (suggestion). A missing or wrong column in the set → CRITICAL.

### 4. Documentation

- Is there a module docstring at the top of `orch/cli/step_commands.py` (and `orch/cli/item_commands.py` if patched) explaining the rule?
- Is there a new "CLI resilience to in-flight schema drift" subsection in `docs/IW_AI_Core_Agent_Constraints.md`? Does it reference incident I-00073?
- If documentation is missing → HIGH finding (`category: completeness`).

### 5. Project Conventions

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- SQLAlchemy 2.0 style, psycopg v3 driver, Click 8.1+ patterns.
- No tests connected to the live DB (port 5433) — the existing tests must use testcontainers.

### 6. Behavior Preservation

- Run `make test-unit` and `make test-integration`. Existing tests under `tests/unit/cli/` and `tests/integration/cli/` MUST still pass — the projected reads must yield entities indistinguishable from the prior full-ORM reads for every existing caller.
- If any test fails, that is a **CRITICAL** finding.
- Public surface of every CLI command (JSON output schema, exit codes, error messages, click options) must be byte-identical. Any change → CRITICAL.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit`.
2. Run `make test-integration`.
3. Report results accurately.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, missed callsite, daemon file modified, migration file added/modified | Must fix before merge |
| **HIGH** | Missing docstring/policy note, projected set missing a non-load-bearing column | Must fix before merge |
| **MEDIUM (fixable)** | Naming, helper extraction not done where it'd clearly help | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Style improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00073",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing|completeness",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "..."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
