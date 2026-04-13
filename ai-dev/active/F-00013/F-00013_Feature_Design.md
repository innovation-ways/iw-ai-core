# F-00013: Project-Level Documentation System — Automation (Phase 3)

**Type**: Feature
**Priority**: Medium
**Created**: 2026-04-13
**Status**: Draft

---

## Description

Makes documentation generation event-driven rather than purely manual. After every successful batch merge in the orchestration pipeline, the daemon inspects which source files changed and cross-references them against each `ProjectDoc.source_paths`. Any doc whose source files were touched is automatically enqueued for regeneration. This phase also introduces source-mtime staleness tracking (aligned with the InnoForge `source-mtime` strategy from `documentation-strategy.md`), a dashboard staleness indicator per doc, an editorial lint gate that validates generated content against basic quality rules before marking a doc as `draft`, and project-level doc generation configuration stored in the `Project.config` JSONB field.

**Depends on**: F-00012 (Phase 2 — the job execution engine must be live before automation can enqueue jobs)

## Project Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, `orch/daemon/`. Key constraint: the daemon is the sole source of automation — it polls PostgreSQL; no cron, no webhooks, no file watchers. All event-driven logic must be implemented as post-merge hooks within the existing daemon batch completion flow.

## Scope

### In Scope

- Post-merge hook in daemon: after a `BatchItem` transitions to `merged`, compute changed files via `git diff HEAD^..HEAD --name-only` in `project.repo_root` (works because the daemon merges one item at a time), match against `ProjectDoc.source_paths`, enqueue `DocGenerationJob` for each matched doc
- `DocService.find_docs_by_source_path(changed_paths: list[str]) -> list[ProjectDoc]` — efficient path-matching query
- Source-mtime staleness tracking: `DocService.get_stale_docs()` upgraded to check actual git mtime of source files (not just `generated_at` age) — uses `git log --format=%ct -- {path}` to get last-modified epoch
- Dashboard staleness indicator: "Stale" badge on doc cards when `source_paths` have newer commits than `generated_at`; tooltip showing which source changed and when
- Staleness summary row on the doc library page: "3 docs are stale — Regenerate All" button
- `iw docs-check-stale <project_id>` CLI command: outputs a table of stale docs (mirrors `make docs-check-stale` from InnoForge `README.md`)
- Editorial lint gate: after `iw doc-update` writes content, run a lightweight validation pass:
  - Checks that YAML frontmatter is present and well-formed
  - Checks that required sections exist (based on `editorial_category` rules stored as config)
  - Checks that no forbidden phrases are used (configurable list per project)
  - If lint fails: job completes but `DocGenerationJob.lint_warnings` is populated; doc status stays `draft` (not promoted)
- Project-level doc config in `Project.config` JSONB: `doc_generation.enabled`, `doc_generation.auto_trigger_on_merge`, `doc_generation.stale_threshold_hours`, `doc_generation.forbidden_phrases`
- Dashboard doc config panel: toggle auto-trigger, set stale threshold, manage forbidden phrases (accessible from Docs tab settings icon)
- Concurrent job limit: max 2 `DocGenerationJob` records in `running` state per project at any time; additional jobs stay `queued` until a slot opens

### Out of Scope

- Version diffing UI (Phase 4)
- Cross-project staleness report (Phase 4)
- Full editorial guideline enforcement (human review remains required for Tier 2/3 docs)
- GitHub Actions / CI integration
- Scheduled/cron-based regeneration (time-based staleness is detected but regeneration is still daemon-driven)

## Architecture References

| Existing Pattern | Location | How We Extend It |
|-----------------|----------|-----------------|
| Batch merge completion hook | `orch/daemon/merge_queue.py` | Add `trigger_doc_regeneration_on_merge(batch_item, project)` call after `item_merged` event |
| Git diff after squash merge | `orch/daemon/` | `git diff HEAD^..HEAD --name-only` — safe because daemon is single-threaded; no SHA storage needed |
| `DocGenerationJob` enqueue | F-00012 | Same job creation pattern |
| `DocService.get_stale_docs()` | `orch/doc_service.py` (F-00011) | Upgrade with git mtime check |
| `Project.config` JSONB | `orch/db/models.py` | Add `doc_generation` sub-key |
| Dashboard settings panels | `dashboard/templates/` | New config panel on Docs tab |

## Implementation Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Post-merge hook; `find_docs_by_source_path()`; git-mtime staleness upgrade; `iw docs-check-stale` CLI; editorial lint gate; concurrent job limit enforcement | — |
| S02 | Frontend | Staleness badge on cards; "Stale" summary row + "Regenerate All"; doc config panel (auto-trigger toggle, stale threshold, forbidden phrases) | — |
| S03 | Tests | Integration tests: merge → job enqueued; staleness detection; lint gate; concurrent limit; config panel | — |
| S04 | CodeReview_Final | Global cross-layer review | — |
| S05–S12 | QV Gates | lint → format → typecheck → arch-check → security-sast → unit → frontend → integration | — |

## Database Changes

**Modified tables:**
- `doc_generation_jobs` — add `lint_warnings` (JSONB, nullable) column: list of lint warning objects `{rule, message, line}`

**No new tables** — all automation state is in existing tables + `Project.config` JSONB.

**Migration**: One Alembic migration adding `lint_warnings` column.

## API Changes

**New CLI command:**
- `iw docs-check-stale <project_id> [--threshold-hours INTEGER]` — prints table of stale docs with source file and mtime info; exits 0 if none stale, exits 1 if any stale (usable in CI)

**New dashboard routes:**
- `GET /api/project/{id}/docs/stale` — htmx fragment: stale docs summary row
- `POST /api/project/{id}/docs/regenerate-stale` — enqueues jobs for all stale docs, returns count
- `GET /api/project/{id}/docs/config` — render doc config panel fragment
- `POST /api/project/{id}/docs/config` — save doc config to `Project.config.doc_generation`
- `GET /api/project/{id}/docs/{doc_id}/lint-warnings` — htmx fragment: lint warnings callout for detail page

## Frontend Changes

**Modified templates:**
- `dashboard/templates/fragments/docs_card.html` — add "Stale" badge (yellow warning icon + "Sources changed") when doc is stale; tooltip with changed source name
- `dashboard/templates/docs_library.html` — add staleness summary row above card grid; add settings gear icon linking to config panel

**New templates:**
- `dashboard/templates/fragments/docs_stale_summary.html` — "N docs are stale — Regenerate All" row
- `dashboard/templates/fragments/docs_config_panel.html` — doc generation config form

## File Manifest

All files for this work item live under `ai-dev/active/F-00013/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00013_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00013_S01_Backend_prompt.md` | Prompt | S01 backend implementation instructions |
| `prompts/F-00013_S02_Frontend_prompt.md` | Prompt | S02 frontend implementation instructions |
| `prompts/F-00013_S03_Tests_prompt.md` | Prompt | S03 integration tests instructions |
| `prompts/F-00013_S04_CodeReview_Final_prompt.md` | Prompt | S04 final cross-agent review instructions |

Reports are created during execution in `ai-dev/work/F-00013/reports/`.

## Acceptance Criteria

### AC1: Batch merge triggers doc regeneration

```
Given: A ProjectDoc with source_paths=["docs/auth.md"] exists
And: Project.config.doc_generation.auto_trigger_on_merge = true
When: A batch merges and the merge includes a change to docs/auth.md
Then: A DocGenerationJob is created for that doc with status=queued
And: trigger_reason = "batch-merge:{batch_id}"
```

### AC2: Unchanged source files do not trigger jobs

```
Given: A ProjectDoc with source_paths=["docs/billing.md"] exists
When: A batch merges with changes only to docs/auth.md
Then: No DocGenerationJob is created for the billing doc
```

### AC3: Stale badge appears on outdated docs

```
Given: A ProjectDoc with generated_at=T and source_paths=["docs/auth.md"]
And: docs/auth.md has a git commit newer than T
When: User visits the Docs library page
Then: The doc card shows a "Stale" badge with tooltip indicating docs/auth.md changed
```

### AC4: Regenerate All enqueues jobs for all stale docs

```
Given: 3 docs are stale (sources changed after generated_at)
When: User clicks "Regenerate All"
Then: 3 DocGenerationJob records are created (status=queued)
And: The button shows count: "Queued 3 jobs"
```

### AC5: iw docs-check-stale exits 1 when stale docs exist

```
When: iw docs-check-stale innoforge
Then: Prints table with stale doc IDs, source files, and mtime
And: Exits with code 1
When: No stale docs exist
Then: Prints "All docs are current"
And: Exits with code 0
```

### AC6: Editorial lint gate populates warnings without blocking

```
Given: A generated doc is missing the required "## Purpose" section (for technical category)
When: iw doc-update writes the content
Then: The lint gate detects the missing section
And: DocGenerationJob.lint_warnings contains a warning entry
And: Doc status remains draft (not promoted to published)
And: The detail page shows a "Lint warnings" callout listing the issues
```

### AC7: Concurrent job limit is enforced

```
Given: 2 DocGenerationJob records are in running state for a project
When: The daemon tries to start a 3rd job
Then: The 3rd job remains queued until one of the running jobs completes
```

### AC8: Auto-trigger can be disabled per project

```
Given: Project.config.doc_generation.auto_trigger_on_merge = false
When: A batch merges with changes to source files
Then: No DocGenerationJob is created automatically
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| source_paths uses glob patterns | `["docs/auth/**/*.md"]` | Path matching expands glob before comparing to changed files |
| Source file deleted from repo | `source_paths` references a deleted file | File is no longer git-tracked → doc marked stale with reason "source deleted" |
| Merge changes 50 source files matching 10 docs | High-volume merge | At most 2 jobs run concurrently; remaining 8 queue in order |
| Lint warns on forbidden phrase | Content contains "cutting-edge" (forbidden) | Warning added, doc not blocked from publishing manually |
| docs-check-stale with no source_paths | Docs without source_paths | Skipped (shown as "N/A" in stale check output) |
| Project config not set | `doc_generation` key missing from `Project.config` | Use defaults: `auto_trigger_on_merge=false`, `stale_threshold_hours=24` |
| Regenerate All with 0 stale docs | Button clicked when no stale docs | Button is hidden (not disabled) — only shown when stale docs exist |

## Invariants

1. At most 2 `DocGenerationJob` records per project can be in `running` state simultaneously
2. `auto_trigger_on_merge=false` means zero jobs are auto-created — no exceptions
3. The lint gate never changes `DocStatus` — it only populates `lint_warnings`; status transitions remain human-controlled (or Phase 2 generation job logic)
4. `iw docs-check-stale` exit code is always 0 (no stale) or 1 (stale found) — never crashes
5. Path matching in `find_docs_by_source_path()` handles both exact paths and glob patterns

## Dependencies

- **Depends on**: F-00012 (Phase 2)
- **Blocks**: F-00014 (Phase 4)

## TDD Approach

- Unit tests: `find_docs_by_source_path()` with exact and glob paths; git mtime staleness logic; lint gate rule evaluation; concurrent limit enforcement
- Integration tests: full merge→job pipeline with real DB; staleness detection with real git repo context (use testcontainer + git init fixture); config panel save/load

## Notes

**Git mtime implementation:**
```python
import subprocess
result = subprocess.run(
    ["git", "log", "-1", "--format=%ct", "--", path],
    cwd=project.repo_root, capture_output=True, text=True
)
mtime = int(result.stdout.strip()) if result.stdout.strip() else None
```
Run for each path in `source_paths`. Compare against `doc.generated_at.timestamp()`.

**Forbidden phrases default list** (seeded from InnoForge editorial `_default.md`):
`["cutting-edge", "state-of-the-art", "revolutionary", "game-changing", "leverage", "synergy", "robust solution"]`

**Editorial lint rules** (configurable per `editorial_category`):
- `technical`: must contain `## Purpose`, `## Architecture`, at least one code block
- `functional`: must contain `## Overview`, `## Key Capabilities`
- `guide`: must contain `## Prerequisites`, `## Steps`
- All categories: no forbidden phrases, YAML frontmatter present and parseable
