# I-00042_S05_CodeReview_Final_prompt

**Work Item**: I-00042 — PostgreSQL `batch_item_status` enum missing `migration_invalid` and `migration_rolled_back` labels
**Step**: S05
**Agent**: CodeReview_Final

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB.
Read-only `alembic history | current | show` and `uv run iw migrations dry-run` are fine.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00042/I-00042_Issue_Design.md` — Design document
- All implementation step reports: `ai-dev/active/I-00042/reports/I-00042_S0{1,3}_*_report.md`
- All per-agent code review reports: `ai-dev/active/I-00042/reports/I-00042_S0{2,4}_CodeReview_*_report.md`
- All files listed in S01 and S03 reports' `files_changed`

## Output Files

- `ai-dev/active/I-00042/reports/I-00042_S05_CodeReview_Final_report.md` — Final review report

## Context

You are performing the **final cross-agent review** for I-00042. The per-step
reviews have already happened; your job is to verify the migration (S01) and the
test (S03) compose correctly into a complete fix that satisfies the design
document's acceptance criteria.

The work item is small — only two files were changed (one new migration, one new
test). Despite the small scope, run the full verification suite to confirm nothing
regressed.

## Review Checklist

### 1. Completeness vs Design Document

- AC1: Migration adds `migration_invalid` and `migration_rolled_back` to PG enum.
  Verify by inspecting the migration file's `upgrade()` body. Both labels by name?
- AC2: Regression test exists. Verify the test file is at the path specified in the
  design document and contains the assertions described.
- AC3: Daemon startup is clean. You cannot test this directly without restarting the
  live daemon (operator-only action), but you CAN verify that the migration applies
  successfully via `uv run iw migrations dry-run`. The daemon-startup verification
  is implicit: with the labels present, the worktree re-attach query no longer
  binds an unknown enum value.
- All design document `File Manifest` entries exist on disk?
- No TODO comments or placeholder implementations in either file?

### 2. Cross-Step Consistency

- Does the test reference exactly the labels added by the migration? (If S03 asserts
  `"migration_invalid" in labels` but S01's migration only added
  `"migration_invalid"`, the test passes — but if S03 also references some unrelated
  label name and S01 missed it, that is a cross-step bug per-step review missed.)
- Are the migration's `down_revision` and the project's current alembic head aligned?
  Run `uv run alembic history | head -5` and confirm the new migration is the new
  head and chains off `c062b6bf5eb3`.

### 3. Integration: end-to-end dry-run

This is the integration check that per-step reviews could not perform:

```bash
uv run iw migrations dry-run
```

Must succeed and the output must list the new revision among "Revisions applied".

Then:

```bash
uv run pytest tests/integration/test_batch_item_status_enum_drift.py -v
```

Must pass against the testcontainer (which applies the new migration).

### 4. Architecture compliance

- Migration follows the canonical pattern in `40af3b76e1d5_cr_00021_rebase_pipeline_phase.py`?
- Test uses the existing testcontainer fixture, not a new bespoke one?
- No new abstractions introduced (no new helpers, no new fixture, no shared util)?

### 5. Security and scope

- No hardcoded credentials in either file?
- No expansion of scope: migration touches only the enum, test touches only the
  enum drift?
- Did either step modify files outside their stated scope (`orch/db/models.py`,
  daemon code, dashboard, etc.)? Cross-check against the design document's
  `File Manifest`.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. `uv run iw migrations dry-run` — must succeed.
2. `make test-unit` — must pass with zero failures.
3. `make allure-integration` — must pass; the new test must appear in the report.
4. `make lint` — must pass.
5. `make typecheck` — must pass.

If integration tests fail, this is a CRITICAL finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Migration won't apply, missing label, integration test fails, missing AC, scope violation | Must fix |
| **HIGH** | Down-revision mis-chained, cross-step inconsistency | Must fix |
| **MEDIUM (fixable)** | Convention deviation, missing assertion message | Should fix |
| **MEDIUM (suggestion)** | Better wording, optional defensive check | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00042",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed; lint clean; typecheck clean",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL, zero HIGH, AND zero MEDIUM (fixable) findings.
`missing_requirements`: list every design-doc AC with no corresponding code; each is automatically CRITICAL.
