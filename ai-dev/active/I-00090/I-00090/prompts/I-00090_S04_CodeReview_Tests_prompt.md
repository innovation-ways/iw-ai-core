# I-00090_S04_CodeReview_Tests_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step Being Reviewed**: S03 (tests-impl)
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

Testcontainers spun up by pytest fixtures are exempt. Read-only
introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Alembic upgrade/downgrade/stamp commands against live DBs are prohibited
from agent context. This item does not generate any migration.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00090 --json`
- `ai-dev/active/I-00090/I-00090_Issue_Design.md` -- Design document (especially § "TDD Approach" — lists all 16 mandatory tests by name)
- `ai-dev/active/I-00090/reports/I-00090_S03_Tests_report.md` -- S03 report
- `tests/dashboard/test_running_router_active_filter.py` -- the test file under review
- `dashboard/routers/running.py` -- the code being tested
- `skills/iw-ai-core-testing/SKILL.md` -- the project's testing standards (assertion strength, live-DB write guard, cross-project isolation, RED-flag checklist)

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_S04_CodeReview_Tests_report.md` -- Review report

## Context

You are reviewing the test coverage added in step S03 by `tests-impl` for I-00090. The fix (S01) added an active-item predicate to two SQL query helpers; this review must ensure the new test file proves the bug existed, exercises every status branch the design names, and uses semantically strong assertions (not just shape checks).

## Read the Design Document FIRST

Read `ai-dev/active/I-00090/I-00090_Issue_Design.md`. In particular:

- Read § "TDD Approach" in full. **Write down each of the 16 mandatory test names by hand**: tests 1–8 for `_query_failed_steps`, tests 9–14 for `_query_recent_completions`, tests 15–16 for the routes. Carry the list into your Review Checklist below as a first-class anchor.
- Cross-check every test name against the actual file. **Any missing test name from the design is a CRITICAL finding.**

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violation in `tests/dashboard/test_running_router_active_filter.py` is a CRITICAL finding.

## Review Checklist

### 1. Coverage Completeness (CRITICAL)

- All 8 `_query_failed_steps` tests present and named per the design.
- All 6 `_query_recent_completions` tests present and named per the design.
- Both route-level smoke tests (15, 16) present.
- Test count totals **16**. Anything less is a CRITICAL "missing requirement" finding.

### 2. RED-First Reproduction Evidence (HIGH)

- `test_query_failed_steps_excludes_completed_item` is the designated REPRODUCTION test (per design § "TDD Approach").
- S03's `tdd_red_evidence` field MUST contain a textual reasoning sentence explaining why the assertion would fail against pre-S01 code.
- Reason about this yourself: would `assert "CR-DEAD" not in [r.item_id for r in rows]` (where the seeded item is `WorkItem(id="CR-DEAD", status=completed)` with a failed step) actually fail against pre-S01's unfiltered query? Answer YES — the unfiltered query returns the row, so the assertion fails. State this reasoning in your review report.
- Do NOT ask S03 to perform a runtime source-revert or stash-recheck to "produce" RED evidence — that workflow is prohibited (see I-00073 / iw-review-design). The textual reasoning is sufficient and is what the S03 prompt requires.

### 3. Assertion Strength (HIGH)

Every assertion MUST be semantically strong. Reject as HIGH if you find:

- `assert "failed" in body` (shape-only, matches everything)
- `assert len(rows) > 0` standalone (says nothing about which row)
- `assert len(rows) == N` standalone (brittle, says nothing about which row)
- `assert "permissions" in data`-style shape checks

Accept and prefer:

- `assert "I-DEAD" not in [r.item_id for r in rows]`
- `assert any(r.item_id == "I-ALIVE" for r in rows)`
- `assert "I-ALIVE" in response.text and "I-DEAD" not in response.text` (item IDs are unique tokens, so this is semantically strong)

The CSS-class-name false-positive rule (I-00067) does not apply to item-id assertions because item IDs are unique tokens; do not flag those.

### 4. Test Isolation & Determinism (HIGH)

- No test depends on another test's seed (pytest-randomly resilience).
- Every test creates its own `Project` + `WorkItem` rows with names that won't collide if multiple tests run in any order (use distinct project IDs or unique item IDs per test, e.g. `f"p-{test_name}-1"`).
- No `time.sleep`, no real network calls.
- The `db_session` fixture is testcontainer-backed; tests MUST NOT import `orch.db.session.SessionLocal` directly (live-DB write guard will fail them).

### 5. Project-Filter Regression (MEDIUM_FIXABLE)

Test 8 (`test_query_failed_steps_respects_project_filter`) MUST seed two distinct projects and verify the per-project filter still works after the new predicate is added. If missing OR only seeds one project, raise MEDIUM_FIXABLE.

Test 16 (`test_project_running_route_renders_active_item_only`) MUST seed two projects and verify rows from project B do not appear in the project-A request. If missing, raise MEDIUM_FIXABLE.

### 6. Helper-vs-Route Coherence (MEDIUM_SUGGESTION)

The route-level tests use the dashboard `client` fixture. The helper-level tests should use the `db_session` fixture directly. If S03 uses `client.get(...)` in helper-level tests (introducing unnecessary route overhead), that's a MEDIUM_SUGGESTION (acceptable but not ideal).

### 7. Cleanup & Style (LOW)

- Module docstring identifies the work item (I-00090).
- Small private helper functions (`_make_project`, `_make_item`, …) are at the top of the file.
- Imports organized (stdlib, third-party, local).

### 8. TDD RED Evidence — exempt for tests-impl

Per the per-agent review template § 5a: "Dedicated coverage steps (`tests-impl`) are exempt" from the RED-first behavioural test gate. Do NOT raise findings about missing RED evidence on the Tests step — that's the Backend step's responsibility, and S01 legitimately deferred RED to this step. However, you DO check that the `tdd_red_evidence` field in the S03 report is populated per § 2 above.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

```bash
uv run pytest tests/dashboard/test_running_router_active_filter.py -v
```

All 16 tests MUST pass. Report results accurately.

Then run `make test-unit` to verify no unit-test regressions elsewhere.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing required tests from the design, lint/format violation, file in wrong location, fixture-not-found error |
| **HIGH** | Shape-only assertions, no RED reasoning in report, test depends on another test's seed, uses live DB |
| **MEDIUM_FIXABLE** | Missing project-filter regression coverage, missing docstring, brittle `assert len() == N` |
| **MEDIUM_SUGGESTION** | Helper extraction would improve readability |
| **LOW** | Naming nit, comment suggestion |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00090",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/dashboard/test_running_router_active_filter.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "16 passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
