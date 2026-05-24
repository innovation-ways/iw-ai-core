# CR-00086: Self-dashboarding of test health — surface mutation score, coverage trend, flaky-test count, and assertion-baseline size in the dashboard's existing Tests / Quality view

**Type**: Change Request
**Priority**: Medium
**Reason**: Dogfood the IW AI Core dashboard. The platform runs other projects' test/quality gates and surfaces the results in its Tests/Quality view, but it does not surface its own test-health signals. Phases 0–3 of the testing initiative produced four headline metrics — mutation score, coverage trend, flaky-test count, assertion-baseline size — that currently live only in CI artefacts and ad-hoc tracker rows. Promoting them to the dashboard closes the dogfood loop and gives the team a single pane of glass for the platform's own quality story.
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. CI job in `.github/workflows/test-health.yml` runs in GitHub-hosted Linux and may freely use `docker` there; agent steps within the worktree do NOT.

## ⛔ Migrations: agents generate, daemon applies

**This item ADDS a migration**. S01 generates the Alembic revision file under `orch/db/migrations/versions/` and writes the matching `TestHealthSnapshot` model. The daemon applies the migration during the merge pipeline (pre-merge dry-run on testcontainer + post-merge apply to live DB). Agents MUST NOT run `alembic upgrade head` against the live orch DB (port 5433).

A `migration-check` QV gate runs immediately after S01 to catch model↔migration drift before downstream agents inherit a wrong schema.

## Description

Add a Test Health panel to the existing per-project Tests / Quality dashboard view that displays four metrics — mutation score, coverage trend, flaky-test count, and assertion-baseline size — with the latest value plus a 30-point trend sparkline. A new `iw test-health-capture` CLI command and a GitHub Actions workflow ingest snapshots on every successful main-branch push and nightly. Snapshots are stored in a new `test_health_snapshots` table and surfaced as a job type in the unified Jobs view.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Particularly relevant for this CR:

- `orch/db/models.py` — SQLAlchemy ORM conventions; `doc=` strings required (testing skill rule).
- `orch/db/migrations/versions/` — Alembic revisions; daemon owns application (rule above).
- `orch/coverage_service.py` — existing coverage parser; reuse.
- `orch/jobs/aggregator.py` — unified Jobs view; pattern for adding a new job type.
- `dashboard/routers/tests.py` + `dashboard/routers/quality.py` — existing Tests / Quality routes.
- `dashboard/templates/fragments/` — htmx fragment template convention.
- `tests/CLAUDE.md` — testcontainer rules; never connect tests to live DB on port 5433.
- `skills/iw-ai-core-testing/SKILL.md` — assertion strength and TDD-RED-evidence requirements.

## Current Behavior

- The dashboard's Tests view (`dashboard/routers/tests.py`) surfaces unit, integration, and quality-gate results for managed projects, including `iw-ai-core` itself when listed as a project.
- Mutation score is produced by `make mutation-audit` / `make mutation-results` (CR-00059 / CR-00080) and lives only in `tests/output/mutation-*.json` artefacts on the runner. It is not stored or trended.
- Coverage trend artefacts (`make diff-coverage`, CR-00047) live only in CI artefacts.
- Flaky-test counts come from `scripts/flake_detect_aggregate.py` parsing `tests/output/flake-detect-*.log` (CR-00061). They are not persisted between runs.
- Assertion-baseline size is the line count of `tests/assertion_free_baseline.txt` (CR-00046). It is checked at lint time but not trended over time.
- There is no single dashboard surface that shows the four headline test-health metrics together for the platform itself; the team checks each artefact source manually.
- The unified Jobs view (`orch/jobs/aggregator.py` → `dashboard/routers/jobs_ui.py`) aggregates Batches, CodeIndex, DocGeneration, and ResearchDraft jobs. There is no `test-health-capture` job type.

## Desired Behavior

- A new database table `test_health_snapshots` stores one row per `(project_id, metric, ts)` tuple with `value` (numeric) and `meta` (JSONB for run-id, commit-sha, etc.).
- A new service `orch/test_health_service.py` exposes:
  - `capture_snapshot(project_id, metric: str, value: float, meta: dict) -> TestHealthSnapshot`
  - `read_sources(project_id) -> dict[str, tuple[float, dict]]` returning the latest value+meta for each of the four metrics by reading the source artefacts.
  - `latest(project_id) -> dict[str, TestHealthSnapshot]` and `trend(project_id, metric, limit=30) -> list[TestHealthSnapshot]` for the dashboard.
- A new CLI command `iw test-health-capture --project <slug>` reads the four artefact sources for the named project, writes one snapshot per metric, and prints a JSON summary. Idempotent per `(project_id, metric, ts)` (ts truncated to the minute).
- The Tests / Quality dashboard view renders a new "Test Health" panel under the existing gates summary, showing each metric's latest value, the delta vs. the previous snapshot, and an inline SVG sparkline of the last 30 snapshots. htmx-fragment driven; reuses Tailwind utility classes already in the Tests view.
- Each `iw test-health-capture` run appears in the unified Jobs view as job type `test-health-capture`.
- `.github/workflows/test-health.yml` runs the capture on every successful main-branch push (post-merge) and nightly via cron.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/db/models.py` | No `TestHealthSnapshot` model | New model with `doc=` strings, FK to `projects` |
| `orch/db/migrations/versions/` | No `add_test_health_snapshots_table` migration | New Alembic revision with up + down + index |
| `orch/test_health_service.py` | Does not exist | New service module reading 4 artefact sources |
| `orch/cli/` | No `test-health-capture` subcommand | New `test_health_commands.py` (or extended existing module) wired into the Typer app |
| `orch/jobs/aggregator.py` | Aggregates batches / code-index / doc-gen / research jobs | Adds `test-health-capture` job type rows |
| `dashboard/routers/tests.py` | Renders gate summaries only | Adds `/projects/{slug}/test-health` htmx fragment endpoint and mounts the panel |
| `dashboard/routers/quality.py` | Renders quality gates only | Same panel mounted; shared partial render path |
| `dashboard/templates/fragments/test_health_panel.html` | Does not exist | New fragment with 4 metric cards + inline SVG sparkline |
| `dashboard/templates/pages/{tests,quality}.html` (whichever mounts the panel) | No test-health include | Adds an htmx-include for the new fragment |
| `.github/workflows/test-health.yml` | Does not exist | New workflow: on-push to main + nightly cron |
| `docs/IW_AI_Core_Testing_Strategy.md` | No §10 on self-dashboarding | New §10 covers the panel, metrics, capture cadence |
| `docs/IW_AI_Core_Database_Schema.md` | No `test_health_snapshots` table | DDL block added |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §8 row 4.6 = TODO | Row 4.6 → DONE + v1.4 header bump |
| `skills/iw-ai-core-testing/**` + mirror in `.claude/skills/iw-ai-core-testing/**` | No cross-reference to the panel | Adds one paragraph pointing readers at the dashboard panel for live metric values |

### Breaking Changes

- **None**. The new table, service, CLI command, panel, and workflow are purely additive. Existing Tests / Quality routes, Jobs view rows, and Makefile targets are unchanged in semantics — the panel is mounted as a new fragment and the new job type is appended to the aggregator's union.

### Data Migration

- **Schema migration**: forward — creates `test_health_snapshots` table + index. Reversible — `downgrade()` drops the table.
- **No data backfill**. Historical snapshots are not reconstructed from prior CI artefacts; the panel starts empty and fills as the workflow runs. The first capture after merge provides the seed row.
- **Reversible**: yes. `alembic downgrade -1` drops the table; the panel renders an empty state.

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. This CR splits into Database / Backend service+CLI / Frontend panel+Jobs / CI+docs+skill+tracker — four implementation steps, then per-step CodeReviews, a CodeReview_Final, the standard 8 QV gates, a qv-browser, and a final SelfAssess. 16 steps total.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration `add_test_health_snapshots_table` + `TestHealthSnapshot` model with `doc=` strings + round-trip-test fixture row | — |
| S02 | qv-gate (migration-check) | `make migration-check` (placed immediately after S01 per CR-00021 / the new-CR skill rule) | — |
| S03 | backend-impl | `orch/test_health_service.py` (read 4 source artefacts, write snapshot) + new `iw test-health-capture` CLI command | — |
| S04 | code-review-impl | Review S01 + S03 backend work (schema, service, CLI) | — |
| S05 | frontend-impl | `test_health_panel.html` fragment + tests/quality router endpoint + Jobs aggregator wiring | — |
| S06 | code-review-impl | Review S05 frontend + jobs integration | — |
| S07 | backend-impl | `.github/workflows/test-health.yml` + docs (`Testing_Strategy.md` §10, `Database_Schema.md` DDL) + tracker (§8 row 4.6 → DONE, v1.4 header) + skill cross-reference + `iw sync-skills` | — |
| S08 | code-review-final-impl | Global cross-step review covering AC1–AC6 | — |
| S09 | qv-gate | `make lint` | — |
| S10 | qv-gate | `make format-check` | — |
| S11 | qv-gate | `make type-check` | — |
| S12 | qv-gate | `make test-unit` | — |
| S13 | qv-gate | `make allure-integration` | — |
| S14 | qv-gate | `make diff-coverage` | — |
| S15 | qv-gate | `make security-secrets` | — |
| S16 | qv-browser | Browser verification: Test Health panel renders, sparklines paint, no console errors | — |
| S17 | self-assess-impl | SelfAssess via `iw-item-analyze` (project has `self_assess = true`) | — |

> **Note**: the user spec mentions "16 steps + S15 qv-browser + S16 SelfAssess". The skill's mandatory `migration-check` gate after S01 (per the new-CR skill rules) adds one step, and the project's `self_assess = true` flag mandates a final SelfAssess step. Net total: **17 steps**. Per the new-CR skill, migration-check + self_assess are mandatory and may NOT be omitted; the design honours the user's intent (4 impl + CRs + 8 QV + qv-browser + SelfAssess) while complying with both required rules.

Agent slugs: `database-impl`, `backend-impl`, `frontend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`, `self-assess-impl`.

### Database Changes

- **New tables**: `test_health_snapshots`
  - `id BIGSERIAL PRIMARY KEY`
  - `project_id BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE`
  - `ts TIMESTAMPTZ NOT NULL DEFAULT now()`
  - `metric TEXT NOT NULL` (one of: `mutation_score`, `coverage_pct`, `flaky_test_count`, `assertion_baseline_size`)
  - `value DOUBLE PRECISION NOT NULL`
  - `meta JSONB NOT NULL DEFAULT '{}'::jsonb` (carries commit SHA, source path, raw counts)
  - Index: `ix_test_health_snapshots_project_metric_ts ON (project_id, metric, ts DESC)` for fast latest+trend lookups.
- **Modified tables**: none
- **Migration notes**: standard Alembic revision; the round-trip test (`tests/integration/data_layer/test_migration_round_trip.py` pattern) catches schema-vs-model drift.

### API Changes

- **New endpoints**:
  - `GET /projects/{slug}/test-health` — htmx fragment rendering the Test Health panel (mounted from tests.py and quality.py)
  - `GET /api/v1/projects/{slug}/test-health/latest` — JSON `{metric: {value, ts, meta}}` for callers (sparkline JSON consumers)
- **Modified endpoints**: none
- **Removed endpoints**: none

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/test_health_panel.html` — 4 metric cards + inline SVG sparkline (no JS library; SVG built server-side from snapshot rows)
- **Modified components**:
  - The Tests page (and Quality page) template adds one `<div hx-get="…test-health" hx-trigger="load">` mount point under the existing gate summary.
- **Removed components**: none

## File Manifest

All files for this work item live under `ai-dev/active/CR-00086/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00086_CR_Design.md` | Design | This document |
| `CR-00086_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00086_S01_Database_prompt.md` | Prompt | Migration + model |
| `prompts/CR-00086_S03_Backend_prompt.md` | Prompt | Service + CLI |
| `prompts/CR-00086_S04_CodeReview_prompt.md` | Prompt | Review S01 + S03 |
| `prompts/CR-00086_S05_Frontend_prompt.md` | Prompt | Panel + Jobs integration |
| `prompts/CR-00086_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00086_S07_Backend_prompt.md` | Prompt | CI + docs + skill + tracker |
| `prompts/CR-00086_S08_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/CR-00086_S16_BrowserVerification_prompt.md` | Prompt | qv-browser |
| `prompts/CR-00086_S17_SelfAssess_prompt.md` | Prompt | SelfAssess |

Reports are created during execution in `ai-dev/work/CR-00086/reports/`.

## Acceptance Criteria

### AC1: Schema migration round-trip

```
Given the migration add_test_health_snapshots_table is at head
When `make migration-check` runs (upgrade base → head, then downgrade base → upgrade head)
Then the schema matches `Base.metadata.create_all()` exactly, the round-trip succeeds with no drift, and the resulting table has the expected columns and the (project_id, metric, ts DESC) index
```

### AC2: Capture command writes one snapshot per metric

```
Given an iw-ai-core project row exists and the four artefact sources (mutation JSON, coverage XML, flaky log, assertion baseline) are present
When `uv run iw test-health-capture --project iw-ai-core` is invoked
Then exactly one snapshot row is inserted per metric (mutation_score, coverage_pct, flaky_test_count, assertion_baseline_size), the printed JSON summary echoes the four (metric, value, ts) tuples, and a job row appears in the unified Jobs view with type=test-health-capture
```

### AC3: Capture is idempotent per minute

```
Given a snapshot for (project_id, metric, ts_minute) already exists
When `iw test-health-capture --project iw-ai-core` is invoked again within the same minute with the same source values
Then no duplicate row is inserted; the existing row's `meta` is left intact and the command exits 0 with a "no-op" annotation in the JSON summary
```

### AC4: Test Health panel renders all four metrics

```
Given at least one snapshot exists for each of the four metrics on the iw-ai-core project
When a user opens /projects/iw-ai-core/tests in the browser
Then the Test Health panel is visible under the gates summary; each of the four metric cards shows the latest value, a delta vs. the previous snapshot, and an inline SVG sparkline drawn from the last 30 snapshots; no console errors fire on load
```

### AC5: Empty-state handling

```
Given no snapshots exist for a metric (e.g. a freshly-onboarded project)
When the Test Health panel renders
Then that metric's card shows a "no data yet" placeholder rather than crashing or rendering NaN
```

### AC6: CI workflow runs on push and nightly

```
Given .github/workflows/test-health.yml is merged
When a commit lands on main OR the nightly cron fires
Then the workflow invokes `iw test-health-capture --project iw-ai-core`, snapshots are written, and the workflow exits 0
```

## Rollback Plan

- **Database**: reverse migration available — `alembic downgrade -1` drops `test_health_snapshots`. No FK from other tables points at it, so the drop is safe.
- **Code**: revert the merge commit. The new endpoint, fragment, service, CLI command, jobs aggregator branch, and CI workflow disappear in one shot. The Tests and Quality pages return to their pre-CR appearance because the panel is mounted via a single htmx include that the revert removes.
- **Data**: no loss on rollback. Snapshot rows are observability data only; nothing else depends on them. The CI workflow stops running because its file no longer exists.

## Dependencies

- **Depends on**:
  - **HARD: CR-00080 (mutation-score widened scope)** — this CR's mutation-score metric is only meaningful once CR-00080 has widened mutation-test scope beyond CR-00059's `orch/daemon/` spike. **This Feature design can be drafted now, but execution MUST NOT begin until CR-00080 is merged to `main`.** The operator MUST verify CR-00080 status with `iw item-status CR-00080 --json` (status: `done` AND merged) before approving CR-00086 for batch execution.
  - **SOFT: CR-00061 (flaky-detect aggregator)** — DONE, on main. Provides `scripts/flake_detect_aggregate.py` output that the flaky-count reader parses.
  - **SOFT: CR-00047 (diff-coverage artefacts)** — DONE, on main. Coverage trend reader uses CR-00047's `make diff-coverage` artefact pattern.
  - **SOFT: CR-00046 (assertion-baseline file)** — DONE, on main. Baseline-size reader counts lines of `tests/assertion_free_baseline.txt`.
  - **SOFT: CR-00059 (mutation pipeline foundations)** — DONE, on main. CR-00080 builds on this.
- **Blocks**: None

## Impacted Paths

- `orch/test_health_service.py`
- `orch/cli/**`
- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/jobs/aggregator.py`
- `dashboard/routers/tests.py`
- `dashboard/routers/quality.py`
- `dashboard/templates/fragments/test_health_panel.html`
- `dashboard/templates/pages/**`
- `.github/workflows/test-health.yml`
- `tests/integration/test_test_health_service.py`
- `tests/dashboard/test_test_health_panel.py`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `docs/IW_AI_Core_Database_Schema.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **Unit tests** (S03 / S05):
  - `tests/unit/test_test_health_service.py` — parses each artefact source from canned fixture files (mutation JSON, coverage XML, flaky log, baseline file); asserts the parsed value+meta tuple; covers missing-source graceful degradation (returns None, not raise).
  - `tests/unit/test_test_health_sparkline.py` — given a list of `TestHealthSnapshot` rows, the SVG path string produced by the panel render contains the expected `M…L…` commands for ascending and descending sequences; an empty list yields the empty-state SVG.
- **Integration tests** (S03 / S05):
  - `tests/integration/test_test_health_service.py` — using the testcontainer Postgres + the new migration: `capture_snapshot` round-trips through the DB; `latest()` and `trend(limit=30)` return correct ordering; idempotency: two captures within the same minute produce one row.
  - `tests/dashboard/test_test_health_panel.py` — using the dashboard test client + a seeded session: GET `/projects/iw-ai-core/test-health` returns HTTP 200, body contains the four metric labels and 4 `<svg>` tags (or one empty-state placeholder per missing metric); GET `/projects/iw-ai-core/tests` includes the panel mount point.
  - `tests/integration/test_jobs_aggregator_test_health.py` — after running `capture_snapshot`, the aggregator's union query returns one row with `job_type='test-health-capture'`.
- **Migration round-trip** (S01 / S02):
  - The standard `tests/integration/data_layer/test_migration_round_trip.py` pattern; covered by the `make migration-check` QV gate at S02.
- **Updated tests**:
  - `tests/dashboard/test_tests_view.py` (if it exists) — add one assertion that the page now mounts the test-health fragment.
  - `tests/integration/test_jobs_aggregator.py` (if it exists) — extend the type-coverage assertion to include `test-health-capture`.

**TDD RED-evidence requirement** (per `skills/iw-ai-core-testing/SKILL.md`): S03 and S05 are behaviour-implementing steps. Each MUST capture `tdd_red_evidence` showing the failing test was run before implementation existed (snippet of `AssertionError` / `NotImplementedError`).

## Notes

- **Migration lock**: checked free at design time (`iw migration-lock status` → free). Re-verify at S01 launch.
- **CR-00080 hard dep**: the design explicitly forbids execution before CR-00080 merges. The operator must check `iw item-status CR-00080 --json` shows `status=done` and the merge commit is on `main` before approving the CR-00086 batch.
- **Risk: mutation-source format drift**. CR-00080 may change the JSON shape of the mutation-results artefact. S03's reader MUST handle both the legacy (CR-00059) and new (CR-00080) shapes; the service module pins the parser behind a small adapter so a future shape change is a one-file edit.
- **Risk: coverage-XML location**. CR-00047 emits to `coverage.xml` at repo root; S03 reuses `orch/coverage_service.py`'s existing path resolution rather than re-implementing it.
- **Out of scope**: alerting on metric regressions (e.g., mutation score drops by N), metric thresholds with red/amber/green colouring, cross-project test-health rollups. These are obvious follow-ups but are NOT in this CR's scope.
- **Sync chores**: S07 runs `iw sync-skills` after editing `skills/iw-ai-core-testing/`. Operator notes apply (see `feedback_skills_sync` memory).
