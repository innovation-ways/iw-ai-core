# F-00012: Project-Level Documentation System — AI Generation (Phase 2)

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-13
**Status**: Draft

---

## Description

Adds AI-driven on-demand documentation generation to the platform. A user clicks "Generate" on any `ProjectDoc` card in the dashboard, which enqueues a `DocGenerationJob`, launches a Claude Code agent (via the existing `opencode`/`claude-code` executor) with the appropriate `iw-doc-generator` or `iw-doc-system` skill, streams real-time progress via SSE to the dashboard, and writes the result back to the database via `iw doc-update`. This phase transforms the Phase 1 read-only doc library into a live, AI-powered documentation engine.

**Depends on**: F-00011 (Phase 1 — foundation tables, DocService, `iw doc-update` CLI, Docs tab UI)

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`. Key architecture: the daemon polls for queued work; the dashboard uses SSE for real-time updates; agents write results back via CLI (`iw` commands). This phase follows the exact same pattern — `DocGenerationJob` is the work unit, the daemon picks it up, the agent generates content and calls `iw doc-update`.

## Scope

### In Scope

- "Generate" button on each doc card in the library view (triggers job creation)
- "Regenerate" button on the document detail page
- `DocGenerationJob` lifecycle management: `queued → running → completed | failed`
- Daemon extension: new poll loop for `DocGenerationJob` records in `queued` state
- Agent executor integration: launch `claude-code` agent with `iw-doc-generator` skill and the doc's `source_paths` as context
- SSE stream per job: `GET /api/project/{id}/docs/jobs/{job_id}/stream` — emits progress events while job is running
- Job status polling fallback: `GET /api/project/{id}/docs/jobs/{job_id}/status` — for non-SSE clients
- Job history panel on the doc detail page: shows recent generation jobs with status, duration, and error (if any)
- `iw doc-job-start <job_id>` CLI command: marks job as `running`, used by the launched agent process
- `iw doc-job-done <job_id> [--error TEXT]` CLI command: marks job as `completed` or `failed`
- Editorial category → skill mapping: `technical/architecture/api → iw-doc-generator`, `guide/compliance/marketing → iw-doc-system`
- Dashboard notification when generation completes (htmx-driven card refresh on the library page)

### Out of Scope

- Automatic trigger on batch merge (Phase 3)
- Diff view between generated versions (Phase 4)
- Concurrent job limits / rate limiting (Phase 3)
- Scheduled/cron-based regeneration (Phase 3)
- Multi-agent parallel generation (Phase 4)

## Architecture References

| Existing Pattern | Location | How We Extend It |
|-----------------|----------|-----------------|
| Daemon batch poll loop | `orch/daemon/` | Add new poll loop for `doc_generation_jobs` |
| Agent executor (opencode/claude-code) | `executor/` | Reuse to launch doc generation agent |
| SSE stream for daemon events | `dashboard/routers/sse.py` | Add per-job SSE endpoint |
| `iw step-done` CLI command | `orch/cli/step_commands.py` | Model `iw doc-job-done` on this |
| `DocGenerationJob` model | `orch/db/models.py` (F-00011) | Already exists — this phase activates it |
| `DocService.upsert_doc()` | `orch/doc_service.py` (F-00011) | Called by agent after generation |

## Implementation Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Daemon extension: `DocJobPoller` class; job lifecycle state machine; agent launcher integration | — |
| S02 | API | `iw doc-job-start`, `iw doc-job-done` CLI commands; SSE stream route; job status route | S03 |
| S03 | Frontend | "Generate" / "Regenerate" buttons; SSE-driven progress indicator on detail page; job history panel on detail page; library card refresh on completion | S02 |
| S04 | Tests | Integration tests: job creation → daemon pickup → completion roundtrip; SSE stream; CLI commands | — |
| S05 | CodeReview_Final | Global cross-layer review | — |
| S06–S13 | QV Gates | lint → format → typecheck → arch-check → security-sast → unit → frontend → integration | — |

## Database Changes

**Modified tables:**
- `doc_generation_jobs` — already defined in F-00011; this phase populates and manages it

**New columns (if needed):**
- `doc_generation_jobs.agent_pid` (Integer, nullable) — PID of launched agent process for monitoring
- `doc_generation_jobs.skill_used` (String, nullable) — which skill was invoked (e.g., "iw-doc-generator")
- `doc_generation_jobs.duration_seconds` (Integer, nullable) — computed on completion

**Migration**: One Alembic migration adding the three new columns.

## API Changes

**New CLI commands:**
- `iw doc-job-start <job_id> [--pid INTEGER] [--skill TEXT]` — marks job as `running`
- `iw doc-job-done <job_id> [--error TEXT]` — marks job as `completed` (or `failed` if `--error` provided), sets `duration_seconds`

**New dashboard routes:**
- `POST /api/project/{id}/docs/{doc_id}/generate` — creates `DocGenerationJob` record, returns job_id
- `GET /api/project/{id}/docs/jobs/{job_id}/stream` — SSE stream of job progress events
- `GET /api/project/{id}/docs/jobs/{job_id}/status` — JSON status poll
- `GET /api/project/{id}/docs/{doc_id}/jobs` — recent job history for a doc (htmx fragment)
- `GET /api/project/{id}/docs/{doc_id}/card` — single doc card fragment (htmx card refresh after generation completes)

## Frontend Changes

**Modified templates:**
- `dashboard/templates/fragments/docs_card.html` — add "Generate" button (POST to generate endpoint)
- `dashboard/templates/docs_detail.html` — add "Regenerate" button, SSE progress indicator, job history panel

**New templates:**
- `dashboard/templates/fragments/docs_job_status.html` — SSE-driven progress bar / spinner
- `dashboard/templates/fragments/docs_job_history.html` — list of recent jobs for a doc

## File Manifest

All files for this work item live under `ai-dev/active/F-00012/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00012_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00012_S01_Backend_prompt.md` | Prompt | S01: daemon poller, job lifecycle, migration |
| `prompts/F-00012_S02_API_prompt.md` | Prompt | S02: CLI commands, SSE stream, job routes |
| `prompts/F-00012_S03_Frontend_prompt.md` | Prompt | S03: Generate button, SSE progress, job history |
| `prompts/F-00012_S04_Tests_prompt.md` | Prompt | S04: integration tests |
| `prompts/F-00012_S05_CodeReview_Final_prompt.md` | Prompt | S05: final cross-agent review |

Reports are created during execution in `ai-dev/work/F-00012/reports/`.

## Acceptance Criteria

### AC1: Generate button triggers a job

```
Given: A ProjectDoc with source_paths populated exists
When: User clicks "Generate" on the doc card or detail page
Then: A DocGenerationJob record is created with status=queued
And: The button changes to a spinner / "Generating..." state
```

### AC2: Daemon picks up and runs the job

```
Given: A DocGenerationJob with status=queued exists
When: The daemon poll loop runs
Then: The job status changes to running
And: A claude-code agent is launched with the appropriate skill and source_paths
```

### AC3: Agent writes result and job completes

```
Given: A running DocGenerationJob
When: The agent finishes and calls iw doc-update (writing content) + iw doc-job-done
Then: The DocGenerationJob status changes to completed
And: The ProjectDoc content is updated with the generated markdown
And: A new ProjectDocVersion snapshot is created
```

### AC4: SSE stream delivers real-time progress

```
Given: A job is running
When: A client subscribes to /api/project/{id}/docs/jobs/{job_id}/stream
Then: The client receives status events as the job progresses
And: A final event is emitted when the job completes or fails
```

### AC5: Failed job surfaces error in UI

```
Given: An agent exits with error
When: The agent calls iw doc-job-done --error "Error message"
Then: Job status becomes failed
And: The error message appears in the job history panel on the detail page
And: The doc card shows a "Last generation failed" badge
```

### AC6: Regenerate creates a new job even if previous completed

```
Given: A ProjectDoc that was already generated (status=draft, has content)
When: User clicks "Regenerate"
Then: A new DocGenerationJob is created (status=queued)
And: On completion, the doc version is incremented and content updated
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Generate clicked on doc with no source_paths | `source_paths = []` | Show warning dialog: "No source paths defined — agent will have no context. Proceed?" |
| Generate clicked while job is already running | Existing job with status=running | Disable button, show "Generation in progress" tooltip |
| Agent crashes mid-run (no doc-job-done call) | Job stays in running state >10 min | Daemon stall detection marks job as failed with reason "timeout" |
| SSE client disconnects mid-stream | Client drops connection | Server cleans up SSE generator gracefully — no orphaned resources |
| Agent calls iw doc-job-done with unknown job_id | Invalid job_id | Exit code 1, error to stderr |
| No claude-code binary available | Executor misconfigured | Job marked failed with reason "agent not found", error surfaced in UI |

## Invariants

1. A `DocGenerationJob` in `running` state always has a non-null `started_at`
2. A `DocGenerationJob` in `completed` or `failed` state always has a non-null `completed_at`
3. Only one `DocGenerationJob` per doc can be in `running` state at any time (enforced by daemon before launch)
4. `iw doc-job-done` is idempotent — calling it twice on a completed job is a no-op (not an error)
5. A failed job never updates `ProjectDoc.content` (agent must not call `iw doc-update` if it fails)

## Dependencies

- **Depends on**: F-00011 (Phase 1)
- **Blocks**: F-00013 (Phase 3 — automation builds on the job execution engine built here)

## TDD Approach

- Unit tests: `DocJobPoller` state transitions; skill selection logic; job timeout detection
- Integration tests: full roundtrip via CliRunner + testcontainer; SSE stream event sequence
- Mock the agent executor in unit tests (do not launch real processes); use real DB

## Notes

**Skill selection logic** (editorial_category → skill mapping):
```
technical | architecture | api → iw-doc-generator
guide | compliance | marketing | release → iw-doc-system
```
If `editorial_category` is unset, default to `iw-doc-generator`.

**Agent launch command** (model on existing executor pattern):
```bash
claude-code --skill iw-doc-generator \
  --context "{source_paths joined as comma-separated}" \
  --output-command "iw doc-update {project_id} {doc_id} --content-file - --generated-by skill:iw-doc-generator --trigger-reason batch-merge:{job_id}" \
  --on-complete "iw doc-job-done {job_id}" \
  --on-error "iw doc-job-done {job_id} --error '{{error}}'"
```
(Adapt to actual executor pattern used in the project — read `executor/CLAUDE.md`.)

**Stall detection**: Daemon considers a job stalled if `status=running` and `started_at < now() - 10 minutes`. Stalled jobs are marked failed with `error="generation timeout after 10 minutes"`.
