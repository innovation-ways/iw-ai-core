# I-00059_S02_CodeReview_Backend_prompt

**Work Item**: I-00059 -- Doc Generation Job Detail Page Shows No Error Info or Parameters
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00059 --json`
- `ai-dev/active/I-00059/I-00059_Issue_Design.md` — Design document
- `ai-dev/active/I-00059/reports/I-00059_S01_Backend_report.md` — S01 implementation report
- `orch/jobs/aggregator.py` — The changed file

## Output Files

- `ai-dev/active/I-00059/reports/I-00059_S02_CodeReview_Backend_report.md` — Review report

## Context

You are reviewing the implementation work done in step S01 by the Backend agent for **I-00059**.

The fix aligned `_get_doc_generation`'s `raw` dict with `_fetch_doc_generation` in `orch/jobs/aggregator.py`. Review that the fix is correct, complete, and hasn't introduced any regressions.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run:

```bash
make lint
make format-check
```

Report any new violations in changed files as CRITICAL findings.

## Review Checklist Focus

### Key correctness checks

1. **Field completeness**: Does `_get_doc_generation`'s `raw` dict contain ALL fields that `_fetch_doc_generation` builds? Compare them side by side. Any missing field is a HIGH finding.

2. **Field value correctness**: Are the values assigned from the correct `job.*` attributes? (E.g., `error` from `job.error`, not `job.error_message` which doesn't exist.)

3. **`triggered_by` alignment**: Does `_get_doc_generation`'s `JobRow` use `job.skill_used or job.trigger_reason` for `triggered_by`, matching the list path?

4. **No scope creep**: The fix must be limited to `orch/jobs/aggregator.py`. Any changes to templates, routes, or other files are out of scope and should be flagged.

5. **Helper method (if introduced)**: If the agent extracted a `_build_doc_generation_raw` helper, verify both `_fetch_doc_generation` and `_get_doc_generation` call it, and the helper is private (underscore-prefixed).

6. **Reproduction test**: Verify the TDD RED phase was followed — confirm a reproduction test was written in `tests/integration/` and that it semantically verifies specific field values (not just that `raw` is non-empty).

### Standard checks

- Architecture compliance (jobs layer is read-only, no DB writes)
- Type annotations consistent with existing code
- No unused imports introduced

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit && make test-integration` and report results.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing field in raw dict, wrong attribute name, scope creep to template/route |
| **HIGH** | `triggered_by` not aligned, helper method inconsistency |
| **MEDIUM (fixable)** | Missing type annotation, unused import |
| **LOW** | Style, naming nit |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00059",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
