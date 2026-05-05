# CR-00035: Doc-generation job observability + execution report + dispatch fix

**Type**: Change Request
**Priority**: High
**Reason**: The doc-generation subsystem is unobservable AND broken end-to-end: every `DocGenerationJob` ever created (DOC-00001..DOC-00004 plus two older UUID jobs) timed out at 15 minutes with empty `agent_output`, because the opencode dispatch path mis-routes doc jobs to `/execute` (the work-item executor). Operators have no live log, no PID liveness signal, and no execution report — the job page just shows "failed: timeout" with no information about what the agent actually did.
**Created**: 2026-05-05
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. No container/volume/network management. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **one** Alembic migration: `report JSONB NULL` column on `doc_generation_jobs`. The agent generates the file under `orch/db/migrations/versions/`. The daemon applies it as part of the merge pipeline.

## Description

Make `DocGenerationJob` execution observable from the dashboard while a job runs (live-tailed log) and after it terminates (structured execution report), and fix the dispatch bug that has prevented every doc-generation job from ever producing content. Adds a PID liveness probe, persists captured stdout into the existing `agent_output` column, adds a new `report JSONB` column populated on terminal state, and surfaces both on the job detail page. Replaces the broken `opencode run "/execute {job.id}"` invocation with a doc-job-aware slash command, and teaches the two doc skills the job lifecycle they currently know nothing about.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Specifically: `orch/CLAUDE.md` for daemon patterns and the doc-job poller's role; `dashboard/CLAUDE.md` for SSE patterns (see `routers/sse.py`, `routers/code_qa.py`); `tests/CLAUDE.md` for testcontainer rules.

## Current Behavior

Six `DocGenerationJob` rows exist in production. All six are `status=failed`, `error="generation timeout after 15 minutes"`, `agent_output_len=0`. The DOC-00004 on-disk log at `ai-dev/logs/doc_job_<uuid>.log` shows the failure mode:

```
> build · MiniMax-M2.7
→ Skill "iw-execute"
$ uv run iw item-status 727a12bd-cae3-443b-b033-924ea767b0e8 --json
  Error: Work item 727a12bd... not found in project iw-ai-core
$ ls -d ai-dev/active/727a12bd-...
  NOT_FOUND
$ uv run iw search 727a12bd
  No results
"Please verify the work item ID, or create a new design with /iw-new-feature..."
```

**Root cause**: `orch/daemon/doc_job_poller.py:_build_agent_command` (lines 222–230) builds, for opencode:
```python
cmd = f'opencode run "/execute {job.id}" --dangerously-skip-permissions'
```
`/execute` is the **work-item executor** (`commands/execute.md` → `iw-execute` skill). It calls `iw item-status <doc-job-uuid>`, gets "not found", and exits cleanly. The opencode subprocess dies in seconds. The daemon's stall guard (`_STALL_TIMEOUT_MINUTES = 15` in the poller) flips the row from `running → failed` 15 minutes later — purely on wall-clock, with no PID-alive check.

Compounding observability gaps:

1. The on-disk log file (`<repo_root>/ai-dev/logs/doc_job_<uuid>.log`) exists and is written by the poller (`doc_job_poller.py:152–162`) but is **never read by the dashboard**. The job detail template (`dashboard/templates/pages/project/job_detail.html` lines 95–132) only renders DB columns: `skill_used`, `trigger_reason`, `duration_seconds`, `lint_warnings`, and `error`.
2. The `DocGenerationJob.agent_output` column exists in the schema (`orch/db/models.py:1397`) and is referenced in `orch/jobs/aggregator.py:430`. **No code path writes to it.** It is dead.
3. There is no execution report for doc jobs (work items have one — see `orch/daemon/execution_report.py` — but doc jobs do not).
4. The 15-minute stall timeout is the only mechanism that detects a failed run. A subprocess that exits in 5 seconds keeps the row `running` for 15 minutes.
5. Neither `skills/iw-doc-generator/SKILL.md` nor `skills/iw-doc-system/SKILL.md` mentions the doc-job lifecycle (`iw doc-update`, `iw doc-job-done`). Even with the dispatch bug fixed, the skills themselves are not job-aware.

## Desired Behavior

### Live (while job is running)

- The job detail page (`/project/{pid}/jobs/doc_generation/{job_id}`) shows a **Live Log** card streaming the on-disk log via SSE. New lines appear within 1–2 seconds of being written. ANSI escapes are stripped server-side.
- The poller marks a job `failed` within ~60 seconds (one poll cycle) when `agent_pid` is no longer alive, with `error="agent process exited without calling iw doc-job-done"` — instead of waiting 15 minutes.

### After job terminates (success or fail)

- The full captured stdout is persisted into `DocGenerationJob.agent_output`, truncated to the **last 64 KB** if larger, with a marker `[truncated: N bytes elided]` at the start of the kept tail.
- A new `report JSONB` column on `doc_generation_jobs` is populated with a structured post-mortem:
  ```json
  {
    "outcome": "completed | failed_timeout | failed_process_exited | failed_agent_error",
    "duration_seconds": 47,
    "skill_used": "iw-doc-generator",
    "cli_tool": "opencode",
    "command_issued": "opencode run \"/doc-job 727a12bd...\" --dangerously-skip-permissions",
    "log_size_bytes": 4443,
    "log_line_count": 98,
    "tool_calls": [
      {"tool": "iw item-status", "exit_code": 1},
      {"tool": "iw search", "exit_code": 0}
    ],
    "doc_update_invocations": 0,
    "lint_warning_count": 0,
    "diagnosis": "Skill never called `iw doc-update` — no content was generated. Likely cause: dispatcher invoked /execute (work-item path) instead of doc-generation skill."
  }
  ```
- The job detail page renders the report as an **Execution Report** card under the existing Parameters card.
- A "Download raw log" link on the page returns the full uncut log file as `text/plain`.

### Dispatch fix (so jobs actually do work)

- `_build_agent_command` (opencode branch) issues `opencode run "/doc-job {job.id}" --dangerously-skip-permissions`.
- A new `commands/doc-job.md` slash command targets the right doc-generation skill (`iw-doc-generator` or `iw-doc-system` depending on the editorial category — the same selection logic as `_select_skill`).
- A **new read-only CLI command** `iw doc-job-status <job-id> [--json]` (in `orch/cli/doc_commands.py`, registered in `orch/cli/main.py`) returns the job's full context — project_id, doc_id, doc title, editorial category, `section_guides_snapshot`, `guide_snapshot`, status — so the agent can read what it needs to produce. Mirrors the shape/style of `iw item-status --json`. Read-only; never mutates state.
- `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md` document the lifecycle: read context via `iw doc-job-status <job-id> --json`; produce content via `iw doc-update <doc-id> --content-file - --generated-by skill:<skill> --trigger-reason job:<job-id>` (project auto-resolved from `.iw-orch.json` in `project.repo_root`); close via `iw doc-job-done <job-id>` on success or `iw doc-job-done <job-id> --error '<msg>'` on failure.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/db/models.py` `DocGenerationJob` | No `report` column | Adds `report: JSONB NULL` |
| Alembic migrations | N/A | New revision adds nullable JSONB column |
| `orch/daemon/doc_job_poller.py` `DocJobPoller.poll` | Wall-clock stall only | Adds PID liveness probe (`os.kill(pid, 0)`); marks job failed in ~60s when subprocess is dead |
| `orch/daemon/doc_job_poller.py` `_build_agent_command` | opencode → `/execute {job.id}` (broken) | opencode → `/doc-job {job.id}` |
| `orch/cli/doc_commands.py` | `doc-update`, `doc-job-start`, `doc-job-done`, `docs-check-stale`, `docs-export` | Adds new read-only `doc-job-status <job-id> [--json]` returning the job + ProjectDoc context the agent needs |
| `orch/cli/main.py` | Registers existing doc commands | Registers `doc-job-status` |
| `orch/doc_service.py` `complete_doc_job` | Sets status / error / lint_warnings only | Also: reads on-disk log, truncates to last 64 KB, writes to `agent_output`; computes and writes `report` JSONB |
| `orch/doc_report.py` | Does not exist | New module: `read_log_tail`, `parse_tool_calls`, `count_doc_update_invocations`, `build_execution_report` |
| `orch/utils/log_capture.py` | Existing log helpers | Adds (or factors out) `strip_ansi(text: str) -> str` reused by `orch/doc_report.py` |
| `dashboard/routers/docs.py` (or `jobs_ui.py`) | No log endpoints | Adds `GET /project/{pid}/jobs/doc_generation/{job_id}/log/tail` (initial N lines), `GET .../log/stream` (SSE), `GET .../log/raw` (text/plain download) |
| `dashboard/routers/jobs_ui.py` job-detail handler | Renders Parameters + Error cards | Resolves the log-file path and passes `log_file_exists: bool` into the template context for the "Download raw log" link |
| `dashboard/templates/pages/project/job_detail.html` | Only Parameters + Error cards under `doc_generation` branch | Adds Live Log card (SSE) when `status == 'running'`; adds Execution Report card when `report` is present; adds Captured log `<details>` fallback for terminal jobs |
| `commands/doc-job.md` | Does not exist | New slash command — invokes correct doc-gen skill with job UUID context |
| `skills/iw-doc-generator/SKILL.md` | No mention of jobs | Adds "When invoked via `/doc-job`" section documenting the lifecycle calls (`iw doc-job-status`, `iw doc-update`, `iw doc-job-done`) |
| `skills/iw-doc-system/SKILL.md` | No mention of jobs | Same lifecycle section (character-for-character identical) |
| `orch/jobs/aggregator.py` `_build_doc_generation_raw` | Already exposes `agent_output` | Add `report` to the raw dict |

### Breaking Changes

- **None for callers.** The DB migration is purely additive (nullable column). The `agent_output` column already existed but was unused — populating it does not break anything that reads it.
- **Behavioural change for the dispatch path**: `_build_agent_command` (opencode) now calls a new slash command. The previous invocation was 100% broken (zero successful runs in production), so this is restoring a feature, not changing one in flight. Claude-code branch is unchanged.

### Data Migration

- **Schema migration only**: add `report JSONB NULL` to `doc_generation_jobs`. Existing rows have `report = NULL` after upgrade.
- **Reversible**: downgrade drops the column.
- **No data backfill** — existing failed jobs will not retroactively get a report (their on-disk logs are still readable manually if needed).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration: `report JSONB NULL` on `doc_generation_jobs`; ORM model field on `DocGenerationJob` | — |
| S02 | code-review-impl | Review S01 (migration safety, naming, downgrade correctness, ORM mapping) | — |
| S03 | backend-impl | **Dispatch unit.** (a) Fix `_build_agent_command` opencode branch → `/doc-job {job.id}`. (b) New `commands/doc-job.md`. (c) New read-only CLI command `iw doc-job-status <job-id> [--json]` (`orch/cli/doc_commands.py` + register in `orch/cli/main.py`) returning project_id, doc_id, doc title, editorial_category, `section_guides_snapshot`, `guide_snapshot`, status. (d) Add identical "Job lifecycle (when invoked via `/doc-job`)" section to both `skills/iw-doc-generator/SKILL.md` and `skills/iw-doc-system/SKILL.md` documenting `iw doc-job-status` → `iw doc-update` → `iw doc-job-done`. No cross-step plumbing of the rendered command string — S05 reconstructs it at report-build time from `job.skill_used` + `project.config["cli_tool"]` + `job.id` (dispatch is deterministic). | — |
| S04 | code-review-impl | Review S03 (dispatch unit) | — |
| S05 | backend-impl | **Observability unit.** (a) PID liveness probe in `DocJobPoller.poll` (runs before stall sweep; `os.kill(pid, 0)`; ~60s detection; race protection for jobs <10s old). (b) New module `orch/doc_report.py` with `read_log_tail`, `parse_tool_calls`, `count_doc_update_invocations`, `build_execution_report`. Factor `strip_ansi` into `orch/utils/log_capture.py`. (c) `complete_doc_job` accepts one new kwarg `worktree_path` (keyword-only); reconstructs `cli_tool` and `command_issued` internally from the loaded `Project` row; reads on-disk log; writes truncated tail to `agent_output`; writes full report to `report`. Both stall path and `iw doc-job-done` path populate. Idempotent. (d) `aggregator._build_doc_generation_raw` exposes `report`. | — |
| S06 | code-review-impl | Review S05 (observability unit) | — |
| S07 | api-impl | New endpoints in `dashboard/routers/docs.py` (or `jobs_ui.py`): `/log/tail` (returns last N=200 stripped lines), `/log/stream` (SSE — opens file, seeks to end, yields new lines until job terminal or client disconnect, with periodic keepalive), `/log/raw` (returns full file as `text/plain` with `Content-Disposition: attachment`). All endpoints resolve the file path from `Project.repo_root` + `ai-dev/logs/doc_job_<job.id>.log`; handle file-not-found gracefully (404 with explanatory body). Modify `dashboard/routers/jobs_ui.py` job-detail handler to pass `log_file_exists: bool` into the template context. | — |
| S08 | code-review-impl | Review S07 (route registration, file path resolution, SSE shape, error handling, no path traversal) | — |
| S09 | frontend-impl | Update `dashboard/templates/pages/project/job_detail.html`: under the existing `job.job_type.value == 'doc_generation'` branch, add (a) Live Log card with `<div hx-ext="sse" sse-connect="...">` and a `<pre>` element when `job.status == 'running'`; (b) Execution Report card when `raw.get('report')` is present; (c) Captured log `<details>` fallback for terminal jobs; (d) "Download raw log" link to `/log/raw` whenever the log file exists. Ensure ANSI is rendered as plain text. | — |
| S10 | code-review-impl | Review S09 (template correctness, htmx wiring, fallback when SSE unavailable, accessibility) | — |
| S11 | tests-impl | Unit tests: PID liveness probe (mock `os.kill`); `orch/doc_report.py` helpers; `complete_doc_job` truncation + report; new `iw doc-job-status` CLI shape and joins. Integration tests: `/log/tail`, `/log/stream`, `/log/raw`. Replay the captured DOC-00004 log as a fixture. | — |
| S12 | code-review-impl | Review S11 (coverage, falsifiability — would tests fail on main?, no flakiness, fixtures clean up, no live-DB / mock-DB violations from `tests/CLAUDE.md`) | — |
| S13 | code-review-final-impl | Cross-step review: integration coherence S01 → S03 (dispatch + new CLI) → S05 (observability) → S07 (endpoints) → S09 (templates) → S11 (tests) | — |
| S14 | qv-gate | `make lint` | — |
| S15 | qv-gate | `make format-check` | — |
| S16 | qv-gate | `make typecheck` | — |
| S17 | qv-gate | `make arch-check` | — |
| S18 | qv-gate | `make security-sast` | — |
| S19 | qv-gate | `make test-unit` | — |
| S20 | qv-gate | `make allure-integration` (integration tests, 900s) | — |
| S21 | qv-browser | Browser verification of execution-report card rendering, captured-log fallback, and download-raw-log link on `/project/{pid}/jobs/doc_generation/<id>` in the isolated worktree stack. (Live-log streaming is excluded from browser verification — the daemon's PID liveness probe runs in a different PID namespace from the app container, making a deterministic running-job fixture unreliable. Live-log behaviour is covered by S11 integration tests instead.) | — |
| S22 | self-assess-impl | iw-item-analyze self-assessment | — |

`code-review-fix-impl` and `code-review-fix-final-impl` steps are NOT pre-declared — the orchestrator inserts them only when the corresponding review step produces findings.

### Database Changes

- **New tables**: None
- **Modified tables**: `doc_generation_jobs` — add `report JSONB NULL` (no default, no index — read-only at this stage; querying patterns can add a GIN index in a future CR if needed)
- **Migration notes**: Single Alembic revision; downgrade drops the column; no data backfill.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/tail` → JSON `{lines: [str, ...], truncated_from_bytes: int|null, file_size_bytes: int}` (last 200 stripped lines by default; `?n=` query param caps the count, hard maximum 1000)
  - `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/stream` → `text/event-stream`. SSE events: `data:<one log line>\n\n` per line; sentinel `event:status\ndata:terminal\n\n` when the job reaches a terminal state, after which the stream closes. Heartbeat every 15s: `event:ping\ndata:\n\n`.
  - `GET /project/{project_id}/jobs/doc_generation/{job_id}/log/raw` → `text/plain; charset=utf-8` with `Content-Disposition: attachment; filename="doc_job_<id>.log"`. ANSI **not** stripped on the raw download (operators may want the original).
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: Live Log card (htmx SSE consumer) and Execution Report card on the job detail template — both as inline blocks under the existing `doc_generation` branch in `job_detail.html`.
- **Modified components**: `job_detail.html` (additive)
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00035/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00035_CR_Design.md` | Design | This document |
| `CR-00035_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00035_S01_Database_prompt.md` | Prompt | S01 — Alembic migration + ORM field |
| `prompts/CR-00035_S02_CodeReview_Database_prompt.md` | Prompt | S02 — review of S01 |
| `prompts/CR-00035_S03_Backend_prompt.md` | Prompt | S03 — dispatch unit (dispatch fix + slash command + new `iw doc-job-status` CLI + skills) |
| `prompts/CR-00035_S04_CodeReview_Backend_prompt.md` | Prompt | S04 — review of S03 |
| `prompts/CR-00035_S05_Backend_prompt.md` | Prompt | S05 — observability unit (PID probe + doc_report module + complete_doc_job + aggregator) |
| `prompts/CR-00035_S06_CodeReview_Backend_prompt.md` | Prompt | S06 — review of S05 |
| `prompts/CR-00035_S07_Api_prompt.md` | Prompt | S07 — log-tail/stream/raw endpoints |
| `prompts/CR-00035_S08_CodeReview_Api_prompt.md` | Prompt | S08 — review of S07 |
| `prompts/CR-00035_S09_Frontend_prompt.md` | Prompt | S09 — job_detail template cards |
| `prompts/CR-00035_S10_CodeReview_Frontend_prompt.md` | Prompt | S10 — review of S09 |
| `prompts/CR-00035_S11_Tests_prompt.md` | Prompt | S11 — unit + integration tests |
| `prompts/CR-00035_S12_CodeReview_Tests_prompt.md` | Prompt | S12 — review of S11 |
| `prompts/CR-00035_S13_CodeReview_Final_prompt.md` | Prompt | S13 — cross-step final review |
| `prompts/CR-00035_S21_BrowserVerification_prompt.md` | Prompt | S21 — qv-browser end-to-end check |
| `prompts/CR-00035_S22_SelfAssess_prompt.md` | Prompt | S22 — self-assessment |

QV gate steps S14..S20 are declarative in the manifest (gate command only) and need no prompt files.

Reports are created during execution under `ai-dev/work/CR-00035/reports/` (orchestrator-managed).

## Acceptance Criteria

### AC1: Live log streams on the job detail page

```
Given a queued DocGenerationJob exists for the iw-ai-core project
And the daemon poll cycle has launched it (status=running, agent_pid set, log file exists)
When an operator opens /project/iw-ai-core/jobs/doc_generation/<id> in the browser
Then a "Live Log" card is visible
And new lines written to <repo_root>/ai-dev/logs/doc_job_<uuid>.log appear in the card within 2 seconds of being written
And ANSI escape sequences (e.g. \x1b[0m) are not visible to the operator
```

### AC2: PID liveness probe shortens "ghost-running" detection

```
Given a DocGenerationJob is running with agent_pid=P
And the OS process P has exited (no longer in the kernel process table)
When the next DocJobPoller.poll() cycle runs
Then the job is marked status=failed with error mentioning "agent process exited"
And the time from process-exit to status=failed is at most one poll interval (~60s), not 15 minutes
```

### AC3: agent_output is persisted on terminal state

```
Given a DocGenerationJob has reached a terminal state (completed or failed)
And the on-disk log file contains N bytes of stdout
When the job row is read from the database
Then DocGenerationJob.agent_output is non-null
And contains either the full log if N <= 64 KB, or the last 64 KB prefixed with a "[truncated: <N-65536> bytes elided]" marker
```

### AC4: Execution report is populated on terminal state

```
Given a DocGenerationJob has reached a terminal state
When the job row is read from the database
Then DocGenerationJob.report is a JSONB object
And the object contains keys: outcome, duration_seconds, skill_used, cli_tool, command_issued, log_size_bytes, log_line_count, tool_calls, doc_update_invocations, lint_warning_count, diagnosis
And outcome is one of: completed, failed_timeout, failed_process_exited, failed_agent_error
```

### AC5: Execution Report card renders on the job detail page

```
Given a DocGenerationJob has report populated
When an operator opens /project/<pid>/jobs/doc_generation/<id>
Then an "Execution Report" card is visible
And it shows: outcome pill, duration, command issued, tool-call summary table, doc_update invocations count, diagnosis line
And a "Download raw log" link is present when the on-disk log exists, linking to the /log/raw endpoint
```

### AC6: Doc-job dispatch invokes a doc-generation skill, not the work-item executor

```
Given _build_agent_command is invoked with cli_tool=opencode for a DocGenerationJob J
When the resulting command string is inspected
Then the slash command is "/doc-job <J.id>", not "/execute <J.id>"
And commands/doc-job.md exists and explicitly references iw-doc-generator and iw-doc-system as the target skills (selected by editorial category)
```

### AC7: Doc skills document the job lifecycle

```
Given the master skill files at skills/iw-doc-generator/SKILL.md and skills/iw-doc-system/SKILL.md
When an agent reads them
Then both files describe how to: (1) read job context via `iw doc-job-status <job-id> --json`, (2) write generated content via `iw doc-update <doc-id> --content-file - --generated-by skill:<skill> --trigger-reason job:<job-id>` (project auto-resolved from the worktree's `.iw-orch.json`), (3) close the job via `iw doc-job-done <job-id>` on success or `iw doc-job-done <job-id> --error '<msg>'` on failure
And the lifecycle section is character-for-character identical between the two SKILL.md files
```

### AC9: New `iw doc-job-status` CLI exists and returns job context

```
Given a DocGenerationJob row exists for project <pid> with doc_id <did>
When an operator runs `uv run iw doc-job-status <job-id> --json`
Then exit code is 0
And stdout is JSON containing keys: id, public_id, project_id, doc_id, doc_title, editorial_category, status, section_guides_snapshot, guide_snapshot
And the command does not mutate any DB row (read-only)
And running it for a non-existent job-id exits non-zero with a clear error message
```

### AC8: New raw-log endpoints behave correctly

```
Given a DocGenerationJob with agent_pid still alive and an on-disk log
When a client GETs /log/tail
Then the response is JSON with the last 200 ANSI-stripped lines and the file size

When a client GETs /log/stream
Then the response is text/event-stream
And new lines arrive within 2 seconds of file write
And on terminal status, an event:status data:terminal frame is sent and the stream closes

When a client GETs /log/raw
Then the response is text/plain with Content-Disposition: attachment
And the body contains the unmodified original log content
```

## Rollback Plan

- **Database**: The Alembic migration adds a single nullable JSONB column. Downgrade drops it. No data loss on roll-forward (column is empty for existing rows). On rollback, any `report` data populated post-deploy is discarded — acceptable since the column is purely advisory.
- **Code**: Revert the merge commit. The dispatch fix is part of the same commit; reverting restores the (broken) `/execute {job.id}` behaviour. Since that path was 100% broken before this CR, rollback effectively turns doc generation back off — no in-flight successful runs to lose.
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None
- **Blocks**: Any future work that wants doc generation to actually produce documents (it has never worked in production).

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/doc_job_poller.py`
- `orch/doc_service.py`
- `orch/doc_report.py`
- `orch/utils/log_capture.py`
- `orch/cli/doc_commands.py`
- `orch/cli/main.py`
- `orch/jobs/aggregator.py`
- `dashboard/routers/docs.py`
- `dashboard/routers/jobs_ui.py`
- `dashboard/templates/pages/project/job_detail.html`
- `dashboard/templates/base.html`
- `dashboard/static/styles.css`
- `commands/doc-job.md`
- `skills/iw-doc-generator/SKILL.md`
- `skills/iw-doc-system/SKILL.md`
- `tests/unit/test_doc_job_poller_pid_liveness.py`
- `tests/unit/test_doc_report.py`
- `tests/unit/test_doc_service_complete_writes_output.py`
- `tests/unit/test_doc_job_status_cli.py`
- `tests/integration/test_doc_job_log_endpoints.py`
- `tests/fixtures/doc_jobs/**`
- `ai-dev/active/CR-00035/**`
- `ai-dev/archive/CR-00035/**`

## TDD Approach

- **Unit tests**:
  - `tests/unit/test_doc_job_poller_pid_liveness.py` — mocks `os.kill`; asserts dead PID flips status to failed in one poll cycle with the new error message; asserts living PID does not.
  - `tests/unit/test_doc_report.py` — feeds fixture log files (success, timeout, process-exited, the actual replayed DOC-00004 log) to the report builder; asserts every field in the AC4 schema; asserts ANSI is stripped; asserts diagnosis heuristics fire correctly.
  - `tests/unit/test_doc_service_complete_writes_output.py` — calls `complete_doc_job` with a fixture log file present; asserts `agent_output` truncation rule (full when ≤64 KB, last 64 KB + marker when larger); asserts `report` JSONB is populated.
  - `tests/unit/test_doc_job_status_cli.py` — invokes the new CLI via Click's `CliRunner`; asserts JSON shape (keys per AC9), join with `ProjectDoc` returns title/editorial_category, missing job-id exits non-zero, command never mutates the row.
- **Integration tests** (require testcontainer per `tests/CLAUDE.md`):
  - `tests/integration/test_doc_job_log_endpoints.py` — `/log/tail` returns expected lines and shape; `/log/stream` SSE delivers lines and closes on terminal status; `/log/raw` returns the unmodified original; 404 path when file missing; resolution via `Project.repo_root`.
- **Updated tests**: any existing `test_doc_service*` that asserted `complete_doc_job` produces *only* lint_warnings without `agent_output`/`report` — update to match the new behaviour. Search via `grep -r "complete_doc_job" tests/`.
- **Tests fixtures**: `tests/fixtures/doc_jobs/doc_00004_replay.log` (the actual captured DOC-00004 log, ANSI escapes intact); `tests/fixtures/doc_jobs/successful_run.log` (synthetic — includes `iw doc-update` and `iw doc-job-done` calls); `tests/fixtures/doc_jobs/process_exited_early.log` (synthetic — short, no doc-job-done call).

## Notes

- **DocService method signature**: `complete_doc_job` currently takes `(self, job_id, error=None)`. To compute `agent_output` and `report` it needs access to the project's `repo_root` to find the log file. Two options: (a) pass `worktree_path` as an optional kwarg from the poller (simple), (b) look up the project inside the method (an extra query per call). Prefer (a) — the poller already holds the project — falling back to (b) only when called from a different code path. Document the choice in the S05 prompt (observability unit).
- **ANSI strip helper**: there is no central helper today; `orch/daemon/execution_report.py` strips ANSI for work-item reports inline. Factor a tiny utility into `orch/utils/log_capture.py` (which already exists) so both work-item reports and doc reports can share it.
- **Aggregator**: `JobsAggregator._build_doc_generation_raw` already includes `agent_output`. We only need to add `report`. Forgetting this would leave the JSONB invisible from the dashboard side — easy miss, called out in S05 deliverable (d) and S06 review.
- **SSE backpressure**: with rapidly-written logs, the SSE generator should `os.read` a chunk and split on newlines rather than `readline` in a busy-loop. Use `selectors` or a simple `time.sleep(0.25)` between empty reads. Cap line length at 8 KB before sending.
- **Tail caveat**: the on-disk log file may be deleted by housekeeping (none today, but not impossible). The endpoints must treat missing files as 404 with a clear body, not 500.
- **`/doc-job` slash command file format**: see `commands/execute.md` for the established pattern (frontmatter `description` + `agent` keys, then a short prose body). The new file follows the same shape but routes to the doc-gen skills.
- **Skill update wording**: keep both skill SKILL.md updates additive (new section near the bottom titled "Job lifecycle (when invoked via /doc-job)") so existing manual usage of these skills outside the job system continues to work unchanged.
- **`iw doc-job-status` is the chosen context channel**: rejected alternatives — passing context inline in the slash command (impractical for multi-line guides) and writing a JSON sidecar file (adds another lifecycle artefact to manage). The CLI command reuses the same DB session/aggregator pattern as existing `iw item-status` and `iw doc-job-start/done`, and is small (~15-25 LOC). New CLI is **read-only** — it never mutates the row. Failures (job not found) exit non-zero so skills can detect missing context and call `iw doc-job-done <job-id> --error 'context not found'` without proceeding.
- **Browser verification scope (S21)**: V1 (live-log streaming) is intentionally excluded. The PID liveness probe relies on `os.kill(pid, 0)` from the daemon's PID namespace; an `agent_pid` belonging to a process running inside a different container (the per-worktree app container) would be reported as dead by the daemon, making a deterministic running-job fixture brittle. Live-log behaviour is fully exercised by S11 integration tests (`/log/stream` SSE), which is the right layer for that check.
- **Step splitting**: S03 (dispatch) and S05 (observability) are deliberately separate so a fix-cycle on one does not roll back the other. The two units are decoupled at the file level — there is no cross-step plumbing. S05 reconstructs the `command_issued` string at report-build time from `job.skill_used` + `project.config["cli_tool"]` + `job.id`, since the opencode dispatch shape is fixed (`opencode run "/doc-job <id>" --dangerously-skip-permissions`). This avoids both an in-memory poller stash (would lose info on the agent-driven `iw doc-job-done` path) and a schema column dedicated to the rendered string. If S03 ships first and S05 lags, jobs dispatch correctly but produce empty `agent_output` / null `report` — observable but not catastrophic. The merge ordering through batch_manager will keep them together in practice.
