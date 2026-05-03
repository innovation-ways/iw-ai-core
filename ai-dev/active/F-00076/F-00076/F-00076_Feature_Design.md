# F-00076: Cross-batch file-conflict gate

**Type**: Feature
**Priority**: High
**Created**: 2026-05-02
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Description

Promote impacted file paths to a first-class `WorkItem` field declared as globs in the design doc, then add a launch-time gate to the daemon that holds any candidate batch item whose impacted paths overlap with an in-flight item from any batch in the same project. Today, `orch/batch_planner.py` only detects overlaps inside a single batch and emits warnings for cross-batch conflicts (`orch/batch_planner.py:206-219`); nothing prevents the daemon from launching two items that touch the same files, which produces merge conflicts at squash-merge time and requires manual resolution. This feature converts cross-batch overlaps into a hard launch-time hold, wires up the dead `BatchItem.merge_info.conflict_files` schema field, and surfaces both states in the dashboard.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Critical companions for this feature:

- `orch/CLAUDE.md` — daemon module map and SQLAlchemy/Alembic conventions
- `executor/CLAUDE.md` — bash-script constraints (no docker, no alembic from executor)
- `dashboard/CLAUDE.md` — htmx fragment patterns
- `tests/CLAUDE.md` — testcontainer rules and FTS-trigger requirements

## Scope

### In Scope

- New `WorkItem.impacted_paths` JSONB column (NOT NULL DEFAULT `'[]'`) — array of glob strings.
- Use of `WorkItem.config.scope_extraction = {source, warned_at}` JSONB convention to record whether `impacted_paths` came from an explicit "Impacted Paths" section in the design doc (`source: "declared"`) or from the regex fallback (`source: "regex_fallback"`).
- New "Impacted Paths" section in `ai-dev/templates/Feature_Design_Template.md`, `ai-dev/templates/Issue_Design_Template.md`, `ai-dev/templates/CR_Design_Template.md` (and the master copies under `templates/design/`).
- New parser `parse_impacted_paths()` in `orch/design_doc_parser.py` — validates glob strings (no absolute paths, no `..`, no whitespace, must contain at least one path-like character).
- Hook in `orch/cli/item_commands.py:register()` (around line 350) that populates `WorkItem.impacted_paths` + `config.scope_extraction` at design-save time.
- Update `orch/batch_planner.py:analyze_dependencies()` to read `impacted_paths` from `items_data` dict instead of re-running `extract_affected_files()` (regex retained as the design-save fallback only).
- New helper module `orch/daemon/scope_overlap.py` exposing:
  - `is_test_path(glob: str) -> bool`
  - `globs_intersect(a: list[str], b: list[str]) -> list[str]` (uses `pathspec` GitWildMatchPattern, returns the conflicting globs)
  - `find_blocking_items(db, project_id, candidate) -> list[tuple[item_id, list[glob]]]`
- Launch-time gate in `orch/daemon/batch_manager.py:_process_batch()` (insert before line 351 `self._launch_item(...)`):
  - Skip gate when candidate's `WorkItem.type == Research`.
  - Filter in-flight items by `BatchItem.status in {setting_up, executing, merging}` AND `BatchItem.project_id == candidate.project_id` AND `WorkItem.type != Research`.
  - On any non-empty intersection (after stripping test-path patterns from both sides): leave candidate `status=pending`, emit one `item_held_for_scope` `DaemonEvent` per polling cycle with payload `{candidate_item_id, blocking_item_id, conflicting_globs}`.
- Wire-up of `BatchItem.merge_info.conflict_files`:
  - `executor/worktree_commit.sh` rebase block (lines 234-286): emit a structured `[worktree_commit] CONFLICT_FILES <json>` line listing files that hit conflict markers (auto-resolved or blocking).
  - `orch/daemon/merge_queue.py` `_perform_merge()` (around line 237): parse the marker line from `result.stdout` and store in `merge_info.conflict_files`.
- Dashboard surfacing:
  - `dashboard/templates/fragments/item_overview.html` — render `impacted_paths` as a collapsible list with the source badge.
  - `dashboard/templates/system/worktrees_table.html` (or the equivalent fragment) — add an "In-flight scope" tooltip column showing the in-flight item's globs.
  - `dashboard/templates/fragments/batch_items.html` — show "Held: overlaps with I-NNNNN on `<glob>`" for items in `pending` with a recent `item_held_for_scope` event.

### Out of Scope

- Cross-project overlap detection — different managed projects map to different repos, so no shared files exist by definition.
- Pre-merge trial-merge dry-run (deferred — the launch gate plus the existing scope gate at merge time are the two layers we ship now).
- Mid-flight claim extension via `git diff` snapshots (deferred — declared scope is treated as authoritative for v1).
- Global parallelism cap — per-batch `Batch.max_parallel` remains the only ceiling, as confirmed in design discussion.
- Editor UI for `impacted_paths` — the dashboard is read-only for this field; corrections happen in the design doc and via re-registration.
- Ad-hoc launch path patches — items launch only via batches in the current system.

## Impacted Paths

Globs declared here populate `WorkItem.impacted_paths` and are mirrored to `workflow-manifest.json:scope.allowed_paths`. Parser rules: gitignore-style globs only; no absolute paths; no `..`; no whitespace.

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/design_doc_parser.py`
- `orch/cli/item_commands.py`
- `orch/cli/batch_commands.py`
- `orch/batch_planner.py`
- `orch/daemon/scope_overlap.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/merge_queue.py`
- `executor/worktree_commit.sh`
- `ai-dev/templates/Feature_Design_Template.md`
- `ai-dev/templates/Issue_Design_Template.md`
- `ai-dev/templates/CR_Design_Template.md`
- `templates/design/Feature_Design_Template.md`
- `templates/design/Issue_Design_Template.md`
- `templates/design/CR_Design_Template.md`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/templates/system/worktrees_table.html`
- `dashboard/templates/fragments/batch_items.html`
- `dashboard/routers/items.py`
- `dashboard/routers/worktrees.py`
- `dashboard/routers/batches.py`
- `pyproject.toml`
- `uv.lock`

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration adding `WorkItem.impacted_paths JSONB NOT NULL DEFAULT '[]'`, ORM column, FTS trigger left untouched. Backfill running `extract_affected_files()` over `design_doc_content` for items in non-terminal status only. | — |
| S02 | code-review-impl | Review S01 (database) | — |
| S03 | backend-impl | `parse_impacted_paths()` parser, validation, `register()` hook, `config.scope_extraction` write, `analyze_dependencies()` switch to read from DB column. Update master + active design templates. | S04 |
| S04 | pipeline-impl | `orch/daemon/scope_overlap.py` helper, launch-time gate in `batch_manager._process_batch()`, `item_held_for_scope` events, `executor/worktree_commit.sh` `CONFLICT_FILES` marker, `merge_queue._perform_merge()` capture into `BatchItem.merge_info.conflict_files`. | S03 |
| S05 | code-review-impl | Review S03 (backend) | — |
| S06 | code-review-impl | Review S04 (pipeline) | — |
| S07 | frontend-impl | Dashboard surfacing: item overview panel, worktrees table tooltip, batch-detail held indicator. Templates + minor router additions if a held-event lookup is needed. | — |
| S08 | code-review-impl | Review S07 (frontend) | — |
| S09 | tests-impl | Cross-batch gate integration tests (Feature/Feature blocked, Feature/Research bypass), `globs_intersect()` unit tests, parser validation tests, `merge_info.conflict_files` capture test, regex-fallback test. | — |
| S10 | code-review-impl | Review S09 (tests) | — |
| S11 | code-review-final-impl | Global cross-agent review | — |
| S12 | qv-gate (lint) | `make lint` | — |
| S13 | qv-gate (format) | `make format-check` | — |
| S14 | qv-gate (typecheck) | `make type-check` | — |
| S15 | qv-gate (frontend-tsc) | `cd frontend && npx tsc --noEmit` | — |
| S16 | qv-gate (arch-check) | `make arch-check` | — |
| S17 | qv-gate (security-sast) | `make security-sast` | — |
| S18 | qv-gate (unit-tests) | `make test-unit` | — |
| S19 | qv-gate (frontend-tests) | `make test-frontend` | — |
| S20 | qv-gate (integration-tests) | `make allure-integration` | — |
| S21 | qv-browser | Browser verification of dashboard surfacing | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `work_items` — add `impacted_paths JSONB NOT NULL DEFAULT '[]'`. The existing `config` JSONB column gains a new convention key `scope_extraction = {"source": "declared|regex_fallback|none", "warned_at": "<ISO-8601>"}` — no schema change for that.
- **Migration notes**:
  - One new revision; depends on the latest current head (`alembic history` to discover).
  - Backfill in `upgrade()`: for each row where `status NOT IN ('completed', 'archived')` and `design_doc_content IS NOT NULL`, set `impacted_paths` to the result of `extract_affected_files(design_doc_content)`. Use `op.get_bind()` and a Python loop — no SQL-side regex needed.
  - `downgrade()`: drop the column.
  - No FTS-trigger rewrite required — the field is not text-searched.

### API Changes

- **New endpoints**: None.
- **Modified endpoints**: None — the dashboard reads `impacted_paths` through existing item-detail and worktrees routers (`dashboard/routers/items.py:949` overview tab and `dashboard/routers/worktrees.py:570` table). Routers may need to expand the data they pass to templates; that is template-coupled work owned by S07.

### Frontend Changes

- **New components**: An "Impacted Paths" panel partial (collapsible, glob list with source badge); an "In-flight scope" tooltip surface for the worktrees table.
- **Modified components**: `dashboard/templates/fragments/item_overview.html`, `dashboard/templates/system/worktrees_table.html` (or equivalent), `dashboard/templates/fragments/batch_items.html`.

## File Manifest

All files for this work item live under `ai-dev/active/F-00076/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00076_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00076_S01_Database_prompt.md` | Prompt | Database migration + ORM column + backfill |
| `prompts/F-00076_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/F-00076_S03_Backend_prompt.md` | Prompt | Parser, register hook, batch_planner switch, templates |
| `prompts/F-00076_S04_Pipeline_prompt.md` | Prompt | scope_overlap helper, launch-time gate, conflict_files capture |
| `prompts/F-00076_S05_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/F-00076_S06_CodeReview_Pipeline_prompt.md` | Prompt | Review S04 |
| `prompts/F-00076_S07_Frontend_prompt.md` | Prompt | Dashboard surfacing |
| `prompts/F-00076_S08_CodeReview_Frontend_prompt.md` | Prompt | Review S07 |
| `prompts/F-00076_S09_Tests_prompt.md` | Prompt | Integration + unit tests |
| `prompts/F-00076_S10_CodeReview_Tests_prompt.md` | Prompt | Review S09 |
| `prompts/F-00076_S11_CodeReview_Final_prompt.md` | Prompt | Cross-agent review |
| `prompts/F-00076_S21_BrowserVerification_prompt.md` | Prompt | Dashboard browser verification |

Implementation files referenced (sources of truth; modified by the steps above):

| Path | Layer |
|------|-------|
| `orch/db/models.py` | Database |
| `orch/db/migrations/versions/<new>_add_impacted_paths_to_work_items.py` | Database |
| `orch/design_doc_parser.py` | Backend |
| `orch/cli/item_commands.py` | Backend |
| `orch/cli/batch_commands.py` | Backend |
| `orch/batch_planner.py` | Backend |
| `ai-dev/templates/Feature_Design_Template.md` | Backend (template) |
| `ai-dev/templates/Issue_Design_Template.md` | Backend (template) |
| `ai-dev/templates/CR_Design_Template.md` | Backend (template) |
| `templates/design/Feature_Design_Template.md` | Backend (template) |
| `templates/design/Issue_Design_Template.md` | Backend (template) |
| `templates/design/CR_Design_Template.md` | Backend (template) |
| `orch/daemon/scope_overlap.py` | Pipeline |
| `orch/daemon/batch_manager.py` | Pipeline |
| `orch/daemon/merge_queue.py` | Pipeline |
| `executor/worktree_commit.sh` | Pipeline |
| `dashboard/templates/fragments/item_overview.html` | Frontend |
| `dashboard/templates/system/worktrees_table.html` | Frontend |
| `dashboard/templates/fragments/batch_items.html` | Frontend |
| `dashboard/routers/items.py` | Frontend (data pass-through) |
| `dashboard/routers/worktrees.py` | Frontend (data pass-through) |
| `dashboard/routers/batches.py` | Frontend (data pass-through) |

Reports are created during execution in `ai-dev/active/F-00076/reports/`.

## Acceptance Criteria

### AC1: Cross-batch overlap is held until upstream merges

```
Given batch A contains item I-100 (Feature) currently in BatchItem status
      'executing' with WorkItem.impacted_paths = ["orch/daemon/**"]
And   batch B contains item I-200 (Feature) with WorkItem.impacted_paths
      = ["orch/daemon/batch_manager.py"]
When  batch B becomes 'approved' and the daemon poll runs while I-100
      is still in flight
Then  I-200 remains in BatchItem.status='pending'
And   exactly one DaemonEvent of type 'item_held_for_scope' is emitted
      per poll cycle while I-200 is held, with event_metadata
      {candidate: "I-200", blocking: "I-100", conflicting_globs: [...]}
And   within one poll cycle after I-100 transitions to 'merged',
      I-200 launches normally
```

### AC2: Research items bypass the gate

```
Given a Feature item I-100 in 'executing' with impacted_paths
      = ["docs/**", "orch/foo.py"]
And   a Research item RES-50 in batch B with impacted_paths
      = ["docs/architecture.md"]
When  the daemon evaluates RES-50 for launch
Then  RES-50 launches in the same poll cycle (no hold, no
      'item_held_for_scope' event)
```

### AC3: LLM-declared scope is recorded as 'declared'

```
Given a Feature design doc with an "Impacted Paths" H2 section listing
      globs as a markdown list
When  iw register is invoked against that design doc
Then  WorkItem.impacted_paths contains exactly those globs (preserving
      order and uniqueness)
And   WorkItem.config["scope_extraction"]["source"] == "declared"
And   WorkItem.config["scope_extraction"] has no "warned_at" key
```

### AC4: Regex fallback flags missing scope

```
Given a Feature design doc that omits the "Impacted Paths" H2 section
      but mentions code paths in prose (e.g. "modify orch/foo.py")
When  iw register is invoked
Then  WorkItem.impacted_paths is populated by extract_affected_files
And   WorkItem.config["scope_extraction"]["source"] == "regex_fallback"
And   WorkItem.config["scope_extraction"]["warned_at"] is an ISO-8601
      timestamp
And   stderr from `iw register` contains a warning string
      matching r"scope auto-extracted, please verify"
```

### AC5: Conflict files captured during rebase auto-resolution

```
Given a worktree branch where rebase onto main hits a conflict on
      uv.lock that the script auto-resolves with --ours
When  worktree_commit.sh completes the rebase and the squash-merge
      succeeds
Then  BatchItem.merge_info["conflict_files"] == ["uv.lock"]
And   the value is a JSON array of strings (not a string blob)
```

### AC6: Dashboard surfaces impacted paths and held reason

```
Given a Feature item with impacted_paths = ["orch/daemon/**"] and a
      DaemonEvent of type 'item_held_for_scope' emitted within the
      last 60s for it
When  the user opens the item-detail page in the dashboard
Then  the page renders an "Impacted Paths" panel listing the globs
      and a "declared" badge
And   when the user opens the batch-detail page containing this item
      they see "Held: overlaps with I-NNNNN on `orch/daemon/**`" as
      the row indicator
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Empty `impacted_paths` (research item) | `[]` | Gate is no-op; item launches |
| Empty `impacted_paths` on a Feature | `[]` after design save (LLM declared empty) | Item launches without hold; future cross-batch conflicts are not detected. Considered a designer error, NOT a system bug — `config.scope_extraction.source` is `"declared"` |
| Glob with `..` | `"../etc/passwd"` | `parse_impacted_paths()` rejects with ValueError; `iw register` exits non-zero |
| Absolute glob | `"/etc/passwd"` | Rejected, same as above |
| Whitespace-only glob | `"   "` | Rejected |
| Mix of test and non-test globs | `["orch/foo.py", "**/tests/**"]` | Stored as-is. Intersection check against another item with the same `**/tests/**` ignores the test glob — items run in parallel if test patterns are the only overlap |
| Both items only declare test globs | A: `["**/tests/**"]`, B: `["tests/test_x.py"]` | No conflict — they may run in parallel |
| In-flight item is in `setup_failed` | A is `setup_failed` (terminal failure); B candidates | A is NOT considered in-flight — gate ignores it (not in `{setting_up, executing, merging}`) |
| In-flight item is in `merged` | A is `merged`; B candidates | A is NOT considered in-flight; B can launch even with overlap |
| Held item on later poll | I-200 held last cycle; I-100 still executing | One new `item_held_for_scope` event per cycle while held — no event coalescing |
| Glob `**` matches everything | A: `["**"]`, B: any non-test glob | Treated as overlap; B holds. (Designers should avoid `**`; documented anti-pattern) |
| Cross-project items overlap on path string | A `project=foo` `["orch/x.py"]`, B `project=bar` `["orch/x.py"]` | NO conflict — gate filters by project_id |
| `pathspec` library not installed at daemon start | Import error at module load | Daemon fails fast at startup with a clear error message — added to `pyproject.toml` deps in S01/S03 (whichever pulls it first) |
| Design doc has multi-line/code-block "Impacted Paths" section | Globs inside a fenced code block | Parser supports fenced code blocks AND markdown bullet lists; documents both formats in template |

## Invariants

1. `WorkItem.impacted_paths` is NEVER NULL at the database layer (NOT NULL constraint with default `'[]'`).
2. For every Feature/Incident/CR item, `config["scope_extraction"]["source"] ∈ {"declared", "regex_fallback", "none"}` after `iw register` completes (Research items may keep `"none"` even if `impacted_paths` is empty).
3. The cross-batch gate NEVER blocks a Research item, regardless of overlap.
4. The cross-batch gate NEVER compares items from different `project_id`.
5. The cross-batch gate NEVER considers test-path globs when computing intersection.
6. After every successful or auto-resolved rebase, `BatchItem.merge_info["conflict_files"]` is either an empty array (no conflicts) or a JSON array of file paths — never absent and never a string.
7. The intra-batch overlap detection in `orch/batch_planner.py` continues to detect conflicts identically to today, but reads from `WorkItem.impacted_paths` rather than re-running `extract_affected_files()`.
8. The merge-time `executor/scope_gate.py` continues to enforce `workflow-manifest.json:scope.allowed_paths` unchanged; this feature only adds an upstream gate.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

- **Unit tests**:
  - `orch/design_doc_parser.py::parse_impacted_paths()` — happy path, missing section, fenced code block, bullet list, validation errors (absolute path, `..`, whitespace, empty), unicode-safe.
  - `orch/daemon/scope_overlap.py::globs_intersect()` — exact match, prefix glob (`dir/**`), wildcard glob (`*.py`), test-path stripping, empty inputs, both-empty returns empty list.
  - `orch/daemon/scope_overlap.py::is_test_path()` — coverage for each `_TEST_PATH_MARKERS` pattern.
- **Integration tests** (testcontainer with FTS triggers wired up per `tests/CLAUDE.md`):
  - `iw register` populates `WorkItem.impacted_paths` from declared section (AC3 fixture).
  - `iw register` falls back to regex and stamps `config.scope_extraction.warned_at` when section is missing (AC4).
  - Daemon `_process_batch()` holds a Feature when an in-flight Feature in another batch has overlapping globs (AC1).
  - Daemon `_process_batch()` launches a Research item even when in-flight Feature overlaps (AC2).
  - Backfill in the new alembic migration produces sane `impacted_paths` for existing in-flight items (run on a fixture seeded with a representative `design_doc_content`).
  - `merge_queue._perform_merge()` populates `merge_info["conflict_files"]` when `worktree_commit.sh` emits the marker.
- **Edge cases**:
  - `impacted_paths` containing both test and production globs — only production globs participate in intersection.
  - Two items with `["**"]` each — they hold each other (both are pending until one runs; the daemon picks one deterministically by `BatchItem.id` order).
  - Held event emission cadence — exactly one per poll cycle.
  - Cross-project items with identical paths — never compared.

## Notes

- `pathspec` is the chosen glob engine because it implements gitignore-style matching (which matches the existing `executor/scope_gate.py` semantics for `dir/**`). If it is not already a transitive dependency, S01 (or S03) adds it to `pyproject.toml` and runs `uv lock`.
- The "Impacted Paths" template section uses a markdown bullet list as the canonical format; the parser also accepts a fenced code block for cases where globs contain characters Markdown might misinterpret.
- The existing intra-batch overlap detection in `orch/batch_planner.py` (`Phase 3` at lines 194-204) and the cross-batch warning emission (`Phase 3b` at lines 206-219) are both updated to read from `WorkItem.impacted_paths`. The Phase 3b warning message remains useful as an early signal at batch-create time even though the daemon now enforces the rule at launch time — keep it as an informational warning.
- The merge-time scope gate (`executor/scope_gate.py` invoked from `executor/worktree_commit.sh`) is OUT OF SCOPE for this feature. It is currently opt-in per project via `.iw-orch.json:scope_gate_enabled` (default OFF — see `executor/CLAUDE.md`). When enabled, it reads `workflow-manifest.json:scope.allowed_paths`, which the design-save hook in S03 mirrors from `WorkItem.impacted_paths`. CR-00030 will replace that blanket toggle with finer-grained enforcement; F-00076's launch-time gate is independent and ALWAYS on for Feature/Incident/CR items, so it remains the primary defense even on projects with the merge-time gate disabled.
- The daemon's poll loop runs every `IW_CORE_POLL_INTERVAL` seconds (default 60s per `.env`). Held-event emission cadence inherits this; a held item will emit one event per minute.
- `WorkItem` has no top-level `notes` column (only `BatchItem` does). Fallback warnings live in `config["scope_extraction"]` JSONB to avoid a schema change for diagnostic-only data.
