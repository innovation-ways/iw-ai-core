# F-00058: OSS compliance dashboard view + status pill

**Type**: Feature
**Priority**: High
**Created**: 2026-04-21
**Status**: Draft

---

## Description

Adds a per-project OSS view in the dashboard (sibling to Code / Tests / Quality / Documentation), an "OSS Status" frame underneath the Git Status frame on every project page, and the UI actions to enable OSS, install missing Tier-1 tools, trigger Scan/Prepare/Publish, and surface results grouped by domain with per-tool-run cards. Every destructive server-side action (Prepare, Publish) runs inside a throwaway git worktree clone, never touches the developer's working tree, and is mirrored by a collapsible "run it yourself" CLI block. All scans run async and stream progress to the browser via SSE.

## Project Context

Read the project's `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, htmx patterns, routing, testcontainer rules, and playwright-cli conventions.

## Scope

### In Scope

- New DB table `project_oss_job` for async job tracking (queue + status + stdout tail).
- New dashboard service `dashboard/services/oss_service.py`: enqueue jobs, spawn `iw oss` subprocesses in throwaway worktrees, stream job status to DB, freshness helper, Tier-1 probe wrapper.
- New HTTP router `dashboard/routers/oss.py` with 7 endpoints (page, status fragment, enable, scan, prepare, publish, tools, SSE stream).
- New templates under `dashboard/templates/pages/project/oss.html` + fragments (pill, domain cards, tool cards, install modal, CLI block, scan progress).
- OSS Status frame added under Git Status on every project page (its own frame, not inline).
- "OSS" tab in the project sidebar/tab row visible only when `project.oss_enabled=true`.
- Integration tests (API + Jinja reproduction) + browser verification on the isolated E2E stack.

### Out of Scope

- Generalizing the status-frame pattern to Quality or Tests (separate future work).
- Machine-level tool installation via privileged operations (`sudo apt`, etc.) — F-00057 installer fallbacks stay the same; when sudo is needed, the UI surfaces the command for manual execution.
- Modifying the developer's checked-out working tree from the server (Prepare/Publish always run in a throwaway clone).
- Auto-running scans on git push / schedule (out of scope for V1 — manual trigger only).
- Cross-project aggregation / "all projects" OSS health view.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `project_oss_job` table + ORM model (id, project_id FK, kind [scan/prepare/publish], status [queued/running/complete/error], stdout_tail, started/completed_at, exit_code) | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | `dashboard/services/oss_service.py`: job enqueue/execute (subprocess of `uv run iw oss …`), throwaway worktree provisioning via `git worktree add`, SSE message emission helpers, Tier-1 probe wrapper (delegates to `orch.oss.tool_probe`), freshness helper | — |
| S04 | code-review-impl | Review S03 (subprocess hygiene, worktree cleanup, SSE backpressure, error paths) | — |
| S05 | api-impl | `dashboard/routers/oss.py`: `GET /projects/{id}/oss` (HTML page), `GET /projects/{id}/oss/status` (htmx fragment), `POST /projects/{id}/oss/enable` / `scan` / `prepare` / `publish`, `GET /projects/{id}/oss/tools`, `GET /projects/{id}/oss/stream/{job_id}` (SSE) | S06 |
| S06 | frontend-impl | Templates + htmx + CSS: `pages/project/oss.html`, fragments (`oss_status_pill.html`, `oss_status_frame.html`, `oss_domain_card.html`, `oss_tool_run_card.html`, `oss_install_modal.html`, `oss_cli_block.html`, `oss_scan_progress.html`). Add "OSS Status" frame underneath the Git Status frame in the project header; show "OSS" tab when `oss_enabled=true` | S05 |
| S07 | code-review-impl | Joint review of S05 + S06 (API↔template contract, htmx headers, form action alignment) | — |
| S08 | tests-impl | Integration tests: API routes, htmx fragment renders, SSE job lifecycle, Jinja reproduction tests for pill color mapping + domain-card empty-state + install-modal | — |
| S09 | code-review-impl | Review S08 | — |
| S10 | code-review-final-impl | Global cross-layer review: DB → service → API → template coherence; AC coverage; no regressions to sibling views | — |
| S11 | qv-gate | `make lint` | — |
| S12 | qv-gate | `uv run ruff format --check .` | — |
| S13 | qv-gate | `uv run mypy orch/ dashboard/` | — |
| S14 | qv-gate | `make test-unit` | — |
| S15 | qv-gate | `make test-integration` | — |
| S16 | qv-browser | Browser verification on the isolated E2E stack — pill rendering, Install modal flow, Scan + SSE, results tree, Prepare/Publish flow, no regressions | — |

### Database Changes

- **New tables**: `project_oss_job`.
- **Modified tables**: none in this Feature (F-00057 adds `project.oss_enabled`).
- **Migration notes**: Alembic migration, downgradeable. Uses PG enum `project_oss_job_kind` (`scan`/`prepare`/`publish`) and `project_oss_job_status` (`queued`/`running`/`complete`/`error`/`cancelled`).

`project_oss_job` columns:
- `id BIGSERIAL PRIMARY KEY`
- `project_id` FK → `project.id`, NOT NULL, `ON DELETE CASCADE`
- `kind` ENUM NOT NULL
- `status` ENUM NOT NULL DEFAULT `queued`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `started_at TIMESTAMPTZ NULL`
- `completed_at TIMESTAMPTZ NULL`
- `exit_code INT NULL`
- `worktree_path TEXT NULL` (temp path used for prepare/publish)
- `scan_id BIGINT NULL` (FK → `oss_scan.id` when kind=scan)
- `stdout_tail TEXT NULL` (last 16KB of combined stdout/stderr)
- `error_message TEXT NULL`
- Indexes: `(project_id, created_at DESC)`, `(status)` for pending-job queries.

### API Changes

All under `/projects/{project_id}/oss`:

- `GET ` → HTML page (renders `pages/project/oss.html`)
- `GET /status` → htmx fragment (pill + summary) — polled or pushed via SSE
- `GET /tools` → htmx fragment / JSON — Tier-1 tool availability
- `POST /enable` → create `.iw/oss-publish.toml`, set `project.oss_enabled=true`
- `POST /disable` → unset flag (keep `.iw/` on disk)
- `POST /scan` → enqueue scan job, return job_id + SSE stream URL
- `POST /prepare` → enqueue make_oss job in a throwaway worktree
- `POST /publish` → enqueue publish job (emits scripts, does NOT flip public)
- `GET /stream/{job_id}` → SSE: `status`, `progress` (stdout line), `complete` events

Also modify the existing project header template to include the new OSS Status frame slot underneath the Git Status frame.

### Frontend Changes

- **New templates**:
  - `pages/project/oss.html` — top-level OSS view page
  - `fragments/oss_status_pill.html` — the 4-state pill (green/yellow/red/gray) + stale flag
  - `fragments/oss_status_frame.html` — the frame rendered under Git Status on all project pages
  - `fragments/oss_domain_card.html` — one card per domain (secrets, license, …)
  - `fragments/oss_tool_run_card.html` — one card per tool invocation with version, runtime, verdict
  - `fragments/oss_install_modal.html` — Tier-1 tool availability + Install-now button + per-tool commands
  - `fragments/oss_cli_block.html` — collapsible "run it yourself" block, reusable (pass in CLI command text)
  - `fragments/oss_scan_progress.html` — SSE-driven progress row
- **Modified templates**:
  - `templates/pages/project/_header.html` (or wherever Git Status frame lives): add OSS Status frame underneath
  - Project sidebar/tab partial: add "OSS" tab gated on `project.oss_enabled`

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00058/F-00058_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00058/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00058/evidences/pre/F-00058-project-page-before.png` | Evidence | Project page pre-state (captured 2026-04-21) |
| `ai-dev/active/F-00058/prompts/F-00058_S01_Database_prompt.md` | Prompt | S01 |
| `ai-dev/active/F-00058/prompts/F-00058_S02_CodeReview_prompt.md` | Prompt | S02 |
| `ai-dev/active/F-00058/prompts/F-00058_S03_Backend_prompt.md` | Prompt | S03 |
| `ai-dev/active/F-00058/prompts/F-00058_S04_CodeReview_prompt.md` | Prompt | S04 |
| `ai-dev/active/F-00058/prompts/F-00058_S05_API_prompt.md` | Prompt | S05 |
| `ai-dev/active/F-00058/prompts/F-00058_S06_Frontend_prompt.md` | Prompt | S06 |
| `ai-dev/active/F-00058/prompts/F-00058_S07_CodeReview_prompt.md` | Prompt | S07 |
| `ai-dev/active/F-00058/prompts/F-00058_S08_Tests_prompt.md` | Prompt | S08 |
| `ai-dev/active/F-00058/prompts/F-00058_S09_CodeReview_prompt.md` | Prompt | S09 |
| `ai-dev/active/F-00058/prompts/F-00058_S10_CodeReview_Final_prompt.md` | Prompt | S10 |
| `ai-dev/active/F-00058/prompts/F-00058_S16_BrowserVerification_prompt.md` | Prompt | S16 |

**Source files created / modified**:

- `orch/db/migrations/versions/{hash}_add_project_oss_job.py` (new)
- `orch/db/models.py` (modified — add `ProjectOssJob`)
- `dashboard/services/__init__.py` (may be new)
- `dashboard/services/oss_service.py` (new)
- `dashboard/routers/oss.py` (new)
- `dashboard/app.py` (modified — register router)
- `dashboard/templates/pages/project/oss.html` (new)
- `dashboard/templates/fragments/oss_status_pill.html` (new)
- `dashboard/templates/fragments/oss_status_frame.html` (new)
- `dashboard/templates/fragments/oss_domain_card.html` (new)
- `dashboard/templates/fragments/oss_tool_run_card.html` (new)
- `dashboard/templates/fragments/oss_install_modal.html` (new)
- `dashboard/templates/fragments/oss_cli_block.html` (new)
- `dashboard/templates/fragments/oss_scan_progress.html` (new)
- `dashboard/templates/pages/project/_header.html` or equivalent (modified — add OSS Status frame slot)
- `dashboard/templates/fragments/project_tabs.html` or equivalent (modified — conditional "OSS" tab)
- `dashboard/static/` (modified — OSS-specific CSS additions if needed, no new JS framework)
- `tests/integration/test_oss_dashboard_routes.py` (new)
- `tests/integration/test_oss_dashboard_templates.py` (new)
- `tests/integration/test_oss_dashboard_sse.py` (new)

Reports are created during execution in `ai-dev/active/F-00058/reports/`.

## Acceptance Criteria

### AC1: OSS Status frame on every project page

```
Given   a project with oss_enabled=true and a recent scan with pill_color='yellow'
When    I open any project page (Code, Tests, Quality, Documentation, OSS)
Then    an "OSS Status" frame appears immediately underneath the Git Status frame
And     the frame contains the 🟡 yellow pill with summary text "3 warnings, 0 blockers"
And     clicking the pill navigates to /projects/{id}/oss
```

### AC2: Install OSS flow (disabled → enabled)

```
Given   a project with oss_enabled=false
When    I click "Install OSS" in the OSS Status frame
Then    a modal opens listing every Tier-1 tool with status (installed | missing)
And     missing tools each show a copy-able install command
And     a single "Install now" button runs the installer on the server
And     after install (or skip), clicking "Enable OSS" flips oss_enabled=true,
        writes .iw/oss-publish.toml, and dismisses the modal
And     the OSS Status frame becomes a gray pill "not yet scanned"
And     the "OSS" tab appears in the project tab row
```

### AC3: Scan with SSE progress

```
Given   a project with oss_enabled=true on the OSS view
When    I click "Scan"
Then    a POST /scan creates a project_oss_job row with status='queued'
And     the UI shows a progress row that subscribes to GET /stream/{job_id} via SSE
And     streamed stdout lines render line-by-line
And     on completion, the oss_scan row is inserted (via F-00057 pipeline),
        the page's findings tree refreshes without a full reload,
        and the pill transitions to green/yellow/red based on the scan verdict
```

### AC4: Prepare / Publish with throwaway worktree + CLI block

```
Given   an enabled project with no MUST-level blockers (prepare) or clean pre-publish (publish)
When    I click "Prepare for OSS"
Then    the server creates a throwaway worktree via `git worktree add` (NOT touching the user's working tree),
        runs `uv run iw oss prepare` inside it, and reports the generated prep branch,
        the count of staged files, and a link to view the diff (via existing code view or a read-only patch)
And     underneath the "Prepare" button a "Run it yourself" collapsible block shows
        the equivalent `uv run iw oss prepare --project {id}` CLI command
And     same pattern applies to Publish (with prominent warning about visibility flip)
```

### AC5: HEAD-freshness banner

```
Given   the project HEAD has advanced past the last oss_scan.head_sha
When    I open /projects/{id}/oss or view the OSS Status frame
Then    a "scan is stale: HEAD has changed" banner appears
And     the pill color reflects the last scan's verdict but is annotated (⚠ icon) as stale
And     clicking "Rescan" triggers a new scan
```

### AC6: Results tree is understandable

```
Given   a completed scan with findings across multiple domains
When    I view /projects/{id}/oss
Then    findings are grouped by domain (secrets, license, community, …) in collapsible cards
And     each tool invocation (gitleaks, syft, grype, grant, osv-scanner, ripgrep, …) appears
        as a card with: tool name, version, runtime, verdict badge (PASS/FAIL/MISSING/SKIPPED),
        and an expandable details panel showing the command run and first 2KB of output
And     every finding shows: severity badge, summary, remediation hint, and for auto-fixable
        findings a "Fix via Prepare" link
```

### AC7: No regressions on sibling views

```
Given   the OSS feature is deployed
When    I navigate to Code, Tests, Quality, Documentation pages
Then    each page renders without console errors
And     the Git Status frame is intact and in the same visual position
And     the OSS Status frame appears underneath consistently on every project page
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Disabled project | `oss_enabled=false` | No OSS tab in sidebar; OSS Status frame shows "Install OSS" CTA; /oss URL redirects to install-modal state |
| No scans yet | Enabled, no `oss_scan` rows | Gray pill "not yet scanned"; Scan button prominent |
| Scan in progress | `project_oss_job.status='running'` | Pill shows spinner; results tree shows "scanning…" overlay; Scan button disabled |
| Scan errored | `status='error'` | Pill stays prior color (or gray if first scan); banner surfaces `stdout_tail` last lines + re-scan button |
| HEAD advanced since last scan | Live `rev-parse HEAD` ≠ `oss_scan.head_sha` | Banner "stale: last scan at abc123, HEAD now def456"; pill annotated with ⚠ |
| Tier-1 tool missing on server | `oss_service.probe()` returns at least one missing | Install modal preselected on first visit; Scan button disabled with tooltip |
| Concurrent scan request | Existing job `status='running'` | POST /scan returns 409 Conflict + `{running_job_id}`; UI shows "scan already in progress" toast |
| SSE disconnect mid-scan | Client reconnects | New SSE stream replays `project_oss_job.stdout_tail` from last persisted offset then subscribes live |
| Prepare on repo with dirty tree | N/A — we use a throwaway worktree | Prepare still works; user's tree untouched |
| Delete project with active jobs | `DELETE /projects/{id}` with `status='running'` | Cancel jobs, cleanup worktrees, cascade to `project_oss_job` rows (and F-00057 tables) |

## Invariants

1. No dashboard request ever modifies the developer's working tree directly; Prepare/Publish always use `git worktree add` + cleanup on completion.
2. `project_oss_job.status` transitions are monotonic: `queued → running → {complete, error, cancelled}` — no regressions.
3. On server shutdown mid-scan, orphaned `running` jobs are marked `error` at next startup with `error_message='orphaned by server restart'`.
4. SSE stream per job is idempotent: reconnecting replays from persisted `stdout_tail` then joins live stream.
5. Pill color rendered in the Status frame equals the pill color from F-00057's `status --json` output for the same scan.
6. The "OSS" tab appears in the project tab row **iff** `project.oss_enabled=true` — no other condition.
7. OSS Status frame renders on every project page identically (single template partial, included at the same slot).

## Dependencies

- **Depends on**: F-00057 (CLI + DB persistence — MUST merge first).
- **Blocks**: future generalization to Quality / Tests status frames.

## TDD Approach

**Unit tests**:
- `oss_service` job state transitions (mocked subprocess).
- Worktree lifecycle helper (create → execute → cleanup).
- SSE message encoding.

**Integration tests** (Postgres testcontainer + TestClient):
- Every API route (GET/POST for each endpoint) with success + error states.
- htmx fragment endpoints return the right `HX-*` headers.
- SSE stream emits `status`, `progress`, `complete` events in order; replay works on reconnect.
- Jinja reproduction: pill renders for each of 4 states; install modal renders for each Tier-1-availability mix; CLI block correctly shows the command variant per action.
- Tab visibility — OSS tab present iff `oss_enabled=true`.

**Browser tests** (S16 qv-browser):
- End-to-end Scan → pill transition.
- Install modal flow.
- Prepare button → see throwaway-worktree output + CLI block.
- No console errors on OSS, Code, Tests, Quality, Documentation pages.

**Edge cases**: every Boundary Behavior row → at least one test.

## Notes

- SSE implementation: reuse the existing pattern from `dashboard/routers/sse.py` if one exists; otherwise a small new `EventSourceResponse` helper. Heartbeat every 20s to prevent proxy timeouts.
- Throwaway worktree lifecycle: `git worktree add /tmp/oss-{uuid} HEAD` before run, `git worktree remove --force` after. Cleanup on any exit path (success, error, cancel, server shutdown via signal handler). Orphaned worktrees cleaned up at service startup.
- The OSS Status frame is cheap to render: it queries the latest `oss_scan` row for the project (indexed lookup) + compares HEAD. No subprocess call per page view.
- **Security**: enabling OSS or triggering scans on a project requires the same authorization as other project actions (dashboard already enforces this; reuse existing guard).
- The "Fix via Prepare" link on auto-fixable findings is a shortcut that triggers the Prepare flow scoped to that single finding. V1 can do full-Prepare; scoped-Prepare is nice-to-have.
- CSS: no new JS framework added. Use existing tailwind (or htmx + hyperscript if that's what the project uses — confirm during S06 by reading existing fragments).
- Design doc will be extended with wireframe references once S06 starts; for this Feature's planning we describe the layout in prose.
