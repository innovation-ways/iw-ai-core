# CR-00087 S14 — SelfAssess Report

**Work Item**: CR-00087 — Auto-amend scope violations matching per-project allow-patterns
**Step**: S14
**Agent**: self-assess-impl
**Status**: complete

---

## What Was Done

Invoked the `iw-item-analyze` skill to analyze the execution history of CR-00087 (13 completed steps: S01–S13). Read all run logs, step reports, and DB telemetry. Produced two output files:

- `ai-dev/work/CR-00087/reports/CR-00087_self_assess_report.md` — human-readable narrative analysis
- `ai-dev/work/CR-00087/reports/CR-00087_self_assess_findings.json` — structured findings

## Key Findings (4 promoted)

| # | Title | Severity | Class | Frequency |
|---|-------|----------|-------|-----------|
| 1 | Integration tests caught composite-PK SQLAlchemy bug that unit tests missed | HIGH | platform | systemic |
| 2 | TDD stub tests went stale after S03 wired the real implementation | MED | platform | systemic |
| 3 | QV gates S09–S11 each ran twice (identical results, both passed) | MED | platform | systemic |
| 4 | S04 fixture had no HEAD, causing _captured_paths to return empty | MED | platform | systemic |

### Finding 1 (HIGH): Integration tests caught composite-PK bug
`db.get(WorkItem, step.work_item_id)` was called with a single key against `WorkItem`'s composite PK `(project_id, id)`. The bug was caught by S04's integration tests. A targeted unit test in `tests/unit/test_fix_cycle.py` would prevent regression.

### Finding 2 (MED): TDD stubs went stale
S03 wired the real `_try_auto_amend_after_escalation` but the TDD stub tests still raised `NotImplementedError`. A fix cycle (S05 fix) was required. A linter rule for NotImplementedError stubs in the same function scope would prevent this.

### Finding 3 (MED): QV gate double-runs
S09, S10, S11 all have two log files with identical content, both exit 0. Likely a timing issue in the executor where the step is marked "in progress" before the gate finishes, triggering an immediate re-invocation. Investigation needed in `orch/cli/step_commands.py` and `executor/`.

### Finding 4 (MED): Worktree fixture had no HEAD
`_write_worktree_with_git` staged but never committed pre-cycle files, leaving the worktree without a HEAD. `_captured_paths` uses `git diff HEAD` which requires HEAD to exist. Fixed in S04; a smoke assertion in the fixture would prevent recurrence.

## Files Changed

| File | Change |
|------|--------|
| `ai-dev/work/CR-00087/reports/CR-00087_self_assess_report.md` | **NEW** — narrative self-assessment analysis |
| `ai-dev/work/CR-00087/reports/CR-00087_self_assess_findings.json` | **NEW** — structured findings JSON |

## Test Results

No new tests (analysis step). DB telemetry available (DB:UP confirmed).

## Issues and Observations

- **Item ran cleanly overall**: All 6 acceptance criteria verified by S06 final review, all QV gates green.
- **One fix cycle** (S05): Correctly handled — stale TDD stubs were fixed automatically.
- **Two bugs caught by integration tests** (S04): The composite-PK bug and the git fixture HEAD issue. Both were legitimate bugs that unit tests would not have caught — integration tests paid for themselves.
- **Redundant QV gate runs** (S09–S11): Minor executor issue; does not affect correctness but wastes ~1–3 minutes per item.

## Notes

- Coverage: all 13 completed step logs read in full (< 2 KB each except S13 at 439 KB tail-sampled); all QV gate and step reports from `ai-dev/active/CR-00087/reports/` reviewed.
- DB signal: full (DB:UP confirmed).
- Self-assessment step is soft — findings are advisory only.
