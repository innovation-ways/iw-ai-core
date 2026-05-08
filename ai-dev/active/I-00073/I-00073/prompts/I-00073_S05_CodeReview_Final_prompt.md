# I-00073_S05_CodeReview_Final_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

Standard policy. Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **No migration may be added by this incident** — if you find any new file under `orch/db/migrations/versions/`, that is an automatic CRITICAL finding.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00073 --json`.
- `ai-dev/active/I-00073/I-00073_Issue_Design.md`
- All implementation step reports: `ai-dev/active/I-00073/reports/I-00073_S01_Backend_report.md`, `I-00073_S03_Tests_report.md`
- All per-agent code review reports: `ai-dev/active/I-00073/reports/I-00073_S02_CodeReview_report.md`, `I-00073_S04_CodeReview_report.md`
- All files listed in S01 + S03 `files_changed`

## Output Files

- `ai-dev/active/I-00073/reports/I-00073_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of all implementation work for I-00073.

This review verifies the chain holds end-to-end:
- S01 patched every agent-facing CLI read of `StepRun`/`WorkItem`/`WorkflowStep` to use column-projected SELECTs.
- S03 wrote the regression suite that simulates worktree-vs-live drift and verifies every patched command tolerates it.
- The two halves must fit together: every callsite S01 patched is covered by an S03 test; every test in S03 exercises a callsite S01 patched.

Read the design's Acceptance Criteria — your verdict must affirm AC1 (bug fixed end-to-end), AC2 (regression test exists and pins the bug), AC3 (no daemon files modified), AC4 (constraints doc updated).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL finding (`category: conventions`).

## Review Checklist

### 1. Completeness vs Design Document

- Walk every row of the design's Root Cause Analysis table. For each callsite listed (BOTH Shape A — `select(Model)` — AND Shape B — `session.get(Model, key)`), confirm S01 patched it AND S03 has a regression test that drives the corresponding command.
- Specifically check: (a) all six `session.get(WorkItem, ...)` callsites in `item_commands.py` were rewritten (RCA lines 249, 416, 542, 605, 718, 854); (b) all three `select(WorkflowStep)` callsites in `step_commands.py` were rewritten (RCA lines 141, 622, 730); (c) S03 has the TWO `item-status` drift scenarios (work_items-only AND workflow_steps-only) — a single combined scenario is insufficient to pin both shapes.
- Walk every Acceptance Criterion (AC1..AC4). For each, confirm there is concrete evidence in the implementation that satisfies it.
- AC4 specifically requires a "CLI resilience to in-flight schema drift" subsection in `docs/IW_AI_Core_Agent_Constraints.md`. Open the file and confirm the subsection exists, references this incident, and explains the rule (including the `session.get` pitfall).

A missing requirement is automatically a **CRITICAL** finding (`missing_requirements` array).

### 2. Cross-Agent Consistency

- The pinned column set defined in S01 must include every column the test scenarios in S03 indirectly verify (the `step_done` test asserts `latest_run.status == "completed"` — that means `status` must be in the projected set, otherwise the test would not reflect reality).
- The dropped columns in S03's drift simulation must be ones the in-process ORM (after S01) still declares — confirm by reading `orch/db/models.py`.

### 3. Integration Points

- Confirm no file under `orch/daemon/`, `orch/db/`, `orch/db/migrations/versions/`, `dashboard/`, or `executor/` was modified. The fix is intentionally narrow. Any modification outside `orch/cli/`, `docs/IW_AI_Core_Agent_Constraints.md`, and `tests/integration/cli/` is an automatic **CRITICAL** finding (`category: architecture`).

### 4. Test Coverage (Holistic)

- Run the full integration suite end-to-end (`make test-integration`). Every test passes — and no test other than the new drift suite changed behavior.
- The new drift suite covers every patched callsite (per S01's `files_changed`). Cross-reference.
- Optionally re-run the RED-check (revert S01 patches, run drift suite, confirm reproduction test fails with `UndefinedColumn`). Skip only if S04 already verified this and you trust S04's report.

### 5. Architecture Compliance

- Read `CLAUDE.md` and `orch/CLAUDE.md`. The fix uses SQLAlchemy 2.0 idioms (`load_only`), psycopg v3, Click 8.1+. No deviations.
- Append-only invariant on `step_runs` is preserved (the patches change SELECT shape, not UPDATE/INSERT semantics).

### 6. Security (Cross-Cutting)

- No hardcoded secrets, credentials, or DB URLs anywhere in the changed files.
- Tests use testcontainer URLs derived from the fixture, not literal connection strings.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — all pass.
2. Run `make test-integration` — all pass, including new drift scenarios.
3. If integration tests fail → **CRITICAL** finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Missing requirement (AC violated), file modified outside the allowed set, integration tests fail, migration file added | Must fix before merge |
| **HIGH** | Cross-step inconsistency (test asserts a column that's not in S01's projected set, or vice versa) | Must fix before merge |
| **MEDIUM (fixable)** | Convention drift, missing edge case | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Better pattern available | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00073",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "...",
      "suggestion": "...",
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
