# I-00110_S05_CodeReview_Final_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network state-changing commands.
Allowed: testcontainers via pytest fixtures, read-only introspection (`docker ps/inspect/logs`), `./ai-core.sh` and `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orchestration DB. This step adds no migrations.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00110 --json`.
- `ai-dev/active/I-00110/I-00110_Issue_Design.md` -- Design document
- All implementation step reports:
  - `ai-dev/work/I-00110/reports/I-00110_S01_Backend_report.md`
  - `ai-dev/work/I-00110/reports/I-00110_S03_Tests_report.md`
- All per-agent code review reports:
  - `ai-dev/work/I-00110/reports/I-00110_S02_CodeReview_report.md`
  - `ai-dev/work/I-00110/reports/I-00110_S04_CodeReview_report.md`
- All files in the combined `files_changed`:
  - `dashboard/routers/keep_alive.py` (S01 — route-boundary fix)
  - `tests/dashboard/test_keep_alive_slot_overflow.py` (S03 — regression tests, new)
  - `tests/dashboard/test_schemathesis_contract.py` (S03 — allowlist deletion)

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of ALL implementation work for **I-00110**.

The cross-cutting surface for this incident is narrow but real: one route file (S01), one new test file (S03), and one allowlist edit (S03). The holistic question is whether the **whole** fix coheres — does the route bound (S01) + the test set (S03) + the schemathesis allowlist edit (S03) together close the loop the design promised?

## Read the Design Document FIRST

Before running the lint/format gate and before opening any changed files:

- Read `## Acceptance Criteria` in full — AC1 (bug is fixed), AC2 (regression test exists), AC3 (in-range still works) are all mandatory.
- Read `## TDD Approach` — six test functions are named by path. Cross-check every one against S01's report `files_changed` and the actual test file. Missing tests are CRITICAL.
- Read `## Notes` — the design explicitly rejects a service-layer try/except. Verify `orch/keep_alive_service.py` is NOT in any `files_changed`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the changed files → CRITICAL findings with `"category": "conventions"`. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Completeness vs Design Document

- All three acceptance criteria (AC1, AC2, AC3) are satisfied by the implementation:
  - AC1: Both handlers have `Path(..., ge=1, le=2**63 - 1)` (or equivalent `Annotated` form). Overflow → 422.
  - AC2: All six tests in `tests/dashboard/test_keep_alive_slot_overflow.py` pass. Both `KNOWN_CONTRACT_5XX` entries are removed from `tests/dashboard/test_schemathesis_contract.py`.
  - AC3: The two boundary tests (`test_*_at_bigint_max_does_not_500`) assert `status_code in (200, 404)` and pass — proving the bound does NOT reject legitimate maximum values.
- No TODO comments or placeholder implementations.
- No design requirements without corresponding code.

### 2. Cross-Agent Consistency

- This incident has TWO implementation steps (S01 Backend, S03 Tests). Verify:
  - S01's `Path(...)` bound covers BOTH handlers (DELETE and PATCH toggle).
  - S03's regression file covers BOTH endpoints in all six tests.
  - S03 removed BOTH `KNOWN_CONTRACT_5XX` entries (not just one — an asymmetric cleanup would leave one route still allowlisted).
  - The schemathesis contract test (when re-run by the QV `integration-tests` gate) stays GREEN — i.e., the route fix actually does prevent the 5xx the allowlist was masking.
  - No file was modified by BOTH S01 and S03 (would indicate scope confusion). S01 owns `dashboard/routers/keep_alive.py`; S03 owns `tests/dashboard/*`.

### 3. Integration Points

- The route fix and the test set wire together correctly: the six tests target the exact endpoints the route fix protects, with status-code assertions that match the new contract (422 for overflow/zero/negative, 200|404 for in-range/BIGINT_MAX).
- No import cycles, no orphan imports, no unused `Path` or `Annotated` import in `keep_alive.py`.

### 4. Test Coverage (Holistic)

- Are the happy path (in-range, valid IDs) AND error paths (overflow, zero, negative) covered? Yes — six tests.
- Does the schemathesis contract suite re-cover both routes after the allowlist deletion? Yes — `JSON_API_FUZZ_PATHS` recomputes from `JSON_API_PATHS` minus the (now empty) `KNOWN_CONTRACT_5XX`.

### 5. Architecture Compliance

- Read `CLAUDE.md` and `dashboard/CLAUDE.md`. The fix respects "routers are thin" (validation at boundary), the testcontainer rule (tests use the dashboard `client` fixture, no live DB), and the per-worktree DB rules.

### 6. Security (Cross-Cutting)

- The fix CLOSES a low-grade DoS smell (unauthenticated 5xx flood). Verify both routes are protected — an asymmetric fix is HIGH (one endpoint remains exploitable).
- No new attack surface introduced — `Path(...)` constraints are strictly subtractive on the accepted input space.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite** (both unit AND integration tests):
   ```bash
   make test-unit
   make test-integration
   ```
2. Report results accurately in the result contract.
3. If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability, missing requirement | Must fix before merge |
| **HIGH** | Significant bug, integration failure, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional |
| **LOW** | Nitpick, style preference | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00110",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL or HIGH findings AND zero MEDIUM (fixable). `fail` if any mandatory fixes needed.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
- `missing_requirements`: Any design requirement with no corresponding implementation. Each missing requirement is automatically CRITICAL.
- `cross_cutting`: `true` on findings that span multiple agents' work or affect integration points.
