# I-00034_S05_CodeReview_Final_prompt

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

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

## Input Files

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- Design document
- All implementation step reports:
  - `ai-dev/active/I-00034/reports/I-00034_S01_Backend_report.md`
  - `ai-dev/active/I-00034/reports/I-00034_S03_Tests_report.md`
- All per-agent code review reports:
  - `ai-dev/active/I-00034/reports/I-00034_S02_CodeReview_Backend_report.md`
  - `ai-dev/active/I-00034/reports/I-00034_S04_CodeReview_Tests_report.md`
- All files listed in `files_changed` across the implementation reports

## Output Files

- `ai-dev/active/I-00034/reports/I-00034_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of the I-00034 fix. The goal is to catch cross-cutting issues that per-agent reviews could not:

- Does the Backend change (S01) integrate with the tests (S03) to actually prove the bug is fixed?
- Are there any AC items left uncovered by the combined work?
- Did anyone touch out-of-scope code (daemon, CLI, ORM models, migrations)?
- Does the full test suite pass, not just the new module?

Read the design document for the full intended scope. Read all implementation and review reports. Then review all changed files holistically.

## Review Checklist

### 1. Completeness vs Design Document — Acceptance Criteria coverage (CRITICAL)

Tick through each AC from the design doc and verify concrete code + test coverage:

- [ ] **AC1**: Per-step duration spans first attempt to last completion — covered by S01 aggregation + S03 reproduction test
- [ ] **AC2**: Total Time metric card aggregated correctly — covered by `_get_metrics` surfacing aggregated `StepDetail` fields + S03 total-duration test
- [ ] **AC3**: In-progress steps render unchanged (`duration_secs=None` → template renders `—`, no template changes) + `StepDetail.started_at` surfaces aggregated earliest-start — S03 in-progress test
- [ ] **AC4**: Happy-path (single run) unchanged — S03 happy-path regression test
- [ ] **AC5**: Bug fixed + regression test exists — S03 RED verification

Any AC without concrete code + test coverage is a CRITICAL finding (missing requirement).

### 2. Scope discipline (CRITICAL)

Verify the combined diff does NOT touch:

- `orch/daemon/fix_cycle.py` — must be untouched
- `orch/cli/step_commands.py` — must be untouched
- `orch/db/models.py` — no new columns, no new indexes
- `orch/db/migrations/versions/` — NO new migration
- `dashboard/templates/fragments/item_overview.html` / `item_header.html` — ideally untouched; if touched, the S01 report must justify it (Requirement 3 in the S01 prompt allows template tweaks only if needed to preserve live-tick)
- Any CLI command, daemon module, or orchestrator component

If any of the above were modified, that's a CRITICAL scope-creep finding.

### 3. Integration between S01 and S03 (HIGH)

- Does the S03 reproduction test actually call `_get_steps` (or the public entry point that wraps it)? Not a private helper in isolation.
- Do the S03 expected values (`630`, `2026-04-22 12:00:00Z`, etc.) match the S01 aggregation contract? Re-do the arithmetic:
  - `MIN(started_at)` across {run1=12:00:00, cycle=12:03:00, run2=12:10:00} = `12:00:00`
  - `MAX(completed_at)` across {run1=12:02:00, cycle=12:09:00, run2=12:10:30} = `12:10:30`
  - Duration = `12:10:30 − 12:00:00 = 630s`. ✓
- Does `StepDetail.started_at` (aggregated) get consumed correctly by `_get_metrics`? If S01 only changed `duration_secs` but left `started_at`/`completed_at` as `step.started_at`/`step.completed_at`, then AC2 is broken. CRITICAL.

### 4. No regressions elsewhere (CRITICAL)

- Run `make test-unit` — zero failures across the entire suite
- Run `make test-integration` — zero failures across the entire suite
- If any pre-existing test was modified by S01 or S03, is the justification sound?
- Check batches router, running router (`dashboard/routers/batches.py`, `running.py`): they also expose a `duration_secs`. If I-00034's fix changed shared helpers, verify the batches view still works (it computes duration from `BatchItem` and step workflow_steps aggregates — check the S01 diff didn't inadvertently break it).

### 5. N+1 discipline preserved (HIGH)

- `_get_steps` issues a bounded number of queries regardless of step count
- S03's query-count assertion is present and pins to a specific number
- No inner loops hit the DB (the existing `runs = list(db.scalars(...))` per-step loop in `_get_steps` was already there pre-fix and is NOT a regression — but verify S01 didn't accidentally duplicate it or add a new per-step query)

### 6. Testcontainer compliance (CRITICAL)

- No test connects to the live DB (port 5433)
- No `unittest.mock` substituting the DB
- `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` handled correctly by the fixture chain

### 7. Comment anchor (MEDIUM)

- Is there a one-line comment in `dashboard/routers/items.py` referencing I-00034 at the aggregation call-site, so a future reader understands why `WorkflowStep.started_at` / `completed_at` are deliberately ignored for this computation?

### 8. CLAUDE.md and subpackage compliance (HIGH)

- `dashboard/CLAUDE.md`: routers stay thin — S01's aggregation is thin enough; verify.
- `orch/CLAUDE.md`: `DaemonEvent.metadata` gotcha doesn't apply here, but double-check nothing in the diff hit it.
- Docker off-limits policy: no docker commands introduced anywhere in the diff (scripts, tests, dev tooling).
- The updated CLAUDE.md rule "NEVER run `docker compose up` (with or without `-d db`) against the orchestration DB" — verify no doc or script added in the diff violates this.

### 9. Cross-view consistency (MEDIUM_SUGGESTION)

The same step-duration truncation bug likely exists in other views that read `WorkflowStep.started_at` / `completed_at` (e.g. `running.py`, `batches.py`, `project_pages.py` history views). If you spot a place that shares the bug class, note it as a MEDIUM_SUGGESTION with a follow-up I-NNNNN recommendation — but do NOT fail the review over it. This incident's scope is the Item view.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite**: `make test-unit` AND `make test-integration`
2. Run `make lint`
3. Run `uv run mypy orch/ dashboard/`
4. Report results accurately in the contract
5. If integration tests fail, this is a CRITICAL finding

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing AC coverage, scope creep into daemon/cli/models, integration failure between S01 and S03, test regressions elsewhere, testcontainer bypass | Must fix |
| **HIGH** | N+1 leak, CLAUDE.md violation, adjacent view broken (batches/running/history) | Must fix |
| **MEDIUM (fixable)** | Missing comment anchor, convention drift | Should fix |
| **MEDIUM (suggestion)** | Cross-view follow-up recommendation | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00034",
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

- `verdict`: `pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `missing_requirements`: List any AC from the design doc with no corresponding implementation — each missing AC is automatically a CRITICAL finding.
- `cross_cutting`: `true` on findings that span S01 and S03 (e.g. mismatch between aggregation contract and test expectation).
