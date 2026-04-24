# CR-00019_S13_CodeReview_Final_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Review Step**: S13 (Final Review)
**Implementation Steps Reviewed**: S01..S12

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- All implementation reports: `ai-dev/work/CR-00019/reports/CR-00019_S0*_*_report.md`
- All per-agent code review reports: `ai-dev/work/CR-00019/reports/CR-00019_S0*_CodeReview_report.md`
- All files listed in every implementation report's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S13_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL implementation work for CR-00019. Per-agent reviews passed — your job is to catch cross-cutting issues they couldn't.

Read the design doc. Read all the per-step reports. Then look at the combined diff holistically.

## Review Checklist

### 1. Completeness vs. design doc

- Every AC (AC1–AC15) has implementation + at least one test.
- No TODO / placeholder / "XXX" comments in the diff.
- Rationale populated for every existing check — no empty-string or placeholder rationales slipped through.
- Every new migration column is referenced somewhere in code (not added-but-unused).

### 2. Cross-agent consistency

- The JSON body shape on `POST /oss/prepare` in S05 matches what the frontend in S09 sends (same keys, same casing).
- The column names on `ProjectOssJob` in S01 match the attribute names used by S05 worker and S07 routes.
- The rationale flow: skill (S03) → scanner → persistence (S03) → DB column (S01) → route context → template (S09). Walk it end-to-end; find any break.
- Branch naming: S05 sets `iw-oss-publish/prep-<job_id>` (via env or hardcoded); S07 reads `job.branch_name` from the DB. Confirm the branch the worker creates matches what's persisted.

### 3. Integration points

- End-to-end manual trace: user clicks "Prepare fix (2 selected)" → confirm dialog → POST with JSON → route → enqueue_job → run_job → _run_worktree → skill → scanner + auto-commit → status=awaiting_review → template renders awaiting-review card → user clicks Accept → route → squash-merge → status=complete. Every hop should line up.
- Same trace for Discard.
- Trace the moved-main path: base_sha stored by S05, read by S07, compared to current main. Column type matches usage.

### 4. Test coverage (holistic)

- Happy path + sad path covered for both accept and discard.
- Edge cases: empty diff from subprocess, worktree already gone, branch already gone, main moved, concurrent prepares.
- The publish / install paths still have passing regression tests (they must not have changed behavior).

### 5. CLAUDE.md compliance

Read `CLAUDE.md`, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`, and `tests/CLAUDE.md`. Verify:
- No `docker compose up` / `docker compose down` called from any new code.
- No alembic upgrade/downgrade/stamp in route or test code.
- No psycopg2 URLs in tests.
- `DaemonEvent.metadata` alias respected if touched.
- `postgresql+psycopg://` in all new test fixtures.
- Thin routers; business logic in services.
- No dynamic Tailwind classes.

### 6. Security (cross-cutting)

- Accept is the most destructive route in the CR. Confirm:
  - The handler cannot be coerced into running `git` outside `project.repo_root` or `worktree_path` (no user-controlled cwd).
  - The prep branch name is constructed by the worker (deterministic), not supplied by the client — so the user can't POST a `branch_name` that points at something else.
  - The commit message interpolates `job.id` only, no user-controlled data.
- No secrets printed to `stdout_tail` (grep the skill output mock tests for accidentally-leaked patterns — should be clean, but confirm).

### 7. Skill mirror sync

- `diff -rq skills/iw-oss-publish/ .claude/skills/iw-oss-publish/` — must be empty (ignoring `__pycache__`).
- Any discrepancy is CRITICAL — the skill is loaded from both directories in different contexts.

### 8. Documentation sync

- `docs/IW_AI_Core_Database_Schema.md` reflects the new columns + enum values.
- `skills/iw-oss-publish/README.md` documents `--check` and the dropped always-try list.
- Design doc's File Manifest matches what's actually in the repo.

### 9. Migration safety

- `ALTER TYPE ADD VALUE` pattern is correct for this PG version (>=12).
- Down-migration explicitly calls out the enum-drop limitation.
- No server_defaults that would trigger a table rewrite on a large production table (all new columns are nullable, no defaults — safe).

### 10. UI correctness (cross-checked with evidences)

- Compare `evidences/pre/` screenshots with what the code renders. The card layout must be gone; the table must be present; no "→ Fix via Prepare" anywhere.
- Ready for the QV Browser step (S19) to validate end-to-end.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run the **full test suite**: `make test-unit && make test-integration`.
2. Run: `make lint && make quality` (quality = lint + format-check + mypy).
3. Integration-test failure is a CRITICAL finding.
4. Report test results precisely.

## Severity Levels

Same as per-step reviews. Missing-AC coverage is treated as a missing requirement → automatically CRITICAL.

## Review Result Contract

```json
{
  "step": "S13",
  "agent": "CodeReview_Final",
  "work_item": "CR-00019",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11", "S12"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `missing_requirements`: each missing AC is automatically CRITICAL.
- `cross_cutting: true` on findings that span multiple agents' work.
