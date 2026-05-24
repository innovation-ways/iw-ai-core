# CR-00086_S08_CodeReview_Final_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Review Step**: S08 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05, S07 (impl) — plus S02 (qv-gate migration-check), S04, S06 (CodeReviews)

---

## ⛔ Docker is off-limits

Same policy as the other review prompts. Read-only `docker ps/inspect/logs` plus `make` / `./ai-core.sh` targets only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp`. The migration was validated at S02 in a testcontainer.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design (read in full, every section)
- All implementation reports: `ai-dev/work/CR-00086/reports/CR-00086_S0{1,3,5,7}_*_report.md`
- All per-agent CodeReview reports: `ai-dev/work/CR-00086/reports/CR-00086_S0{4,6}_CodeReview_report.md`
- S02 migration-check QV result (in the DB; `iw item-status CR-00086 --json`)
- All files listed in all implementation reports' `files_changed`

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S08_CodeReview_Final_report.md`

## Context

You are performing the **final cross-step review** of ALL implementation work for **CR-00086: Self-dashboarding of test health**. Look at the complete picture — not individual steps in isolation. Per-step reviews have already validated the local work; your job is to catch cross-cutting issues they could not.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC1 through AC6 are all in scope here. Every AC is a mandatory check.
- `## TDD Approach` — list every test file the design names. Cross-check against ALL implementation step reports' `files_changed`. Missing entries are CRITICAL.
- `## Dependencies` — the CR-00080 HARD dependency. Before passing, verify in your report that the operator has confirmed CR-00080 was merged before approval. (This is observational; the daemon will not have blocked execution since the design is just a doc.)
- `## Notes` — flags risks (mutation-source format drift, coverage-XML location). Cross-check the implementation accounted for them.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

New violations on any changed file are CRITICAL `category: conventions`.

## Review Checklist

### 1. Completeness vs Design Document (AC1–AC6)

- **AC1**: `make migration-check` (S02) is green; the new table has the expected columns and the `(project_id, metric, ts DESC)` index.
- **AC2**: capture writes exactly one snapshot per metric AND a job row appears in the unified Jobs view. Re-run `uv run pytest tests/integration/test_test_health_service.py::test_capture_writes_four_snapshots tests/integration/test_jobs_aggregator_test_health.py -v` and report the result.
- **AC3**: idempotency-within-minute test exists and passes.
- **AC4**: panel test asserts four metric labels + four `<svg>` tags.
- **AC5**: empty-state per-metric placeholder test exists AND combined empty-state test exists. Both pass.
- **AC6**: `.github/workflows/test-health.yml` exists, has `push` to main + `schedule` cron + `workflow_dispatch`, invokes `iw test-health-capture --project iw-ai-core`.

### 2. Cross-Agent Consistency

- The `TestHealthSnapshot` column names in S01 match the columns the S03 service writes and the S05 panel reads. A drift (e.g., `meta` vs `metadata`) is CRITICAL.
- The Jobs aggregator's union row shape includes the columns the unified Jobs view expects (study an adjacent job type — code-index — for the column list).
- The mutation-JSON adapter handles both CR-00080's shape AND CR-00059's legacy shape. If only one is handled, raise HIGH (design Notes called this out).

### 3. Integration Points

- The htmx mount in the page templates references the new endpoint URL exactly as the router defines it.
- The CI workflow's `iw test-health-capture --project iw-ai-core` matches the CLI command's actual signature from S03.
- The skill cross-reference paragraph (S07) names the table `test_health_snapshots` — confirm the name matches the migration.

### 4. Test Coverage (Holistic)

- Are there enough integration tests to cover the cross-module behaviour (service writes → aggregator returns → panel renders)? At minimum: capture → DB row → aggregator union → panel HTTP 200 with snapshot value visible. If this end-to-end chain is not exercised, raise HIGH.
- Edge case: ALL metrics empty (AC5 combined empty state) is tested.
- Edge case: one source missing (S03 test_missing_source_skips_that_metric) is tested.

### 5. Architecture Compliance

- `CLAUDE.md` rules respected: no docker compose against orch DB; no migration applied to live DB from agent context; Jinja2 `%`-style format filters; `event_metadata` trap not tripped (N/A here, column is `meta`).
- The Jobs aggregator addition follows the existing union/select pattern (no Python-side concatenation).
- Service module respects layer boundaries (no dashboard imports in `orch/`).

### 6. Security (Cross-Cutting)

- No hardcoded secrets in `.github/workflows/test-health.yml`. All credentials via `${{ secrets.IW_CORE_* }}`.
- `meta` JSONB column does not stuff unbounded raw mutation payloads (small fields only: commit SHA, file path, top counts).
- Jinja autoescape on metric values in the panel template (no `|safe` on user-derived data — though metric values are server-derived, the rule still applies).

### 7. Docs + Tracker + Skill consistency (S07)

- `docs/IW_AI_Core_Testing_Strategy.md` §10 column names match the migration + model.
- `docs/IW_AI_Core_Database_Schema.md` DDL block matches the migration exactly (column types, default, index).
- `ai-dev/work/TESTS_ENHANCEMENT.md` row 4.6 is DONE, references CR-00086, dated 2026-05-24; header is v1.4.
- `skills/iw-ai-core-testing/SKILL.md` and `.claude/skills/iw-ai-core-testing/SKILL.md` are byte-identical (`diff -u` is empty).

## Distrust "no production code change needed"

The Jobs aggregator addition is a place where the design said "follow the existing union pattern". Re-trace: does the new union row's column order match the existing rows? A column-order drift in `union_all` silently shifts the columns in the rendered Jobs table (the kind of latent crash I-00075-class issues hide). If you find a mismatch, raise CRITICAL even though the design said "follow the pattern".

## Test Verification (NON-NEGOTIABLE)

Run the full unit AND integration suites:

```bash
make test-unit
make test-integration
```

Any failure here is a CRITICAL finding. If integration tests fail, the merge MUST NOT proceed.

## Severity Levels

Standard table. `verdict: pass` only if zero CRITICAL + HIGH + MEDIUM-fixable.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview_Final",
  "work_item": "CR-00086",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
