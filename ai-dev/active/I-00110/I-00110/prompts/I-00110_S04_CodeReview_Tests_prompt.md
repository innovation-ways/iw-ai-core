# I-00110_S04_CodeReview_Tests_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

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
- `ai-dev/active/I-00110/I-00110_Issue_Design.md` -- Design document (especially `## Test to Reproduce` — the verbatim test code S03 must have copied)
- `ai-dev/work/I-00110/reports/I-00110_S03_Tests_report.md` -- S03 tests step report
- All files in S03's `files_changed`:
  - `tests/dashboard/test_keep_alive_slot_overflow.py` (new)
  - `tests/dashboard/test_schemathesis_contract.py` (modified — allowlist deletion)

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the regression test suite + schemathesis allowlist edit done in step S03 by Tests for **I-00110**.

The route-boundary fix itself was reviewed in S02; do NOT re-review `dashboard/routers/keep_alive.py` here unless S03 modified it (which it should not — that would be a scope violation).

Read the design document first to understand the exact test contract (six tests named by name, assertion shape, file location). Read S03's report to understand what was done. Then review the changed files.

## Read the Design Document FIRST

Before running the lint/format gate and before opening any changed files:

- Read `## Test to Reproduce` — the design specifies SIX tests by exact name and the assertion content for each. Every one must appear in `tests/dashboard/test_keep_alive_slot_overflow.py`. Missing tests are CRITICAL findings.
- Read `## Acceptance Criteria` — AC2 (regression test exists + both KNOWN_CONTRACT_5XX entries removed) is what S03 must satisfy.
- Read `## TDD Approach` — S03 is a dedicated coverage step (`tests-impl`), exempt from RED-first. S03's `tdd_red_evidence` should be the `"n/a — …"` form. If S03 instead claims to have done a runtime stash/checkout to verify RED, that is a HIGH finding (workflow contract violation).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these commands on the files in S03's `files_changed`:

```bash
make lint          # ruff check
make format        # ruff format --check
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `"category": "conventions"`, the `"file"` and `"line"` from the tool output, and `"description"` quoting the exact violation code.

If a command is unavailable, STOP and raise a blocker. Do NOT skip.

## Review Checklist

### 1. Test File Completeness

The new file `tests/dashboard/test_keep_alive_slot_overflow.py` MUST contain exactly six tests, named exactly as in the design:

- `test_delete_slot_overflow_returns_422_not_500`
- `test_toggle_slot_overflow_returns_422_not_500`
- `test_delete_slot_at_bigint_max_does_not_500`
- `test_toggle_slot_at_bigint_max_does_not_500`
- `test_delete_slot_zero_returns_422`
- `test_toggle_slot_negative_returns_422`

Each missing test is a CRITICAL finding. Each renamed test is a HIGH finding (the design names them by exact identifier for grep-ability and tracking).

### 2. Test File Location

The new file MUST live under `tests/dashboard/` — NOT `tests/unit/` or `tests/integration/`. The `client` fixture is registered only in `tests/dashboard/conftest.py`; a test placed elsewhere fails with `fixture 'client' not found` (I-00067 gotcha). Wrong location is a CRITICAL finding.

### 3. Assertion Quality (Semantic, not Shape-Only)

Every assertion MUST verify SPECIFIC values, not just response shape (I003 lesson):

- The two `*_overflow_returns_422_not_500` tests MUST assert:
  - `resp.status_code == 422` (specific status, not `!= 500`)
  - `"detail" in body` (shape — allowed only when paired with the next assertion)
  - `any("slot_id" in str(err.get("loc", ())) for err in body["detail"])` (semantic — verifies the validator names the right field)
- The two `*_at_bigint_max_does_not_500` tests MUST assert:
  - `resp.status_code in (200, 404)` — NOT `!= 500` (under-constrained, accepts 422 which would be a regression) and NOT `== 404` (over-constrained, fails if a slot at BIGINT_MAX exists in seed data)
- The two `*_zero_returns_422` / `*_negative_returns_422` tests MUST assert `resp.status_code == 422`.

Shape-only assertions like `assert "detail" in body` standalone are a HIGH finding.

### 4. Schemathesis Allowlist Cleanup

In `tests/dashboard/test_schemathesis_contract.py`:

- BOTH entries removed: `"/api/keep-alive/slots/{slot_id}"` AND `"/api/keep-alive/slots/{slot_id}/toggle"`. Only one removed is HIGH (the asymmetric fix leaves one route still allowlisted).
- The `KNOWN_CONTRACT_5XX` dict itself is preserved (now empty: `KNOWN_CONTRACT_5XX: dict[str, str] = {}`). Deleting the dict declaration entirely is MEDIUM (fixable) — future incidents may re-populate it.
- The surrounding comment block (lines 88-96-ish in the pre-S03 file) is preserved.
- The `JSON_API_FUZZ_PATHS` derivation is UNCHANGED — the filter is the source of truth and recomputes automatically. Manual additions to `JSON_API_PATHS` or `JSON_API_FUZZ_PATHS` are HIGH (scope violation).

### 5. Scope Check

S03's `files_changed` MUST be exactly two entries:

- `tests/dashboard/test_keep_alive_slot_overflow.py` (new)
- `tests/dashboard/test_schemathesis_contract.py` (modified)

If `dashboard/routers/keep_alive.py` appears (already modified by S01) or any other file is present, that is a HIGH finding (scope violation).

### 6. TDD Evidence

- `tdd_red_evidence` MUST use the `"n/a — dedicated coverage step; RED evidence is in S01 report (...)"` form.
- The `notes` field MUST contain per-test reasoning about why each test would have failed against pre-S01 code (e.g. `AssertionError: assert 500 == 422`).
- No `git stash` / `git checkout` / source-revert evidence. If the report shows any such commands were run, that is a HIGH finding (forbidden by workflow contract).

### 7. Project Conventions

- Read `CLAUDE.md` and `tests/CLAUDE.md` for project conventions.
- pytest-randomly is on by default — the new tests are stateless (no DB writes), so order independence is automatic. Confirm no module-scope state was introduced.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review, run:

```bash
uv run pytest tests/dashboard/test_keep_alive_slot_overflow.py -v --no-cov
make test-unit
```

Both must exit 0. Report results accurately in the result contract.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, missing required test, wrong file location | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, scope violation, shape-only assertion | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00110",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "testing|conventions|scope|architecture",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "tests/dashboard/test_keep_alive_slot_overflow.py: 6 passed; make test-unit: X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL or HIGH findings AND zero MEDIUM (fixable). `fail` if any mandatory fixes needed.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
