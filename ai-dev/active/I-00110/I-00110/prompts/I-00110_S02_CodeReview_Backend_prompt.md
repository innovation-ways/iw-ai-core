# I-00110_S02_CodeReview_Backend_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
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

You MUST NOT run alembic upgrade/downgrade/stamp commands against the live orchestration DB. This step adds no migrations.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00110 --json`.
- `ai-dev/active/I-00110/I-00110_Issue_Design.md` -- Design document
- `ai-dev/work/I-00110/reports/I-00110_S01_Backend_report.md` -- Backend step report
- All files in S01's `files_changed`:
  - `dashboard/routers/keep_alive.py`

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the route-boundary fix done in step S01 by Backend for **I-00110**.

S01's responsibility is the `Path(...)` bound on the two keep-alive slot handlers AND the pre-/post-fix in-process reproduction that captures the 500→422 transition. The regression test suite is the deliverable of S03 (tests-impl), which has NOT run yet — so do NOT flag the absence of `tests/dashboard/test_keep_alive_slot_overflow.py`; that file is S03's concern.

Read the design document first to understand what was intended (especially the rationale for 422 over 404 and for NOT adding a service-layer try/except). Read S01's report to understand what was done. Then review the changed file.

## Read the Design Document FIRST

Before running the lint/format gate and before opening any changed files:

- Read `## Acceptance Criteria` in full — AC1 (overflow → 422) is the part S01 must satisfy; AC2 (regression tests + allowlist removal) is S03's responsibility and is NOT in scope for S02.
- Read `## TDD Approach` — under the Backend → Tests split, S01 owns the RED evidence (in-process pre-fix probe). The S01 report MUST contain pre-fix status codes (both 500) and post-fix status codes (both 422) in `tdd_red_evidence`.
- Read `## Notes` — the design explicitly rejects the service-layer try/except. If S01 modified `orch/keep_alive_service.py`, that is a HIGH finding (scope violation + masks future legitimate overflow bugs).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these commands on the files in S01's `files_changed`:

```bash
make lint          # ruff check
make format        # ruff format --check
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `"category": "conventions"`, the `"file"` and `"line"` from the tool output, and `"description"` quoting the exact violation code.

If a command is unavailable, STOP and raise a blocker. Do NOT skip.

## Review Checklist

### 1. Architecture Compliance

- The fix lives at the FastAPI route boundary (`dashboard/routers/keep_alive.py`) — correct per `dashboard/CLAUDE.md` ("routers are thin, validation belongs at the route boundary").
- `orch/keep_alive_service.py` must be **untouched**. If S01 modified it (e.g., added a try/except for `psycopg.errors.NumericValueOutOfRange`), that is a HIGH finding — the design explicitly rejected this approach.
- The `Annotated[int, Path(ge=1, le=_BIGINT_MAX)]` constraint matches FastAPI idiom. If S01 used the default-parameter form (`slot_id: int = Path(...)`), that is a LOW informational finding — the `Annotated` form is preferred but the default form also works; do not block.

### 2. Code Quality

- The magic number `2**63 - 1` MUST be a named module-level constant (the design says `_BIGINT_MAX`). If it appears inline twice without a constant, that is a MEDIUM (fixable) finding — DRY violation.
- The constant MUST have a short comment explaining WHY (the BIGINT column constraint + the I-00110 reference). Missing comment is MEDIUM (suggestion).
- Imports should include `Path` from `fastapi` AND `Annotated` from `typing` (if the modern idiom is used).
- Both handlers should be updated consistently — same constraint, same constant. Asymmetric fixes are HIGH.
- S01 must NOT have created any test file. If `tests/dashboard/test_keep_alive_slot_overflow.py` appears in S01's `files_changed`, that is a HIGH finding (scope violation — tests belong to S03).

### 3. Project Conventions

- Read `CLAUDE.md` and `dashboard/CLAUDE.md` for project conventions.
- Coding conventions: `ruff format` is the formatter, `ruff check` is the linter, `mypy` is the type checker.

### 4. Security

- No hardcoded secrets, credentials, or API keys.
- Input validation moved to the route boundary — that IS the security fix. Confirm both routes have it; an asymmetric fix leaves one of the two endpoints vulnerable to the same 5xx flood.

### 5. TDD RED Evidence (behaviour-implementing step)

S01 owns the RED evidence under the Backend → Tests split. Verify:

1. **`tdd_red_evidence` is present and plausible.** It MUST contain TWO probes:
   - Pre-fix probe: both endpoints returning HTTP 500 with a `psycopg.errors.NumericValueOutOfRange` (or equivalent BIGINT-overflow) summary.
   - Post-fix probe: both endpoints returning HTTP 422 with `slot_id` in `detail[].loc`.
2. **The probe is in-process** — uses `create_app()` + `TestClient`, NOT a running dashboard server (no `curl localhost:9900`). The agent should not have started the dashboard.
3. **No runtime source-revert** — the agent MUST NOT have done `git stash` / `git checkout` to "verify" RED. The pre-fix probe ran BEFORE the fix was applied; the post-fix probe ran AFTER. If the report shows any evidence of stash/checkout, that is a HIGH finding.

If `tdd_red_evidence` is missing, fabricated, or shows only one of the two probes, that is a HIGH finding.

## Test Verification (NON-NEGOTIABLE)

S01 did NOT create test files (the regression suite is S03's deliverable). Your review's "test verification" is:

```bash
make test-unit
```

This catches any incidental unit-test regressions caused by S01's edit to `keep_alive.py`. Targeted dashboard test runs are NOT meaningful at this stage because the new regression file does not exist yet.

Report results accurately in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation, scope violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00110",
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
  "test_summary": "make test-unit: X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL or HIGH findings AND zero MEDIUM (fixable). `fail` if any mandatory fixes needed.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
