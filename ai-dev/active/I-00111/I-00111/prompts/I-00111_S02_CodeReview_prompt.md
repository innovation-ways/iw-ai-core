# I-00111_S02_CodeReview_prompt

**Work Item**: I-00111 -- `GET /openapi.json` returns HTTP 500 — `create_app().openapi()` raises Pydantic `ForwardRef('Response')` error
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
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident does NOT touch any Alembic migration. If S01's diff contains a migration file, that is a CRITICAL scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00111 --json` is canonical.
- `ai-dev/active/I-00111/I-00111_Issue_Design.md` -- Design document
- `ai-dev/work/I-00111/reports/I-00111_S01_Backend_report.md` -- S01 step report
- All files listed in the S01 report's `files_changed`
- `tests/dashboard/test_schemathesis_contract.py:21-30` -- the test-module docstring describing the bug (reference for what "fixed" looks like)

## Output Files

- `ai-dev/work/I-00111/reports/I-00111_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the production-code fix done in step S01 by the Backend agent for **I-00111**.

The fix should be TINY (1-3 LOC) — a single import correction, a single annotation change, or a single `response_class=…` argument on a route decorator. Any diff larger than ~10 lines of production code is a scope-creep red flag.

Read the design document to understand what was intended. Read the S01 report to understand what was done. Then review all changed files.

## Read the Design Document FIRST

- Read `## Acceptance Criteria` (AC1, AC2, AC3) — for S02 only AC1 applies (AC2 and AC3 are S03's deliverables).
- Read `## Root Cause Analysis` — note the three candidate fault patterns. S01's report MUST name which of the three was the actual fault, with a specific file:line.
- Read `## Fix Plan` row for S01 — the fix is intentionally scoped to "reproduce + bisect + smallest fix", NOT a refactor.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run on the files listed in S01's `files_changed`. Fix nothing yourself — only report.

```bash
make lint
make format-check
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `"category": "conventions"`, `"file"` and `"line"` from the tool output, and `"description"` quoting the exact violation code and message.

## Review Checklist

### 1. Correct root cause located via reproducible traceback (not guessed)

- The S01 report MUST include the captured `ForwardRef` traceback verbatim in `tdd_red_evidence` or `notes`.
- The traceback MUST name a specific route function or Pydantic model class — and that name MUST appear in the file the diff touches.
- If S01 says "I think the cause is X" without a captured traceback supporting it, raise a **HIGH** finding ("guessed root cause without reproduction evidence").

### 2. Fix is the smallest possible change

- Count the lines of production code added/removed in the diff (`git diff origin/main --stat -- 'dashboard/**' 'orch/**' ':!tests/**'`).
- Expected: 1-3 net LOC. Up to ~10 LOC is acceptable if the fix legitimately requires moving an import out of `TYPE_CHECKING:` (which adds an import line + removes the guard line).
- More than 10 LOC of production change → **HIGH** finding ("fix scope exceeds the design's 'smallest possible change' constraint — likely smuggled refactor"). Itemise the lines that are NOT strictly the fix.
- Renamed identifiers, reformatted blocks, added comments, or "improvements" to neighbouring code → each is a separate **MEDIUM (fixable)** finding ("scope creep").

### 3. Diff stays inside `scope.allowed_paths`

```bash
git diff origin/main --name-only
```

- Every changed file MUST be inside `scope.allowed_paths`: `dashboard/routers/**`, `dashboard/app.py`, `orch/**`, `tests/dashboard/test_schemathesis_contract.py`, `tests/dashboard/test_openapi_schema.py`.
- S01 should NOT have touched `tests/dashboard/test_schemathesis_contract.py` (that's S03's job).
- S01 should NOT have touched `tests/dashboard/test_openapi_schema.py` (that's S03's job — the file doesn't exist yet).
- Any file outside scope → **CRITICAL** finding.

### 4. Report includes fault-pattern statement

The S01 report's `notes` MUST identify which of the three candidate root causes was the actual fault (route-signature ForwardRef / response-model ForwardRef / `__future__ annotations` + `TYPE_CHECKING:` import). If the field is missing or vague, raise a **MEDIUM (fixable)** finding ("S01 report missing fault-pattern classification — required for S05 cross-agent review").

### 5. Post-fix verification ran and passed

The S01 report MUST contain the output of both verification commands from Requirement #4 of the S01 prompt:

- `uv run python -c 'from dashboard.app import create_app; ... assert "paths" in s and len(s["paths"]) > 0; print("OK:", ...)'`
- `uv run python -c 'from fastapi.testclient import TestClient ... print("status:", r.status_code, "paths:", len(r.json().get("paths", {})))'`

Both must show non-zero path counts and `status: 200`. If either is missing, raise a **HIGH** finding.

### 6. No new tests, no production refactor, no migration

- New test files → **HIGH** finding ("S03 owns the regression tests; S01 must not add them").
- New alembic migration → **CRITICAL** finding ("incident is a 1-3 LOC type-annotation fix; no schema change involved").
- Production code outside the offending route/model → **MEDIUM (fixable)** finding.

### 7. CLAUDE.md compliance

- If the fix touches `dashboard/routers/**`, did S01 follow the dashboard-router patterns (Jinja2 % formatting, htmx fragment conventions)? Mostly N/A for a one-line annotation fix, but flag any drift.
- If the fix touches `orch/**`, are SQLAlchemy / Pydantic conventions intact?

## Test Verification (NON-NEGOTIABLE)

1. Run the project's unit test command (`make test-unit`) to verify no regressions from the fix.
2. Report test results accurately in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, scope-allowed-paths violation, unauthorised migration | Must fix before merge |
| **HIGH** | Guessed root cause without reproduction evidence, missing required verification output, missing AC1 evidence, new tests in S01, fix exceeds smallest-change bound | Must fix before merge |
| **MEDIUM (fixable)** | Missing fault-pattern statement, scope creep in adjacent code, convention drift | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00111",
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

- `verdict`: `pass` if zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. `fail` otherwise.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM (fixable) findings.
