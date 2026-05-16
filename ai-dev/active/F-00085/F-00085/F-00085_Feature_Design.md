# F-00085: Auto-Merge Resolver — Observability + Per-Project Control

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-16
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in `tests/integration/` are exempt.
The browser-verification step (S24) runs against the isolated per-worktree e2e compose stack which the daemon owns — the agent does not call `docker compose` directly. See `executor/CLAUDE.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Feature adds **one** new alembic migration that creates two tables: `merge_auto_verdicts` (operator verdicts on `merge_auto_resolved` events) and `auto_merge_project_config` (per-project phase + runtime override). The agent in S01 writes the migration file; the daemon applies it during the pre-merge phase. S03 runs `make migration-check` to validate the file before downstream agents inherit a wrong schema.

## Description

Make the LLM auto-merge resolver visible AND operator-controllable from the dashboard. Adds a new `/<project>/auto-merge` page with status chip on every project page, an activity log of `merge_auto_*` events with side-by-side diff viewer + verdict capture, accuracy + token-cost rollups, refuse-list activity breakdown, and a daemon-scheduled health probe. Also adds a per-project control surface: phase toggle and runtime picker that overrides the global `executor/auto_merge.toml` defaults — mirroring the F-00081 step-level override pattern.

## Project Context

Read the project's `CLAUDE.md` and the canonical reference doc [`ai-dev/active/AUTO_MERGE_RESOLUTION.md`](../AUTO_MERGE_RESOLUTION.md) §5b for the full sub-phase scope. Key constraints:

- This is the **Observability + Control** sub-phase of the auto-merge initiative; the resolver itself (Phase 0 plumbing + Phase 1 dry-run) shipped in F-00084 (merge `9ba69891`).
- `daemon_events` is append-only — verdicts MUST live in a sidecar table (`merge_auto_verdicts`), not on `daemon_events` rows.
- F-00081's `agent_runtime_options` table is the SOLE source of `(cli_tool, model)` choices; this Feature reuses it for the per-project runtime picker.
- Dashboard layer: FastAPI + Jinja2 + htmx; templates in `dashboard/templates/`; routers in `dashboard/routers/`; CSS via `dashboard/static/styles.css` (CR-00033 fallback rule).

## Scope

### In Scope

- New alembic migration creating two tables:
  - `merge_auto_verdicts` — composite PK `(project_id, daemon_event_id)`, FK to `daemon_events.id`; columns `verdict` (enum: pending|correct|wrong|partial), `verdict_notes` TEXT, `verdicted_by` TEXT NULL, `verdicted_at` TIMESTAMPTZ.
  - `auto_merge_project_config` — PK `project_id` (FK to projects); columns `phase` INT NULL, `runtime_option_id` INT NULL FK `agent_runtime_options.id`, `updated_at` TIMESTAMPTZ, `updated_by` TEXT NULL. NULL on a column means "use TOML default".
- New ORM models in `orch/db/models.py` for both tables; `__tablename__`, composite PK / unique constraints, append-only marker (none — both tables are mutable on UPDATE).
- New config section `[health]` in `executor/auto_merge.toml`: `probe_interval_seconds` (default 300), `failure_rate_threshold_per_day` (default 3). Loader extended in `orch/daemon/auto_merge.py`.
- New module `orch/auto_merge_aggregator.py` with queries:
  - `get_status_snapshot(project_id)` — resolved phase + runtime + counts since deployment + health
  - `list_recent_events(project_id, page, event_type_filter)` — paginated `daemon_events` slice
  - `get_event_detail(project_id, event_id)` — single row + verdict (LEFT JOIN `merge_auto_verdicts`)
  - `get_verdict_rollup(project_id, window: '7d'|'30d')` — counts grouped by verdict
  - `get_refuse_list_breakdown(project_id, window)` — counts grouped by `event_metadata->>'reason'`
  - `get_health_summary(project_id)` — latest `auto_merge_health_probe` + last-24h failure count
  - `get_token_cost_rollup(project_id, window)` — sum of `event_metadata.llm_calls[*].input_tokens + output_tokens`, with per-model `MODEL_PRICING` dict in code
  - `resolve_project_config(project_id)` — returns `(phase, runtime_option_id)` with resolution order: per-project DB row > TOML > hardcoded defaults
- New daemon background task `orch/daemon/auto_merge_health.py` — on each poll loop iteration, for each enabled project, check whether last `auto_merge_health_probe` event age exceeds `probe_interval_seconds`; if so, emit one tiny LLM call ("Reply with the single word OK") via `step_executor.sh` using that project's resolved runtime; record the result as a new `auto_merge_health_probe` DaemonEvent with `event_metadata = {runtime_reachable: bool, cli_tool, model, probe_duration_ms, error: str|null}`.
- Update `orch/daemon/auto_merge.py` and `orch/daemon/merge_queue.py` to use `resolve_project_config()` instead of reading TOML directly. TOML stays as the fallback layer; per-project DB row overrides.
- New router `dashboard/routers/auto_merge_ui.py` with 7 endpoints (GET page, GET status fragment, GET events fragment, GET event detail modal, POST verdict, POST config, GET rollup fragment).
- New page template `dashboard/templates/pages/project/auto_merge.html` + fragments:
  - `auto_merge_status_chip.html` (also included from `base.html`)
  - `auto_merge_events_table.html` (rows with inline verdict widget)
  - `auto_merge_event_detail.html` (modal with diff viewer + verdict + notes)
  - `auto_merge_rollup.html` (7d/30d windows, accuracy, token cost)
  - `auto_merge_refuse_list.html` (counter widget; hidden when all zero)
  - `auto_merge_settings.html` (per-project control: phase dropdown 0/1, runtime picker with cli_tool/model groups, "use global default" radio, Save button)
- Diff viewer: server-rendered side-by-side HTML via `difflib.HtmlDiff` (left = LLM `proposed_content` from `event_metadata`, right = `git show main:<file>` at request time). If file no longer exists on main, show "(file no longer exists on main)" placeholder.
- Sidebar nav entry `('/auto-merge', 'Auto-Merge')` added to `base.html`'s project nav.
- Header status chip: included from `base.html` so it appears on every per-project page; visible when resolved phase >= 1; hidden when phase == 0; click routes to `/<project>/auto-merge`.
- CSS additions appended to `dashboard/static/styles.css` for chip + diff-viewer + settings panel + status pills (green/yellow/red).
- Per-model pricing constants in `orch/auto_merge_aggregator.py` (`MODEL_PRICING` dict) covering currently-enabled agent_runtime_options rows (opencode/MiniMax, opencode/openai-gpt-5.3-codex, claude/sonnet-4-6, claude/opus-4-7). Unknown models → cost computed as 0 with a comment "unknown model — update MODEL_PRICING".
- New `auto_merge_health_probe` DaemonEvent type (TEXT, no enum change). New `auto_merge_config_updated` DaemonEvent type emitted on every settings change with metadata recording who/what/when.
- Integration tests covering all 14 ACs; unit tests for aggregator + config resolution; dashboard TestClient tests for each endpoint; migration round-trip.
- Browser-verification step covering: status chip on header, page render with 0 events, page render with seeded events, click→modal→diff viewer, verdict (inline + modal both persist), Settings panel writes, phase=0 hides chip, no regressions on adjacent pages.

### Out of Scope

- Email/Slack/webhook alerting — Tier 3 stops at dashboard-visible signal (see `AUTO_MERGE_RESOLUTION.md` §5b.2).
- Verdict-via-LLM-as-judge automation — possibly Phase 3.
- Cross-project aggregation — per-project only; dashboard's existing routing scopes by project.
- Modifying Phase 1 dry-run behaviour (no auto-apply) — Phase 2 CR.
- Editing the existing TOML allowlist/refuselist patterns — those stay as the safety-rule surface.
- Auth for the Settings POST — dashboard is localhost-only today; if/when remote access lands, add auth there.
- Phase 2/3 in the settings dropdown — only 0/1 are selectable in this Feature (2/3 are still reserved for future CRs).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration + ORM models for `merge_auto_verdicts` AND `auto_merge_project_config`; `event_type` strings (no enum migration) | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | qv-gate | `make migration-check` — round-trip + drift | — |
| S04 | pipeline-impl | `executor/auto_merge.toml` `[health]` section; `orch/daemon/auto_merge.py` extends loader for health config | — |
| S05 | code-review-impl | Per-agent review of S04 | — |
| S06 | backend-impl | `orch/auto_merge_aggregator.py` (8 queries + `MODEL_PRICING`); `orch/daemon/auto_merge_health.py` (probe task); update `auto_merge.py` + `merge_queue.py` to use `resolve_project_config()` | — |
| S07 | code-review-impl | Per-agent review of S06 | — |
| S08 | api-impl | `dashboard/routers/auto_merge_ui.py` — 7 endpoints; register router in dashboard app | — |
| S09 | code-review-impl | Per-agent review of S08 | — |
| S10 | frontend-impl | Page template + 6 fragments + chip include from `base.html`; sidebar nav entry; CSS additions | After S08 |
| S11 | code-review-impl | Per-agent review of S10 | — |
| S12 | code-review-final-impl | Cross-agent review of S01..S11 (implementation cross-cut) | — |
| S13 | tests-impl | Unit + integration + dashboard tests; all 14 ACs | — |
| S14 | code-review-impl | Per-agent review of S13 | — |
| S15 | code-review-final-impl | Final review including tests | — |
| S16 | qv-gate | `make lint` | — |
| S17 | qv-gate | `make test-assertions` | — |
| S18 | qv-gate | `make format-check` | — |
| S19 | qv-gate | `make type-check` | — |
| S20 | qv-gate | `make test-unit` | — |
| S21 | qv-gate | `make test-integration` (timeout 900) | — |
| S22 | qv-gate | `make diff-coverage` (timeout 1800) | — |
| S23 | qv-gate | `make security-secrets` | — |
| S24 | qv-browser | Browser verification per V-list below | — |
| S25 | self-assess-impl | `iw-item-analyze` post-mortem | — |

### Database Changes

- **New tables**:
  - `merge_auto_verdicts(project_id TEXT, daemon_event_id BIGINT, verdict TEXT, verdict_notes TEXT, verdicted_by TEXT, verdicted_at TIMESTAMPTZ)` — composite PK `(project_id, daemon_event_id)`, FK to `daemon_events.id`, CHECK constraint `verdict IN ('pending','correct','wrong','partial')`.
  - `auto_merge_project_config(project_id TEXT PK, phase INT, runtime_option_id INT, updated_at TIMESTAMPTZ DEFAULT now(), updated_by TEXT)` — FK `project_id → projects(id)`, FK `runtime_option_id → agent_runtime_options(id)`, CHECK constraint `phase IS NULL OR phase IN (0, 1)` (Phase 2/3 reserved).
- **Modified tables**: None.
- **Migration notes**: Single alembic file. Pre-flight: agents NEVER run `alembic upgrade`. S03 runs `make migration-check` against a testcontainer.

### API Changes

- **New endpoints** (all under `/<project>/auto-merge/...`):
  - `GET /<project>/auto-merge` — page render
  - `GET /<project>/auto-merge/status` — htmx fragment for the status chip
  - `GET /<project>/auto-merge/events?page=N&type=…` — htmx fragment for the events table
  - `GET /<project>/auto-merge/events/<event_id>` — event detail modal (with diff viewer for `merge_auto_resolved`)
  - `POST /<project>/auto-merge/events/<event_id>/verdict` — body: `{verdict: str, notes: str}` → upserts `merge_auto_verdicts`
  - `POST /<project>/auto-merge/config` — body: `{phase: int|null, runtime_option_id: int|null}` → upserts `auto_merge_project_config`; emits `auto_merge_config_updated` event
  - `GET /<project>/auto-merge/rollup?window=7d|30d` — htmx fragment for the rollup widget
- **Modified endpoints**: None (existing routes unchanged).

### Frontend Changes

- **New page**: `pages/project/auto_merge.html`
- **New fragments**: `fragments/auto_merge_status_chip.html`, `fragments/auto_merge_events_table.html`, `fragments/auto_merge_event_detail.html`, `fragments/auto_merge_rollup.html`, `fragments/auto_merge_refuse_list.html`, `fragments/auto_merge_settings.html`
- **Modified components**: `base.html` (one `{% include 'fragments/auto_merge_status_chip.html' %}` in the header + one nav-row tuple addition); `static/styles.css` (~30 lines of new CSS appended)
- **browser_verification**: `true`

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00085_Feature_Design.md` | Design | This document |
| `F-00085_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00085_S01_Database_prompt.md` | Prompt | DB schema + migration |
| `prompts/F-00085_S02_CodeReview_Database_prompt.md` | Prompt | Per-agent review of S01 |
| `prompts/F-00085_S04_Pipeline_prompt.md` | Prompt | TOML [health] section + loader extension |
| `prompts/F-00085_S05_CodeReview_Pipeline_prompt.md` | Prompt | Per-agent review of S04 |
| `prompts/F-00085_S06_Backend_prompt.md` | Prompt | Aggregator + health probe + config resolution |
| `prompts/F-00085_S07_CodeReview_Backend_prompt.md` | Prompt | Per-agent review of S06 |
| `prompts/F-00085_S08_API_prompt.md` | Prompt | 7 dashboard endpoints + router |
| `prompts/F-00085_S09_CodeReview_API_prompt.md` | Prompt | Per-agent review of S08 |
| `prompts/F-00085_S10_Frontend_prompt.md` | Prompt | Page + fragments + chip + CSS |
| `prompts/F-00085_S11_CodeReview_Frontend_prompt.md` | Prompt | Per-agent review of S10 |
| `prompts/F-00085_S12_CodeReview_Final_prompt.md` | Prompt | Cross-agent review (impl) |
| `prompts/F-00085_S13_Tests_prompt.md` | Prompt | Unit + integration + dashboard tests |
| `prompts/F-00085_S14_CodeReview_Tests_prompt.md` | Prompt | Per-agent review of S13 |
| `prompts/F-00085_S15_CodeReview_Final_prompt.md` | Prompt | Final review including tests |
| `prompts/F-00085_S24_BrowserVerification_prompt.md` | Prompt | playwright-cli E2E |
| `prompts/F-00085_S25_SelfAssess_prompt.md` | Prompt | iw-item-analyze |

## Acceptance Criteria

### AC1: Empty-state page render

```
Given a fresh dashboard with zero merge_auto_* events and zero
      auto_merge_project_config rows
When  the operator navigates to /<project>/auto-merge
Then  the page renders with the status chip showing "PHASE 0 (global default)"
  AND the events table shows the empty-state message
      "No auto-merge events yet — Phase 1 only fires on merge-queue conflicts
       in tests/**, docs/**, ai-dev/active/**/reports/**"
  AND the refuse-list widget is hidden (zero events grouped by reason)
  AND the verdict rollup widget shows "0 events" for both 7d and 30d windows
  AND the token-cost rollup shows "$0.00" for both windows
  AND the Settings panel shows phase=0 and "Use global default" runtime selected
  AND HTTP status is 200
```

### AC2: Seeded events render with inline verdict widgets

```
Given three merge_auto_resolution_attempted + three merge_auto_resolved
      DaemonEvents seeded into daemon_events for the project, no verdicts yet
When  the operator navigates to /<project>/auto-merge
Then  the events table shows six rows
  AND each merge_auto_resolved row displays an inline verdict widget with
      buttons [pending] [correct] [wrong] [partial] with [pending] highlighted
  AND each merge_auto_resolution_attempted row shows no verdict widget
      (verdicts only apply to merge_auto_resolved events)
  AND clicking a row opens the event detail modal
```

### AC3: Inline verdict persists

```
Given AC2 state
When  the operator clicks [correct] on an event's inline widget
Then  POST /<project>/auto-merge/events/<event_id>/verdict is fired
      with body {"verdict": "correct", "notes": ""}
  AND a row is upserted into merge_auto_verdicts with verdict="correct"
  AND the fragment re-renders showing [correct] highlighted
  AND the rollup widget moves the event into the "correct" count
  AND a subsequent reload of the page shows the same verdict state
```

### AC4: Modal diff viewer with current main content

```
Given a merge_auto_resolved event whose event_metadata contains
      llm_calls=[{file_path: "tests/integration/test_x.py", proposed_content: "<full file content>"}]
  AND main currently has tests/integration/test_x.py
When  the operator clicks the row OR a "View diff" link
Then  the modal opens with a side-by-side diff viewer
  AND the left pane is the LLM's proposed_content
  AND the right pane is the file's CURRENT content on main
      (fetched via subprocess `git show main:<file>` at request time)
  AND lines that differ are highlighted
  AND the modal also shows the verdict widget AND a notes textarea
  AND saving a verdict + notes from the modal persists both fields
```

### AC5: Health probe + chip indicator

```
Given the daemon is running and auto_merge_project_config has phase=1
      for the project, runtime_option_id=4 (claude/sonnet-4-6, enabled)
  AND auto_merge.toml [health] probe_interval_seconds = 30 (test override)
When  the daemon poll loop runs for >= 30 seconds
Then  an auto_merge_health_probe DaemonEvent fires with
      event_metadata = {runtime_reachable: True, cli_tool: "claude",
                        model: "claude-sonnet-4-6", probe_duration_ms: <int>,
                        error: None}
  AND the status chip shows the green ✓ indicator
  AND when a subsequent probe fails (stub the subprocess to exit 1),
      the chip transitions to yellow ⚠ after one failure
  AND when failures exceed failure_rate_threshold_per_day, chip shows red ✗
```

### AC6: Phase 0 hides the chip

```
Given auto_merge_project_config.phase = 0 (or no row + TOML phase = 0)
When  the operator visits any per-project page (queue, history, batches, code, docs)
Then  the header status chip is hidden (not rendered at all, not just CSS-display:none)
  AND /<project>/auto-merge route is still reachable AND returns 200
  AND the page body shows the friendly message
      "Resolver is in plumbing-only mode for this project.
       Use Settings to enable Phase 1 dry-run."
  AND the events table is hidden
  AND the Settings panel IS still shown so the operator can advance the phase
```

### AC7: Refuse-list breakdown widget

```
Given multiple merge_auto_resolution_skipped events with
      event_metadata.reason values: "refuse_list" (3x), "binary" (1x),
      "phase_0" (2x), "not_allowlisted" (5x)
When  the operator opens /<project>/auto-merge
Then  the refuse-list widget shows the four reason rows with counts (3, 1, 2, 5)
  AND when there are zero merge_auto_resolution_skipped events, the widget
      is hidden entirely (not rendered as empty)
```

### AC8: Token-cost rollup with per-model pricing

```
Given merge_auto_resolved events with llm_calls metadata containing
      input_tokens=10000, output_tokens=2000 for cli_tool=claude, model=claude-sonnet-4-6
  AND MODEL_PRICING constant defines claude-sonnet-4-6: $3/M input + $15/M output
When  the rollup widget renders
Then  the cost calculation is (10000 * 3 + 2000 * 15) / 1_000_000 = $0.06
  AND both 7d and 30d windows are computed against created_at
  AND a row with an unknown model contributes $0.00 to the rollup
      and a banner says "Unknown model in event metadata — pricing may be incomplete"
```

### AC9: Existing pages unaffected

```
When  every existing dashboard route is visited
      (/<project>/queue, /history, /batches, /code, /docs, /tests, /quality,
       /jobs, /worktrees, /healthz)
Then  HTTP 200
  AND no template-render errors
  AND console-error count <= existing baseline (no new errors introduced)
  AND existing fragments (jobs table, batch detail, item header) render unchanged
```

### AC10: Per-project phase override (control surface)

```
Given two projects A and B both managed by the daemon, both with phase=0 by default
  AND auto_merge_project_config has a row for A with phase=1, runtime_option_id=NULL
  AND no row for B
When  a merge-queue conflict happens on project A → invokes the LLM
  AND a merge-queue conflict happens on project B → does NOT invoke the LLM
Then  project A emits merge_auto_resolution_attempted + merge_auto_resolved
  AND project B emits merge_auto_resolution_skipped with reason="phase_0"
  AND the status chip on A's pages shows "PHASE 1 (per-project override)"
  AND the status chip on B's pages is hidden
```

### AC11: Per-project runtime override

```
Given auto_merge_project_config for project A: phase=1, runtime_option_id=4
      (claude + claude-sonnet-4-6)
  AND TOML default runtime_option_id is null (falls back to project default id=1
      opencode + MiniMax-M2.7)
When  a merge-queue conflict occurs on project A
Then  step_executor.sh is invoked with cli_tool=claude, model=claude-sonnet-4-6
  AND the resulting merge_auto_resolved event_metadata shows
      llm_calls[*].cli_tool="claude" and model="claude-sonnet-4-6"
  AND the status chip shows the resolved runtime "claude/claude-sonnet-4-6"
```

### AC12: Settings panel writes

```
Given the Settings panel rendered on /<project>/auto-merge
When  the operator selects phase=1, runtime_option_id=4, clicks Save
Then  POST /<project>/auto-merge/config is fired with body
      {"phase": 1, "runtime_option_id": 4}
  AND an auto_merge_project_config row is upserted with the new values
  AND an auto_merge_config_updated DaemonEvent fires with metadata
      {old: {...}, new: {...}, updated_by: "<operator id or dashboard>"}
  AND the page re-renders (htmx swap) with the chip showing
      "PHASE 1 (per-project override) — claude/claude-sonnet-4-6"
  AND the next merge-queue conflict for the project uses the new config
```

### AC13: Clear override falls back to TOML

```
Given auto_merge_project_config has a row for project A with phase=1
When  the operator selects "Use global default" + clicks Save
Then  POST /<project>/auto-merge/config is fired with body
      {"phase": null, "runtime_option_id": null}
  AND the auto_merge_project_config row is either deleted OR both fields nulled
  AND a subsequent merge-queue conflict resolves config from TOML
      (which has phase=1, runtime_option_id=null → project default id=1)
  AND the chip shows "PHASE 1 (global)"
```

### AC14: Disabled runtime rejected

```
Given agent_runtime_options.id=2 has enabled=False
When  POST /<project>/auto-merge/config is fired with body
      {"phase": 1, "runtime_option_id": 2}
Then  HTTP 400 with body {"error": "runtime_option 2 is disabled — pick an enabled row"}
  AND NO row is written to auto_merge_project_config
  AND NO auto_merge_config_updated event is emitted
  AND the dropdown in the Settings panel does NOT show disabled rows in the first place
      (defence in depth)
```

## Boundary Behavior

Every row becomes a mandatory test case in S13.

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty database | No events, no verdicts, no configs | Page renders empty-state; chip hidden (phase=0 default); no errors |
| Event with no `llm_calls` | `merge_auto_resolved` with `event_metadata.llm_calls` absent | Modal renders but diff viewer panes show "(no proposal recorded)"; row still verdict-able |
| File no longer on main | `proposed_content` references `tests/foo.py`; file deleted from main | Right pane of diff viewer shows "(file no longer exists on main)"; modal still renders |
| Multiple files in one event | `merge_auto_resolved.event_metadata.llm_calls` has 3 entries | Modal shows a file tabs widget; one diff viewer per file; one verdict applies to the event as a whole |
| Verdict on non-resolved event | POST verdict on a `merge_auto_resolution_attempted` event_id | HTTP 400 "verdicts only apply to merge_auto_resolved events"; no row written |
| Disabled runtime in config row | DB row has `runtime_option_id=2` (disabled after the fact) | Resolver falls back to TOML default for that project; chip annotates "(runtime disabled — falling back)"; daemon emits `auto_merge_config_invalid` |
| Phase 2 or 3 attempted in Settings | POST body `{phase: 2}` | HTTP 400 "phases 2 and 3 are reserved for future CRs"; dropdown only offers 0/1 |
| Pagination boundary | 200 events; visit `?page=5` (out of range) | Empty fragment + a "No more events" message; no 500 |
| Verdict with very long notes | 100 KB notes string | HTTP 413 "notes too long (max 8 KB)"; configurable |
| Unknown model in event metadata | `llm_calls[*].model="some-future-model"` | Token-cost rollup contributes $0; banner "Unknown model — update MODEL_PRICING" |
| `git show main:<file>` subprocess timeout | Repo is huge / disk is busy | Right pane shows "(could not read file from main: timeout)"; no 500 |
| Health probe fires while phase=0 globally + phase=1 for one project | Multi-project daemon | Only the phase=1 project's probe runs; phase=0 projects skip the probe |
| Health probe runtime is disabled mid-flight | Operator disables the row via F-00081 UI | Next probe attempt records `runtime_reachable=False, error="runtime_option disabled"`; chip → yellow |
| Daemon restart mid-probe | Probe subprocess running when daemon receives SIGTERM | Existing in-flight probe completes; daemon shuts down cleanly; no orphaned subprocess |
| Concurrent config writes | Two POST `/config` requests for the same project | Last-write-wins; both emit `auto_merge_config_updated` events; `updated_at` reflects the actual write order |

## Invariants

Each invariant maps to a test in S13.

1. **`daemon_events` remains append-only.** No code path UPDATEs or DELETEs `daemon_events` rows. Verdicts and config changes live in their own tables. Verified by grepping the diff for any `update(DaemonEvent)` / `delete(DaemonEvent)` and by a unit test that asserts the only `.commit()`-ing write to `daemon_events` is `session.add(DaemonEvent(...))`.
2. **`auto_merge_project_config` precedence is deterministic.** `resolve_project_config(project_id)` is a pure function of `(DB row, TOML)`. Same inputs → same output. Unit test runs 10× and asserts byte-equal results.
3. **The TOML continues to work standalone.** With NO `auto_merge_project_config` rows, behaviour is identical to F-00084's deployed behaviour. Integration test wipes the table and asserts the merge flow is unchanged.
4. **Disabled runtimes are unreachable from the UI.** The Settings dropdown's `<option>` list is built from `agent_runtime_options WHERE enabled=True`. Defence in depth: the POST endpoint ALSO rejects disabled rows (AC14).
5. **Phase >= 2 is rejected everywhere.** TOML + DB + POST all reject phase=2 or 3 with a clear "reserved for future CR" message. No daemon code path observes phase >= 2 in this Feature.
6. **The status chip is hidden when phase resolves to 0.** Template logic gates the chip on `phase >= 1`; no CSS-only hiding. Browser test asserts the DOM element is absent, not display:none.
7. **The health probe never blocks merge-queue progress.** The probe runs out-of-band on the poll loop, not as a step in any work item's flow. If a probe is in flight when a merge is triggered, the merge proceeds without waiting.
8. **Verdict capture is idempotent and additive.** Upsert (`ON CONFLICT (project_id, daemon_event_id) DO UPDATE`) lets the operator change their mind. `verdicted_at` reflects the latest write. No history table — operator confidence is the only audit needed here.
9. **`auto_merge_config_updated` events record before+after state.** `event_metadata = {old: {...}, new: {...}, updated_by: str, source: "dashboard"}`. This is the audit trail for who flipped what when — replaces the git-history audit you'd otherwise have if config lived in the TOML.

## Dependencies

- **Depends on**:
  - F-00084 (Phase 0/1 plumbing — `merge_auto_*` event types, `executor/auto_merge.toml`, marker parsing, `merge_queue.py` integration point)
  - F-00081 (`agent_runtime_options` table — Settings panel's runtime picker reads from it)
- **Blocks**: None. Phase 2 CR is independently planned and doesn't structurally depend on this; landing F-00085 first just makes the Phase 1 audit more productive.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/auto_merge_aggregator.py`
- `orch/daemon/auto_merge.py`
- `orch/daemon/auto_merge_health.py`
- `orch/daemon/merge_queue.py`
- `orch/daemon/main.py`
- `executor/auto_merge.toml`
- `dashboard/routers/auto_merge_ui.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/templates/pages/project/auto_merge.html`
- `dashboard/templates/fragments/auto_merge_status_chip.html`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/templates/fragments/auto_merge_event_detail.html`
- `dashboard/templates/fragments/auto_merge_rollup.html`
- `dashboard/templates/fragments/auto_merge_refuse_list.html`
- `dashboard/templates/fragments/auto_merge_settings.html`
- `dashboard/static/styles.css`
- `tests/unit/test_auto_merge_aggregator.py`
- `tests/unit/test_auto_merge_config_resolution.py`
- `tests/unit/test_auto_merge_health.py`
- `tests/unit/test_auto_merge_pricing.py`
- `tests/integration/test_auto_merge_observability.py`
- `tests/integration/test_auto_merge_control_surface.py`
- `tests/dashboard/test_auto_merge_routes.py`
- `tests/fixtures/auto_merge_observability/**`

## TDD Approach

- **Unit tests**:
  - `test_auto_merge_aggregator.py` — every public query function: empty DB returns sane defaults; seeded events return expected counts; pagination respects offset+limit; window filters reject impossible windows.
  - `test_auto_merge_config_resolution.py` — every branch of `resolve_project_config()`: DB row present (all combos of phase + runtime nullable), DB row absent, TOML present, TOML absent, disabled runtime fallback, phase=2/3 rejection.
  - `test_auto_merge_health.py` — probe subprocess success/timeout/exit-nonzero/disabled-runtime; event metadata schema; chip-state computation.
  - `test_auto_merge_pricing.py` — every model in `MODEL_PRICING` × tokens; unknown model → $0 + banner.

- **Integration tests**:
  - `test_auto_merge_observability.py` — AC1, AC2, AC3, AC4, AC5, AC7, AC8 against a testcontainer Postgres + seeded events + mocked `git show` + stubbed health probe.
  - `test_auto_merge_control_surface.py` — AC10, AC11, AC12, AC13, AC14 against the same fixture + writes through POST endpoints; verifies config-resolution chain end-to-end.
  - `test_auto_merge_routes.py` (dashboard TestClient) — every endpoint returns expected status + structure; AC6 (phase=0 hides chip), AC9 (no regressions); modal HTML asserts both left and right diff panes are present.

- **Browser tests** (S24 prompt expands):
  - V1: phase=0 fixture → no chip rendered.
  - V2: phase=1 fixture → chip rendered; status text matches resolved runtime.
  - V3: `/auto-merge` empty state.
  - V4: `/auto-merge` with seeded events.
  - V5: Click row → modal → diff viewer.
  - V6: Click [correct] inline; reload; verdict persists.
  - V7: Settings: change phase + runtime → save → chip updates.
  - V8: No regressions on adjacent project pages (queue, history, batches, code, docs).

## Notes

- **Risk: subprocess `git show main:<file>` failure modes.** Empty file, binary file, deleted file, perms error, timeout. The diff viewer wraps each fetch in a try/except → fall back to placeholder strings; never 500. Boundary table row covers this.
- **Risk: per-model pricing drift.** Provider prices change. `MODEL_PRICING` is a code constant; updating it is a one-line PR. Phase 2 may move this to a DB table; out of scope here.
- **Risk: health-probe cost.** At 5-min interval × 4 enabled projects × Sonnet pricing ≈ $5/month idle. If Sonnet is the per-project runtime, every probe spends ~50 tokens. Operator can raise `probe_interval_seconds` in TOML to reduce; or pick a cheaper model per project; or set phase=0 (chip + probe both off).
- **Risk: Settings panel concurrency.** Two operators editing simultaneously → last-write-wins; the `auto_merge_config_updated` event records both writes for audit. Acceptable for single-operator localhost deployment.
- **Future expansion hooks**: the `MODEL_PRICING` dict is a natural seam for a future "cost budget" feature (`SELECT` from `auto_merge_project_config WHERE token_budget_monthly_dollars > sum(...)`). Out of scope now.
- **Cross-reference**: After this Feature merges, update `ai-dev/active/AUTO_MERGE_RESOLUTION.md` §5b rows 1.10–1.18 to DONE and append a v1.4 changelog entry.
