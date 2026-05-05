# I-00069_S02_CodeReview_Backend_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Same policy as S01 — read-only docker introspection only. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch migrations. Read-only alembic commands only.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00069 --json`. The `workflow-manifest.json` is a design-time snapshot.
- `ai-dev/active/I-00069/I-00069_Issue_Design.md` — Design document
- `ai-dev/active/I-00069/reports/I-00069_S01_Backend_report.md` — S01 implementation report
- All files listed in S01's `files_changed` (expected: `dashboard/app.py`)

## Output Files

- `ai-dev/active/I-00069/reports/I-00069_S02_CodeReview_Backend_report.md` -- Review report

## Context

You are reviewing the backend implementation in step S01 for **I-00069**.

The change is small (~5–8 lines): `dashboard/app.py:142-150` should now
catch `LiveDbConnectionRefusedError` separately and log at DEBUG (test
context) or WARNING (otherwise), no traceback. The generic `except
Exception` path must remain at ERROR with traceback.

Read the design document's **Code Changes** and **Acceptance Criteria**
sections. Then read `dashboard/app.py` and confirm the change matches.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint          # ruff check
make format-check  # ruff format --check (does NOT auto-fix)
```

If either reports NEW violations in changed files vs `main`, classify each as
a **CRITICAL** finding with `category: "conventions"`, `file`, `line`, and
the exact violation code/message in `description`.

## Review Checklist

### 1. Architecture Compliance

- Does the import of `LiveDbConnectionRefusedError` go through
  `orch.db.live_db_guard` (not e.g. a re-export)?
- Layer boundary: `dashboard/` importing from `orch/` is OK.
- Are layer boundaries respected (no `orch/` change made)?

### 2. Correctness

- Is `LiveDbConnectionRefusedError` caught **before** the generic `except Exception`? (Order matters — `LiveDbConnectionRefusedError` is a `RuntimeError` subclass.)
- Is the test-context check `os.environ.get("IW_CORE_TEST_CONTEXT") == "true"` (string comparison, not truthiness)? Mismatched casing or `bool()` would silently break.
- Does the DEBUG/WARNING branch use `logger.debug` / `logger.warning` (NOT `logger.exception`)? The whole point is no traceback.
- Does the generic `except Exception` branch still call `logger.exception(...)` at ERROR with traceback?
- In ALL branches, is `app.state.alembic_guard_status = None` set? Behaviour-preserving.

### 3. No Regressions

- The dashboard middleware path
  (`dashboard/middlewares/alembic_guard.py:54-58`) is untouched.
- The daemon path (`orch/daemon/main.py:147`) is untouched.
- `orch/db/live_db_guard.py` is untouched (the guard contract is sacred).
- `check_db_at_head()` in `orch/db/alembic_guard.py` is untouched.
- The success path (when `check_db_at_head()` returns a `GuardStatus`)
  is unchanged: `app.state.alembic_guard_status = check_db_at_head()`
  still runs at the top of the `try`.

### 4. Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`.
- Logger naming: existing `logger = logging.getLogger(__name__)` reused.
- Comment minimality: only WHY-comments, no WHAT-comments.
- Import order matches the existing top-of-file structure.

### 5. Security

- No hardcoded secrets / credentials.
- No new env-var reads beyond `IW_CORE_TEST_CONTEXT` (already widely used in the codebase).

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` and confirm zero failures.
2. Report results in the contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss, security vuln | Must fix |
| **HIGH** | Significant bug, missing requirement | Must fix |
| **MEDIUM (fixable)** | Code quality / convention violation | Should fix |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00069",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "dashboard/app.py",
      "line": 0,
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

- `verdict`: `pass` if zero CRITICAL/HIGH and zero MEDIUM_FIXABLE; otherwise `fail`.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
