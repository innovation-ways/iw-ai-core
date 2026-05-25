# F-00090: Regression-rate tracking — correlate filed Incidents back to the merge that introduced the regression; report as a quality KPI alongside throughput in the dashboard

**Type**: Feature
**Priority**: High
**Created**: 2026-05-24
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies. Testcontainer fixtures in tests are exempt. No agent may run `docker compose up/down/restart`, prune commands, or any container/volume/network state change. The orchestration DB on port 5433 is **never** touched directly.

## ⛔ Migrations: agents generate, daemon applies

This Feature **adds** an Alembic migration (S01). The Database agent writes the revision file only — the daemon's merge pipeline runs the pre-merge dry-run on a testcontainer and then applies the migration to the live orch DB post-merge. No agent shall run `alembic upgrade head` against the live DB.

## Description

Adds a regression-rate quality KPI to the dashboard: every filed Incident gets classified against the merge that introduced the underlying regression (operator-curated, optionally seeded by a heuristic auto-classifier), and the per-week ratio of regressions-to-merges is rendered alongside throughput. This makes the dashboard balanced — throughput without a regression metric is misleading, and a high throughput with a rising regression rate is worse than a steady throughput with a low one.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key surfaces this Feature integrates with:

- `orch/db/models.py` — `WorkItem` model (line 514) — extension target for regression-link fields.
- `dashboard/routers/items.py` — Incident detail page (host for the classification form).
- `dashboard/routers/batches.py` — Batches/History views (host for the regression-risk badge).
- `dashboard/routers/project_dashboard.py` — per-project home (host for the Quality KPIs section).
- `orch/cli/` — CLI command group (host for the new `iw regression-classify` command).
- `orch/regression_link_service.py` — new module (service + heuristic auto-classifier).
- `scripts/backfill_regression_classification.py` — new backfill script (operator-run, not CI).
- `docs/IW_AI_Core_Database_Schema.md` — must document the new fields.
- `docs/IW_AI_Core_Dashboard_Design.md` — must document the new KPI view.
- `docs/IW_AI_Core_Testing_Strategy.md` §10 — gains a new section.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.7 — flips TODO → DONE at v1.4.
- `skills/iw-ai-core-testing/` — adds a cross-reference to the regression KPI.

## Scope

### In Scope

- New schema fields on `work_items` (no separate table): `introduced_by_work_item_id` (TEXT FK NULLABLE), `introduced_by_commit_sha` (TEXT NULLABLE), `regression_classification` (ENUM `regression|pre_existing|unknown` NULLABLE), `classified_at` (TIMESTAMPTZ NULLABLE), `classified_by` (TEXT NULLABLE). Indexed on `introduced_by_work_item_id`.
- Alembic migration with `doc=` strings on each new column.
- `orch/regression_link_service.py` exposing `classify(item_id, introduced_by, sha, classification, classified_by)` plus a heuristic `suggest_introducer(item_id) -> list[Candidate]`.
- `iw regression-classify` CLI command (subcommand of the `iw` root CLI) that runs the heuristic against an Incident and prints ranked suggestions; supports `--accept TOP` to write the top suggestion via the service with `classified_by = 'heuristic:auto'`.
- htmx-driven classification form on the Incident detail page: searchable dropdown of prior merged work items, free-text commit SHA, radio for classification, "Accept suggestion" button when the heuristic has a top candidate.
- Quality KPIs section on the per-project home **and** dedicated `/project/{id}/quality-kpis` route showing: merges/week, regressions/week, regression rate (b/a), 12-week trend chart (inline SVG, no JS library).
- Regression-risk badge on the Batches/History rows showing the count of Incidents pointing to a merged item via `introduced_by_work_item_id`.
- `scripts/backfill_regression_classification.py` runs the heuristic auto-classifier against every existing Incident and persists suggestions for operator triage. **Manual run only** — not a CI step.
- Integration test for the service + heuristic.
- Dashboard tests for the classification form fragment and the Quality KPIs section.
- Doc updates: schema doc, dashboard doc, testing-strategy §10, skill cross-reference, tracker row 4.7 → DONE v1.4.
- Browser verification (qv-browser) captures the classification form, the Quality KPIs section with at least one classified regression, and the regression badge on a Batches/History row.

### Out of Scope

- Automatic classification without operator confirmation. The heuristic always suggests; the human always confirms (acceptance is recorded via the UI's accept button or the `--accept` flag).
- Cross-project regression analytics. The KPI is per-project only.
- Surfacing regression rate to external systems (no API export, no webhook, no Prometheus metric).
- Refactoring the existing throughput KPI rendering or the underlying `merges/week` query.
- Re-classifying historical Incidents inside CI; backfill is manual.
- Changes to the Incident state machine (the new fields are orthogonal to `status`/`phase`).

## Implementation Plan

### Agents and Execution Order

> **Step-granularity rule**: each step targets one cohesive concern. Multi-concern work is split. See `skills/iw-workflow/SKILL.md`.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `WorkItem` regression-link fields + ENUM + Alembic migration | — |
| S02 | backend-impl | `orch/regression_link_service.py` + `iw regression-classify` CLI + integration test | — |
| S03 | frontend-impl | Incident classification form (htmx fragment + route in `dashboard/routers/items.py`) + dashboard test | — |
| S04 | frontend-impl | Quality KPIs section + `/project/{id}/quality-kpis` route + per-merge regression badge on Batches/History + dashboard test | — |
| S05 | backend-impl | `scripts/backfill_regression_classification.py` + docs (schema, dashboard, testing-strategy §10) + tracker row 4.7 → DONE + skill cross-ref + `iw sync-skills` | — |
| S06 | code-review | Per-agent code review of S01..S05 | — |
| S07 | code-review-final | Cross-cutting final review | — |
| S08..S15 | qv-gate | lint, format, typecheck, migration-check, arch-check, security-sast, unit-tests, integration-tests | — |
| S16 | qv-browser | Browser verification end-to-end | — |
| S17 | self-assess-impl | Self-assessment via iw-item-analyze skill (soft) | — |

Note: per the skill rules, migration-check is inserted **immediately after** the Database step + its review wrap. The single S06 CR step reviews all implementation steps S01..S05 (per-agent reviews documented in one report); S07 is the cross-agent final review.

### Database Changes

- **New tables**: None — fields added directly to `work_items`.
- **Modified tables**: `work_items` gains `introduced_by_work_item_id TEXT NULLABLE`, `introduced_by_commit_sha TEXT NULLABLE`, `regression_classification regression_classification_enum NULLABLE`, `classified_at TIMESTAMPTZ NULLABLE`, `classified_by TEXT NULLABLE`. New index `ix_work_items_introduced_by_work_item_id`. New PostgreSQL ENUM `regression_classification_enum` with values `('regression', 'pre_existing', 'unknown')`.
- **Migration notes**: NULLABLE everywhere — no backfill required at upgrade time (the operator runs the backfill script separately). All columns carry `doc=` strings. The ENUM type is created in `upgrade()` and dropped in `downgrade()`. Round-trip test required (`make migration-check`).

### API Changes

- **New endpoints**:
  - `POST /project/{project_id}/item/{item_id}/regression-classify` — htmx endpoint, accepts form data, returns the updated row fragment.
  - `GET /project/{project_id}/quality-kpis` — full page rendering the KPI section.
  - `GET /project/{project_id}/item/{item_id}/regression-suggestions` — htmx endpoint returning ranked heuristic suggestions for the classification form.
- **Modified endpoints**: `dashboard/routers/batches.py` row renderer adds the regression-count badge. `dashboard/routers/project_dashboard.py` per-project home embeds the Quality KPIs section.

### Frontend Changes

- **New fragments**: `dashboard/templates/fragments/regression_classification_form.html`, `dashboard/templates/fragments/regression_suggestion_list.html`, `dashboard/templates/fragments/quality_kpis_section.html`, `dashboard/templates/fragments/regression_badge.html`.
- **New pages**: `dashboard/templates/pages/quality_kpis.html`.
- **Modified components**: Batches/History row template (regression badge), Incident detail page template (mount classification form), per-project home page (mount KPI section).
- **No JS library**: trend chart rendered as inline SVG generated server-side.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00090/F-00090_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00090/F-00090_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `ai-dev/active/F-00090/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/F-00090/prompts/F-00090_S01_Database_prompt.md` | Prompt | S01 — DB fields + migration |
| `ai-dev/active/F-00090/prompts/F-00090_S02_Backend_prompt.md` | Prompt | S02 — Service + CLI + integration test |
| `ai-dev/active/F-00090/prompts/F-00090_S03_Frontend_prompt.md` | Prompt | S03 — Incident classification form |
| `ai-dev/active/F-00090/prompts/F-00090_S04_Frontend_prompt.md` | Prompt | S04 — Quality KPIs + regression badge |
| `ai-dev/active/F-00090/prompts/F-00090_S05_Backend_prompt.md` | Prompt | S05 — Backfill script + docs + tracker + skill |
| `ai-dev/active/F-00090/prompts/F-00090_S06_CodeReview_prompt.md` | Prompt | S06 — Per-agent code review |
| `ai-dev/active/F-00090/prompts/F-00090_S07_CodeReview_Final_prompt.md` | Prompt | S07 — Cross-agent final review |
| `ai-dev/active/F-00090/prompts/F-00090_S08_QV_Lint_prompt.md` | Prompt | S08 — QV lint |
| `ai-dev/active/F-00090/prompts/F-00090_S09_QV_Format_prompt.md` | Prompt | S09 — QV format-check |
| `ai-dev/active/F-00090/prompts/F-00090_S10_QV_TypeCheck_prompt.md` | Prompt | S10 — QV typecheck |
| `ai-dev/active/F-00090/prompts/F-00090_S11_QV_MigrationCheck_prompt.md` | Prompt | S11 — QV migration-check |
| `ai-dev/active/F-00090/prompts/F-00090_S12_QV_ArchCheck_prompt.md` | Prompt | S12 — QV arch-check |
| `ai-dev/active/F-00090/prompts/F-00090_S13_QV_SecuritySast_prompt.md` | Prompt | S13 — QV security-sast |
| `ai-dev/active/F-00090/prompts/F-00090_S14_QV_UnitTests_prompt.md` | Prompt | S14 — QV unit-tests |
| `ai-dev/active/F-00090/prompts/F-00090_S15_QV_IntegrationTests_prompt.md` | Prompt | S15 — QV integration-tests |
| `ai-dev/active/F-00090/prompts/F-00090_S16_BrowserVerification_prompt.md` | Prompt | S16 — qv-browser |
| `ai-dev/active/F-00090/prompts/F-00090_S17_SelfAssess_prompt.md` | Prompt | S17 — self-assess |

Reports are created during execution under `ai-dev/active/F-00090/reports/`.

## Acceptance Criteria

### AC1: Schema additions are persisted and reversible

```
Given a fresh testcontainer Postgres with the existing migration head applied
When `alembic upgrade head` runs with the new revision
Then the `work_items` table has the five new columns with the documented nullability,
  the ENUM `regression_classification_enum` exists with three values,
  the index `ix_work_items_introduced_by_work_item_id` exists,
  and `downgrade base` then `upgrade head` succeeds cleanly (round-trip).
```

### AC2: Service classifies an Incident and persists the link

```
Given a merged Feature F-00001 and a filed Incident I-00001 in the same project
When `regression_link_service.classify(I-00001, F-00001, sha=None, classification='regression', classified_by='operator:sergiog')` is called
Then `WorkItem(I-00001).introduced_by_work_item_id == 'F-00001'`,
  `regression_classification == 'regression'`,
  `classified_at` is a non-null UTC timestamp,
  and `classified_by == 'operator:sergiog'`.
```

### AC3: Heuristic suggests the most-likely introducing merge

```
Given an Incident I-00001 whose fix has been MERGED (status == 'done') and whose merge commit touched files A and B
When `regression_link_service.suggest_introducer(I-00001)` is called
Then the returned candidates list is sorted by descending score (files-touched count) then by recency,
  each candidate carries a `commit_sha` and (when resolvable) a `work_item_id` and `score`,
  candidates resolving to a work item in a different project are filtered out,
  and an empty list is returned when no prior commit touches A or B.
When the Incident is NOT yet merged (status != 'done')
Then `suggest_introducer` returns `[]` immediately without running git,
  and logs at INFO level "I-NNNNN not merged yet; no file list available".
```

### AC4: CLI command prints suggestions and accepts the top one

```
Given an Incident with at least one heuristic suggestion
When `uv run iw regression-classify --incident I-00001` runs
Then the suggestions are printed as a ranked list with score and (when known) work item ID,
  exit code is 0,
When `--accept 1` is added
Then the service is called with `classified_by = 'heuristic:auto'`,
  the row is persisted,
  and the command exits 0.
```

### AC5: Incident detail page shows the classification form

```
Given an authenticated browser session on `/project/{pid}/item/I-00001`
When the page renders
Then the "Regression classification" form is visible with a searchable dropdown,
  a free-text commit SHA input,
  a radio group (regression | pre-existing | unknown),
  and — if a heuristic suggestion is available — an "Accept suggestion" button.
When the operator submits the form via htmx
Then the row updates inline (no full page reload),
  and the persisted values match the submitted form.
```

### AC6: Quality KPIs section renders weekly metrics with trend chart

```
Given a project with at least one merged item and one classified regression
When the operator visits `/project/{pid}/quality-kpis` (and the per-project home)
Then the section shows merges/week, regressions/week, and the regression rate (b/a) for the current week,
  a 12-week trend chart is rendered as inline SVG (no client-side JS dependency),
  and the rate is computed as `regressions / merges` (or `0.0` when merges == 0).
```

### AC7: Regression badge appears on Batches/History rows

```
Given a merged work item that is the `introduced_by_work_item_id` of N classified regressions (N >= 1)
When the operator views the Batches/History page containing that merge row
Then a badge "N regressions" is visible on that row,
When N == 0
Then no badge is rendered on the row.
```

### AC8: Backfill script populates suggestions without persisting confirmations

```
Given a project with existing Incidents that have no `regression_classification`
When `python scripts/backfill_regression_classification.py --project {pid}` runs
Then for each Incident, the heuristic is invoked and the top suggestion is logged,
  no row is silently confirmed (operator triage required via the UI),
  the script is idempotent (re-running yields the same suggestions, no duplicate rows),
  and the script exits 0 with a summary line.
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Incident with no fix files | merge SHA present but `git show --name-only` returns no files | `suggest_introducer` returns `[]`; UI form shows "No heuristic suggestion available" |
| Incident not yet merged | `WorkItem.status != 'done'` | `suggest_introducer` returns `[]` without invoking git; INFO log line recorded; UI form omits "Accept suggestion" |
| Candidate resolves to a different project | git blame surfaces a SHA whose commit message names `F-NNNNN` from another project | Candidate is dropped from the result list (cross-project FK rejected at write anyway) |
| Incident classified as `pre_existing` | classification = pre_existing | `introduced_by_work_item_id` is NULL; regression KPI ignores this row; no badge attribution to any merge |
| `introduced_by` references unknown work item | FK target not in `work_items` | Service raises `ValueError`; CLI exits 2 with a clear message; htmx form re-renders with a validation error |
| Week with zero merges and N regressions | merges=0, regressions=N | Rate is reported as `0.0` (not NaN, not ZeroDivisionError); trend chart still plots regressions as raw counts |
| Heuristic finds 0 candidates | git blame returns empty | CLI prints "No suggestions"; exit 0; UI form shows the form without the "Accept suggestion" button |
| Operator re-classifies an Incident | second `classify()` call with different `classified_by` | Latest values overwrite previous; `classified_at` updates; previous attribution is lost (not appended — single-row model) |
| Backfill script run on project with 0 Incidents | no incidents | Exits 0; prints "0 incidents processed"; no DB writes |
| Trend chart with <12 weeks of history | history length = 4 | Chart plots 4 weeks; X axis labels reflect actual weeks; no padding zeros |
| Regression classified against a non-merged work item | FK target.status != 'done' | Service rejects with `ValueError("introduced_by must be a merged work item")`; UI shows validation error |
| Two regressions point to the same merge | N=2 for same `introduced_by_work_item_id` | Badge reads "2 regressions"; KPI counts both rows in the regressions/week column |

## Invariants

1. **NULL means unknown.** A row with `regression_classification IS NULL` is "not yet classified" — it never contributes to KPI numerators and never produces a badge.
2. **Single-source attribution.** Each Incident has at most one `introduced_by_work_item_id`; the model does not support multi-cause attribution.
3. **Operator confirmation.** The heuristic auto-classifier never persists a classification without operator action (UI accept button or CLI `--accept`). `classified_by` always records the path (`operator:USER`, `heuristic:auto` only when an operator pressed accept).
4. **FK integrity.** `introduced_by_work_item_id` is validated against `work_items(project_id, id)` at write time. Cross-project references are rejected.
5. **KPI determinism.** For a given DB snapshot, the rendered Quality KPIs section is deterministic (same numbers on every render for the same inputs).
6. **Rate guard.** When `merges == 0` in a week, the regression rate is `0.0` (never NaN, never an exception).
7. **Migration round-trip.** `upgrade head` → `downgrade base` → `upgrade head` succeeds cleanly; no orphaned ENUM types, no leftover indexes.
8. **Scope discipline.** No production file outside `scope.allowed_paths` is modified; the merge-time gate enforces this.

## Dependencies

- **Depends on**: None (hard).
- **Soft sequencing**: Recommended to land **after CR-00080** so that the "Test Health" panel from §4.6 establishes the dashboard surface conventions this Feature's KPI section will mirror. Not a hard blocker — design and review can run in parallel; only the visual coherence benefits from 4.6 → 4.7 order.
- **Blocks**: None.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/regression_link_service.py`
- `orch/cli/**`
- `dashboard/routers/items.py`
- `dashboard/routers/batches.py`
- `dashboard/routers/project_dashboard.py`
- `dashboard/templates/fragments/**`
- `dashboard/templates/pages/**`
- `dashboard/static/styles.css`
- `scripts/backfill_regression_classification.py`
- `tests/integration/test_regression_link_service.py`
- `tests/integration/test_backfill_regression_classification.py`
- `tests/dashboard/test_regression_classification_form.py`
- `tests/dashboard/test_quality_kpis_section.py`
- `docs/IW_AI_Core_Testing_Strategy.md`
- `docs/IW_AI_Core_Database_Schema.md`
- `docs/IW_AI_Core_Dashboard_Design.md`
- `skills/iw-ai-core-testing/**`
- `.claude/skills/iw-ai-core-testing/**`
- `ai-dev/work/TESTS_ENHANCEMENT.md`

## TDD Approach

- **Unit tests**: pure helpers in `orch/regression_link_service.py` (rate computation, candidate ranking) covered by `tests/integration/test_regression_link_service.py` (using the testcontainer fixture).
- **Integration tests**: `tests/integration/test_regression_link_service.py` covering AC2..AC4 (classify, suggest, CLI accept flow); `tests/integration/test_backfill_regression_classification.py` covering AC8 (backfill processes only unclassified rows, persists no classifications, idempotent across re-runs, handles zero-incident project, `--dry-run` emits suggestions without writes); migration round-trip enforced by `make migration-check` (AC1) via the existing `tests/integration/test_migrations_round_trip.py` harness.
- **Dashboard tests**: `tests/dashboard/test_regression_classification_form.py` covering AC5 (form rendering + htmx submit roundtrip); `tests/dashboard/test_quality_kpis_section.py` covering AC6 + AC7 (KPI numbers + trend SVG + badge presence/absence).
- **Edge cases**: rows in the Boundary Behavior table — zero merges, zero candidates, unknown FK, cross-project FK rejection, pre-existing classification not contributing to KPIs, re-classification overwrites.
- **RED-first discipline**: S02, S03, S04, and S05 all add behavioural tests and must record `tdd_red_evidence` (AssertionError snippet from the failing run before implementation). S01 follows the `n/a — schema/migration only; verified by make migration-check round-trip` form.

## Notes

- **Why now**: throughput-only KPIs mislead. A regression-rate dimension turns the dashboard into a balanced scorecard (METR-style). Tracker §8 row 4.7.
- **Soft sequencing**: 4.6 (CR-00080 self-dashboarding) is the natural sibling; aligning the visual layout of the KPI section with 4.6's "Test Health" panel reduces dashboard sprawl.
- **Migration lock**: free at design time (verified via `iw migration-lock status`). S01 will re-verify before writing the revision.
- **No state-machine change**: the new fields are orthogonal to `WorkItem.status` / `phase`; the Incident lifecycle in `docs/IW_AI_Core_Database_Schema.md` is unchanged. S01's doc edit only adds field documentation.
- **Heuristic limits**: the `git log -L` / `git blame` heuristic is best-effort — it can return false positives (a refactor commit touched the line; the introducing logic was somewhere else). The operator is the source of truth; the heuristic is a suggestion. The heuristic only runs against **merged** Incidents (`status == 'done'` with a recorded merge SHA): the file list comes from `git show --name-only <merge_sha>`, and unmerged Incidents short-circuit to `[]` without invoking git. See S02 prompt "File-discovery contract" for the exact mechanism.
- **No CI run of the backfill**: the backfill script is idempotent but expensive (one `git log -L` invocation per Incident's fix files). Running it in CI would inflate test time; running it as an operator-triggered command keeps the cost off the critical path.
- **Browser evidence (pre)**: Deferred — the pre-state UI is the existing per-project home / Incident detail / Batches view *without* the new classification form, KPI section, or badge. qv-browser captures the post-state at S16.
