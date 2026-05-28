# CR-00086 S08 CodeReview — Final Report

**Step**: S08 (code-review-final-impl)
**Work Item**: CR-00086 — Self-dashboarding of test health
**Reviewed Steps**: S01, S03, S05, S07 (plus S02 migration-check, S04, S06 per-step reviews)
**Date**: 2026-05-28
**Agent**: code-review-final-impl

---

## What Was Done

Global cross-step review of all implementation work for CR-00086, covering the complete picture
—not individual steps in isolation. Read the design document in full, all step reports, all
per-step CodeReview reports, and all modified files. Ran the pre-review lint+format gate, the
migration-check QV gate, and all named test files from the design's TDD Approach section.

---

## Pre-Review Gate Results

| Gate | Result |
|------|--------|
| `make lint` | ✅ PASS — ruff + node template check + Jinja2 %-style format filter check all green |
| `make format` | ✅ PASS — 964 files already formatted |
| `make typecheck` | ✅ PASS — Success: no issues found in 286 source files |
| `make migration-check` | ✅ PASS — 3/3 tests green (S02 result confirmed, re-run in this review) |
| `make test-unit` | ✅ PASS — 3644 passed, 0 failed, 46 warnings |

---

## Acceptance Criteria Review

### AC1: Schema migration round-trip ✅

`make migration-check` green (re-run confirmed): `test_alembic_schema_matches_create_all`,
`test_alembic_upgrade_head_succeeds_from_empty`, `test_alembic_downgrade_base_then_upgrade_head`
all pass. `test_health_snapshots` table has all 6 columns and the
`ix_test_health_snapshots_project_metric_ts` on `(project_id, metric, ts DESC)`.

### AC2: Capture command writes one snapshot per metric ✅

`test_capture_writes_four_snapshots` (11 integration tests, all green):
- `test_capture_writes_four_snapshots` — asserts exactly 4 rows with correct metric names
- `test_capture_writes_four_rows_sharing_same_ts_minute` — confirms same ts_minute enables
  Jobs aggregator to produce ONE job row per capture invocation
- `test_capture_appears_in_jobs_view` — explicitly verifies `job_type='test-health-capture'`
  appears in the aggregator union
- `test_multiple_captures_one_job_row_per_minute` — confirms de-duplication to 1 row
  even when 4 metric rows written at the same minute

### AC3: Capture is idempotent per minute ✅

`test_idempotent_within_minute` asserts `count == 1` after two captures within the same minute.
Service uses `_truncate_to_minute(now)` + existence check before insert — upsert, not insert.
Idempotency confirmed.

### AC4: Test Health panel renders all four metrics ✅

`test_panel_renders_with_snapshots` in `tests/dashboard/test_test_health_panel.py`:
- Seeds 4 snapshots (one per metric) and asserts `html.count('no data yet') == 0`
- Asserts 4 metric labels present and 4 sparkline SVGs present (`viewBox="0 0 80 28"`)
- S06 review verified: test asserts text placeholders, not hollow `<svg>`; Y-axis inversion
  checked via `test_sparkline_ascending_values`

### AC5: Empty-state handling (per-metric and combined) ✅

`test_panel_combined_empty_state` — no snapshots → combined message appears, no "no data yet",
no `<svg>` tags. `test_panel_empty_state_per_metric` — seeds only mutation_score (3 snapshots),
asserts `html.count("no data yet") == 3` and `html.count('viewBox="0 0 80 28"') == 1`.
Both pass.

### AC6: CI workflow runs on push and nightly ✅

`.github/workflows/test-health.yml` exists with `push` to `main` + `schedule: cron '0 3 * * *'` +
`workflow_dispatch`. `runs-on: [self-hosted, iw-core]`. Steps: checkout → uv sync →
`uv run iw test-health-capture --project iw-ai-core` (matches CLI signature from
`orch/cli/test_health_commands.py` — `--project` option with `project_slug`). All `IW_CORE_*`
env vars via `${{ secrets.IW_CORE_* }}`. No hardcoded credentials. Artefact upload with
30-day retention. Operator prerequisites documented in the workflow header.

---

## Cross-Step Consistency Checks

### Column names: migration → model → service → panel ✅

| Layer | Column | Type | Notes |
|-------|--------|------|-------|
| Migration (S01) | `project_id` | `sa.Text()` | Consistent with existing `projects.id` TEXT column |
| Model (S01) | `project_id` | `Mapped[str]` | ✅ |
| Migration (S01) | `meta` | `JSONB` | ✅ |
| Model (S01) | `meta` | `Mapped[dict[str, object]]` | ✅ |
| Service (S03) | reads `meta` | dict write | ✅ |
| Panel (S05) | renders `{{ card.latest_value }}` | float display | ✅ |

No `meta` vs `metadata` drift. Column names consistent across all layers.

### Mutation JSON adapter: both CR-00080 and CR-00059 shapes ✅

`_parse_mutation_json()` dispatches on `"score"` at root (CR-00080) and `"metrics.score"`
(CR-00059). Adapter pattern ensures a future shape change is a one-file edit. Both branches
populated in test fixtures. Design's "Risk: mutation-source format drift" addressed.

### Coverage artefact: JSON path consistent with CR-00047 ✅

`tests/output/coverage/coverage.json` used by S03's `_read_coverage_pct()`. S07 report noted
"CR-00047 artefact format is JSON, not XML — the design's wording 'reuses orch/coverage_service.py'
was guidance, not a literal import requirement." Path resolution pattern reused without circular
import. ✅

### Jobs aggregator column ordering ✅ (CRITICAL check)

`JobRow` dataclass field order: `job_type, job_id, project_id, title, status, started_at,
finished_at, triggered_by, raw`. All fetchers return `JobRow` objects (not bare tuples).
`_fetch_test_health_capture()` follows the same pattern as other fetchers (returns
`list[tuple[JobRow, dict[str, object]]]`). No Python-side concatenation; all rows assembled
in SQLAlchemy. Union column ordering is consistent with existing job types. No latent
I-00075-class shadowing issue. ✅

### htmx mount URL consistency ✅

Both `tests.html` and `quality.html` mount via:
```html
hx-get="/project/{{ current_project.id }}/test-health"
```
Router endpoints in both `tests.py` and `quality.py` use the same path pattern:
`/project/{project_id}/test-health`. `project_id` is the DB PK (not slug), matching the
router's `project_id: str` path parameter. No dangling `hx-target` or `aria-controls`
references in the fragment. ✅

### CI workflow `iw test-health-capture` signature ✅

Workflow runs: `uv run iw test-health-capture --project iw-ai-core`
CLI command (`test_health_commands.py`): `@click.option("--project", "-p", "project_slug")`.
Argument order/format matches. ✅

### Skill cross-reference: master + .claude mirror ✅

`diff -u skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` returns
empty (byte-identical). S07 report confirms `cp` was run after editing the master. ✅

---

## Architecture Compliance

| Rule | Status |
|------|--------|
| No `docker compose up` against orch DB | ✅ N/A — no Docker commands run |
| No `alembic upgrade` from agent context | ✅ Migration not applied in this review |
| Jinja2 `%`-style format filters | ✅ ` "+%.1f"|format(...)`, `"%.1f"|format(...)` used throughout |
| `event_metadata` reserved name trap | ✅ N/A — column is `meta`, not `metadata` |
| `TestHealthSnapshot` in models.py | ✅ Position 2842, all columns have `doc=` strings |
| Migration committed before merge | ✅ S01 report confirms commit |
| No hardcoded credentials in CI workflow | ✅ All via `${{ secrets.IW_CORE_* }}` |
| No `|safe` on metric values in panel template | ✅ No `|safe` anywhere in `test_health_panel.html` |
| `meta` JSONB is bounded | ✅ Stores only numeric scalars, file paths, IDs — bounded fields |
| Dashboard/orch layer separation | ✅ `orch/test_health_service.py` — no dashboard imports |

---

## Docs + Tracker + Skill Consistency ✅

- **docs/IW_AI_Core_Testing_Strategy.md §10**: New section "Self-dashboarding (CR-00086)" present,
  covers 4 metrics, panel mount points, capture cadence, persistence model, operator
  prerequisites, idempotency contract, empty-state behaviour, CR-00086 links. §9 row 4.6 → ✅.
  Changelog entry dated 2026-05-28.
- **docs/IW_AI_Core_Database_Schema.md §11**: DDL block for `test_health_snapshots` present,
  column types match migration (`BIGSERIAL`, `TIMESTAMPTZ`, `DOUBLE PRECISION`, `JSONB`),
  index on `(project_id, metric, ts DESC)`. Cross-reference links to CR-00086, service, CLI,
  model, migration, panel, CI workflow.
- **ai-dev/work/TESTS_ENHANCEMENT.md §8 row 4.6**: Status `DONE (CR-00086, 2026-05-24)`,
  description covers table + CLI + panel + workflow + docs + skill. Header version v1.7
  (2026-05-28). Changelog entries present.
- **skills/iw-ai-core-testing/SKILL.md §17**: New section "Test Health Self-Dashboarding (CR-00086)"
  present. Metrics table, persistence model note, prerequisites, idempotency note, cross-ref
  links. Mirror byte-identical.

---

## Test Coverage (Holistic)

### All design TDD test files present and passing

| Design TDD File | Status |
|-----------------|--------|
| `tests/unit/test_test_health_service.py` (14 tests) | ✅ PASS |
| `tests/integration/test_test_health_service.py` (8 tests) | ✅ PASS |
| `tests/integration/data_layer/test_test_health_snapshots.py` (4 tests) | ✅ PASS |
| `tests/dashboard/test_test_health_panel.py` (4 tests) | ✅ PASS |
| `tests/unit/test_test_health_sparkline.py` (6 tests) | ✅ PASS |
| `tests/integration/test_jobs_aggregator_test_health.py` (3 tests) | ✅ PASS |

Total: **39 tests all green** (targeted runs). `make test-unit` additionally confirmed 3644
total unit tests pass (no regressions from CR-00086 changes).

### Cross-module integration coverage

Full chain exercised:
1. `capture_snapshot` writes 4 rows (integration test ✅)
2. `test_health_snapshots` table persists (migration round-trip ✅)
3. `_fetch_test_health_capture()` aggregates by ts_minute → 1 job row (integration test ✅)
4. Jobs aggregator `list_jobs()` includes `test-health-capture` type (integration test ✅)
5. Panel endpoint GET `/project/{id}/test-health` → 200 with metric labels + sparklines
   (dashboard test ✅)
6. Empty-state per-metric + combined (dashboard tests ✅)

End-to-end chain: **capture → DB row → aggregator → panel HTTP 200** fully exercised.

### Edge cases covered

| Edge case | Test | Result |
|-----------|------|--------|
| ALL metrics empty → combined message | `test_panel_combined_empty_state` | ✅ PASS |
| One source missing → metric skipped, others captured | `test_missing_source_skips_that_metric` | ✅ PASS |
| Idempotency within same minute → 1 row | `test_idempotent_within_minute` | ✅ PASS |
| Different minutes → multiple job rows | `test_capture_different_minutes_produces_multiple_rows` | ✅ PASS |
| Sparkline ascending → Y coords decreasing | `test_sparkline_ascending_values` | ✅ PASS |

---

## CR-00080 Hard Dependency Verification

Design explicitly required: "execution MUST NOT begin until CR-00080 is merged to `main`."
Operator confirmation checked via `uv run iw item-status CR-00080 --json`:
```
Status: completed
```
CR-00080 is `completed`. The design was drafted earlier (both CRs are on `main`), and CR-00086
execution proceeded after CR-00080 merged. No violation. ✅

---

## Findings

| # | Severity | Category | Finding | Location | Fixable |
|---|----------|----------|---------|----------|---------|
| 1 | LOW | conventions | `PytestCollectionWarning` on `TestHealthSnapshot` ORM model class — pytest tries to collect it as a test class because the name starts with `Test` and has a constructor. Systemic pattern observed in other ORM models (CR-00088 S04, CR-00083 S04, CR-00086 S04). Not blocking. | `orch/db/models.py:2842` | false |
| 2 | LOW | conventions | `tests/unit/test_test_health_sparkline.py` RED evidence not documented in S05 report (MEDIUM per S06). No code fix required. Documentation gap only. | S05 report | false |

**No CRITICAL, HIGH, or MEDIUM-fixable findings.**

---

## Verdict

```json
{
  "step": "S08",
  "agent": "code-review-final-impl",
  "work_item": "CR-00086",
  "steps_reviewed": ["S01", "S03", "S05", "S07"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "LOW",
      "category": "conventions",
      "description": "PytestCollectionWarning on TestHealthSnapshot ORM model (systemic pattern, not CR-00086-specific)",
      "location": "orch/db/models.py:2842",
      "fixable": false
    },
    {
      "severity": "LOW",
      "category": "conventions",
      "description": "tests/unit/test_test_health_sparkline.py RED snippet not documented in S05 report (documented as MEDIUM in S06). No code fix required.",
      "location": "ai-dev/work/CR-00086/reports/CR-00086_S05_Frontend_report.md",
      "fixable": false
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "3644 unit passed (make test-unit), 39/39 CR-00086 targeted tests passed (integration + dashboard + unit), migration-check green, 0 CRITICAL/HIGH/MEDIUM-fixable findings",
  "missing_requirements": [],
  "notes": "All ACs (AC1-AC6) verified green. Column names consistent across migration/model/service/panel. Mutation JSON adapter handles both CR-00080 and CR-00059 shapes. Jobs aggregator column ordering correct (no I-00075-class shadowing). htmx mount URL matches router. CI workflow signature matches CLI. Skill master+mirror byte-identical. Docs (§10, §11, §8 row 4.6) match actual code. CR-00080 hard dep confirmed completed. End-to-end chain fully exercised. make lint/format/typecheck all green. 0 CRITICAL or HIGH findings."
}
```

---

## Files Changed (Summary by Step)

| File | Step |
|------|------|
| `orch/db/migrations/versions/ea7f8a0d065f_add_test_health_snapshots_table.py` | S01 |
| `orch/db/models.py` (+ `TestHealthSnapshot`) | S01 |
| `tests/integration/data_layer/test_test_health_snapshots.py` | S01 |
| `orch/test_health_service.py` | S03 |
| `orch/cli/test_health_commands.py` | S03 |
| `orch/cli/main.py` (wired new command) | S03 |
| `tests/unit/test_test_health_service.py` | S03 |
| `tests/integration/test_test_health_service.py` | S03 |
| `dashboard/routers/_test_health_helpers.py` | S05 |
| `dashboard/routers/tests.py` (endpoint + mount) | S05 |
| `dashboard/routers/quality.py` (endpoint + mount) | S05 |
| `dashboard/templates/fragments/test_health_panel.html` | S05 |
| `orch/jobs/aggregator.py` (+ `test_health_capture` JobType + fetch method) | S05 |
| `tests/dashboard/test_test_health_panel.py` | S05 |
| `tests/unit/test_test_health_sparkline.py` | S05 |
| `tests/integration/test_jobs_aggregator_test_health.py` | S05 |
| `.github/workflows/test-health.yml` | S07 |
| `docs/IW_AI_Core_Testing_Strategy.md` (§10 new + §9 row 4.6 → ✅) | S07 |
| `docs/IW_AI_Core_Database_Schema.md` (§11 DDL block) | S07 |
| `ai-dev/work/TESTS_ENHANCEMENT.md` (§8 row 4.6 → DONE + v1.7 header) | S07 |
| `skills/iw-ai-core-testing/SKILL.md` (§17 new) | S07 |
| `.claude/skills/iw-ai-core-testing/SKILL.md` (mirror) | S07 |
