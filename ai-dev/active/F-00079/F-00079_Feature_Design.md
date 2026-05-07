# F-00079: Files View — Per-Item Git Changes Explorer with Step Drilldown and PDF Export

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-07
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This feature ADDS a new migration. The migration adds five nullable columns
across two existing tables (`work_items` +3, `step_runs` +2) — pure ADD COLUMN
with no defaults that touch existing rows, safe to run online against the live
DB on port 5433. The agent in S01 writes the file only; the daemon's merge
pipeline applies it.

## Description

Replace the work-item detail page's "Artifacts" tab with a new "Files" tab that
shows a modern, GitHub-style explorer of git changes (added / modified /
deleted / renamed files with per-file unified diffs) for every work item —
live for in-progress items, lazy `git diff` for completed-not-archived items,
and DB-stored snapshots for archived items. Adds a step-level drilldown
toggle, a branded PDF export of the diff report, and preserves access to
non-source worktree files via an "Other worktree files" sub-panel.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Critical rules to honour: ORM is SQLAlchemy 2.0 sync, driver is `psycopg` v3
(NOT psycopg2), tests must use testcontainers (NEVER live DB on 5433), append
plain CSS to `dashboard/static/styles.css` if `make css` cannot run, browser
automation goes through `playwright-cli` exclusively, `DaemonEvent.metadata`
is named `event_metadata` in Python (SQLAlchemy reserves `metadata`).

Per-table dashboard router boundaries: see `dashboard/CLAUDE.md` — routers are
thin (validation + delegation only), business logic belongs in `orch/`.

Per-orchestration package boundaries: see `orch/CLAUDE.md` — append-only
tables (`step_runs`, `fix_cycles`, `daemon_events`, `test_runs`,
`project_doc_versions`) never get their existing rows replaced, but field
updates within a row's lifecycle are allowed (e.g., `iw step-done` already
updates `status`, `completed_at`, `duration_secs`, `report_file`,
`log_content` on the in-flight `step_run` row).

## Scope

### In Scope

- New "Files" tab on the work-item detail page replacing "Artifacts" entirely.
- Three-state diff source resolver (live worktree, lazy `git diff` from `main`, DB snapshot).
- Aggregate squash-merge diff captured to `work_items.diff_text` + `diff_summary`.
- Per-step diff captured at `iw step-done` to `step_runs.diff_text` + `diff_summary`.
- Step toggle (aggregate vs single step) in the Files tab toolbar.
- File tree (full nested, IDE-convention ordering: directories first then files alphabetical) + per-file unified diff cards.
- Status badges A / M / D / R + `+N −M` proportional bars + sticky filename headers.
- Auto-collapse heuristics: ≤10 files all expanded; otherwise all collapsed; generated files (`uv.lock`, `package-lock.json`, `*.min.js`, `*.snap`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`) always collapsed.
- Per-file thresholds: 500 lines auto-collapse with htmx "Load full diff"; 5000 lines = no inline view, "Download raw diff" link only.
- Binary files: placeholder card "Binary file changed — N bytes".
- Filter input that filters the tree and the diff cards by path substring.
- "Other worktree files" sub-panel listing untracked files (`git status --porcelain` filtered, status `??`, excluding paths owned by other tabs); only rendered while worktree is alive.
- "Export PDF" toolbar button that downloads a branded WeasyPrint-rendered PDF of the diff report.
- Dark-mode synced with the existing `documentElement.classList` toggle.
- Removal of the existing `/tab/artifacts` route, `item_artifacts.html` fragment, and corresponding helpers in `dashboard/routers/items.py`. The `/artifact-raw` endpoint is preserved (used by the new untracked sub-panel).
- TDD coverage at unit, integration, and browser-smoke layers.

### Out of Scope

- Inline review comments / threaded discussions on diff lines (read-only audit).
- Mark-as-viewed / per-file progress tracking.
- Side-by-side (split) diff mode in v1 — unified only.
- Code-intelligence on hover (go-to-def, find-references).
- Filtering by file extension or status badge dropdown (path-substring filter only).
- Word-level diff highlighting within changed lines (line-level only via diff2html defaults).
- Keyboard shortcuts overlay (`?` overlay) — basic `j/k/t/o` shortcuts are nice-to-have but not required.
- Replacing PDF export styling beyond what `dashboard/routers/docs.py:169` already establishes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration adding `work_items` (+3 cols) and `step_runs` (+2 cols); ORM model updates in `orch/db/models.py` | — |
| S02 | code-review-impl | Review S01 schema migration + model update | — |
| S03 | backend-impl | `orch/diff_service.py` (resolver + unidiff parser), `iw step-done` per-step capture, `merge_queue.py` post-squash aggregate capture, add `unidiff` dep | — |
| S04 | code-review-impl | Review S03 daemon + CLI changes (resolver routing, capture hooks, append-only invariants, daemon_events warnings) | — |
| S05 | api-impl | New routes (`/tab/files`, `/files/diff`, `/files/untracked`, `/files/export.pdf`); remove `/tab/artifacts` and the `_list_artifact_tree` helper if unused | S06, S07 |
| S06 | frontend-impl | `item_files.html` shell + `item_files_untracked.html`; `item_detail.html` tab swap; vendored `diff2html.html` libs include + `static/vendor/diff2html/` bundle; `files.js` for tree/filter/client-side collapse/dark-mode sync; delete `item_artifacts.html` | S05, S07 |
| S07 | template-impl | `exports/diff_pdf.html` Jinja for WeasyPrint with Pygments highlighting and IW palette | S05, S06 |
| S08 | code-review-impl | Review S05 + S06 + S07 holistically (route contract consistency, fragment ↔ JS wiring, PDF template integrity) | — |
| S09 | tests-impl | Unit (resolver), integration (capture hooks + routes + PDF), browser-smoke (Files tab interaction) | — |
| S10 | code-review-impl | Review S09 test coverage against AC1–AC8 | — |
| S11 | code-review-final-impl | Global cross-agent review | — |
| S12 | qv-gate | `make lint` | — |
| S13 | qv-gate | `make format` | — |
| S14 | qv-gate | `make typecheck` | — |
| S15 | qv-gate | `make security-sast` | — |
| S16 | qv-gate | `make test-unit` | — |
| S17 | qv-gate | `make test-frontend` | — |
| S18 | qv-gate | `make test-integration` (timeout 900s) | — |
| S19 | qv-browser | Open Files tab on a real item; verify tree + diff render, step toggle, untracked sub-panel, PDF download | — |
| S20 | self-assess-impl | iw-item-analyze postmortem (project has `self_assess = true`) | — |

### Database Changes

- **New tables**: None.
- **Modified tables**:
  - `work_items` adds `diff_text TEXT NULL`, `diff_summary JSONB NULL`, `merge_commit_sha TEXT NULL`.
  - `step_runs` adds `diff_text TEXT NULL`, `diff_summary JSONB NULL`.
- **Migration notes**: pure `ADD COLUMN ... NULL` (no server defaults, no NOT NULL constraints, no index creation that scans existing rows). Safe online against live DB. PostgreSQL TOAST handles compression of `diff_text` automatically. `diff_summary` JSONB is a list of objects: `[{"path": str, "status": "A|M|D|R", "added": int, "removed": int, "is_generated": bool, "is_binary": bool, "old_path": str | null}, ...]`.

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/item/{item_id}/tab/files` → tab shell fragment (tree + toolbar + summary + lazy diff mounts).
  - `GET /project/{project_id}/item/{item_id}/files/diff?step=<all|step_id>` → returns the raw unified diff text as `text/plain` (consumed client-side by diff2html-ui).
  - `GET /project/{project_id}/item/{item_id}/files/untracked` → JSON list of untracked worktree files (only valid while worktree alive).
  - `GET /project/{project_id}/item/{item_id}/files/export.pdf?step=<all|step_id>` → WeasyPrint-rendered PDF download.
- **Removed endpoints**:
  - `GET /project/{project_id}/item/{item_id}/tab/artifacts` (and the `item_artifacts.html` fragment + helper `_list_artifact_tree` if it has no other callers; verify and prune).
- **Preserved endpoints**:
  - `GET /project/{project_id}/item/{item_id}/artifact-raw?path=<rel>` — reused by the new untracked sub-panel (markdown / image / text preview).

### Frontend Changes

- **New components / fragments**:
  - `dashboard/templates/fragments/item_files.html` — tab shell.
  - `dashboard/templates/fragments/item_files_untracked.html` — untracked files sub-panel (reuses preview behaviour from removed Artifacts).
  - `dashboard/templates/components/libs/diff2html.html` — vendored includes for diff2html-ui CSS + JS (slim bundle), served from `dashboard/static/vendor/diff2html/`. No CDN.
  - `dashboard/templates/exports/diff_pdf.html` — branded WeasyPrint template for PDF export.
  - `dashboard/static/files.js` — small client-side module: tree expand/collapse, filter, client-side per-file collapse toggle (no server roundtrip), dark-mode color-scheme sync for diff2html.
- **Modified components**:
  - `dashboard/templates/pages/project/item_detail.html` — tab button "Artifacts" → "Files" with new `hx-get` URL.
  - `dashboard/static/styles.css` — append plain CSS rules for status-badge variants, `+N −M` bar, sticky headers if Tailwind classes alone don't suffice (see `CLAUDE.md` rule).
- **Removed**:
  - `dashboard/templates/fragments/item_artifacts.html`.

## File Manifest

All files for this work item live under `ai-dev/active/F-00079/`:

| File | Type | Purpose |
|------|------|---------|
| `F-00079_Feature_Design.md` | Design | This document |
| `F-00079_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00079_S01_Database_prompt.md` | Prompt | S01 — schema + migration |
| `prompts/F-00079_S02_CodeReview_Database_prompt.md` | Prompt | S02 — review S01 |
| `prompts/F-00079_S03_Backend_prompt.md` | Prompt | S03 — diff resolver + capture hooks |
| `prompts/F-00079_S04_CodeReview_Backend_prompt.md` | Prompt | S04 — review S03 |
| `prompts/F-00079_S05_API_prompt.md` | Prompt | S05 — FastAPI routes |
| `prompts/F-00079_S06_Frontend_prompt.md` | Prompt | S06 — UI fragments + diff2html |
| `prompts/F-00079_S07_Template_prompt.md` | Prompt | S07 — PDF export template |
| `prompts/F-00079_S08_CodeReview_API_FE_Tmpl_prompt.md` | Prompt | S08 — review S05 + S06 + S07 |
| `prompts/F-00079_S09_Tests_prompt.md` | Prompt | S09 — unit + integration + browser tests |
| `prompts/F-00079_S10_CodeReview_Tests_prompt.md` | Prompt | S10 — review S09 |
| `prompts/F-00079_S11_CodeReview_Final_prompt.md` | Prompt | S11 — final cross-agent review |
| `prompts/F-00079_S19_BrowserVerification_prompt.md` | Prompt | S19 — qv-browser end-to-end verification |
| `prompts/F-00079_S20_SelfAssess_prompt.md` | Prompt | S20 — iw-item-analyze postmortem |

Reports are created during execution under `ai-dev/active/F-00079/reports/`.

## Acceptance Criteria

### AC1: Live diff for in-progress item

```
Given a work item in phase = 'active' with a live worktree containing committed changes
When the user opens the Files tab on the item detail page
Then the unified diff (`git diff <base_branch>...HEAD` in the worktree) is rendered with a nested file tree, status badges (A/M/D/R), +N −M bars, and per-file diff cards
```

### AC2: Step toggle drilldown

```
Given a work item with at least two completed step_runs that captured diff_text
When the user selects a specific step in the Files tab toolbar dropdown
Then only that step's diff is rendered; switching back to "All steps" shows the aggregate diff (live or stored, per state)
```

### AC3: Archived item still has diff

```
Given a work item where archived_at IS NOT NULL and the worktree directory has been removed
When the user opens the Files tab
Then the diff is loaded from work_items.diff_text and rendered identically to a non-archived item; no shell-out to git is attempted
```

### AC4: PDF export downloads a branded report

```
Given any work item with a non-null diff source resolvable for the requested step
When the user clicks "Export PDF" with the current step selection
Then the browser downloads a PDF whose content includes a header with the item ID and title, an aggregate +N −M summary table, and per-file syntax-highlighted unified diffs styled with the IW brand palette
```

### AC5: Untracked artifacts preserved

```
Given an in-progress or completed-not-archived work item with a live worktree containing untracked non-source files (e.g., generated PDFs, scratch markdown, screenshots not in evidences/)
When the user expands the "Other worktree files" sub-panel inside the Files tab
Then untracked files (excluding evidences/, reports/, design-doc paths) are listed and previewable via the preserved /artifact-raw endpoint, matching the previous Artifacts tab's coverage for non-source worktree content
```

### AC6: Generated files auto-collapse

```
Given a diff that includes any file matching the generated-file glob list (uv.lock, package-lock.json, *.min.js, *.snap, pnpm-lock.yaml, yarn.lock, poetry.lock)
When the Files tab renders
Then those files appear in the tree but their diff cards are collapsed by default with a visible "Load full diff" affordance, regardless of how few total files are in the changeset
```

### AC7: Per-step diff captured by iw step-done

```
Given a workflow step that produces at least one git commit in its worktree
When `iw step-done` is invoked for that step
Then step_runs.diff_text is populated with the unified diff of `git diff HEAD^..HEAD` in the worktree, and step_runs.diff_summary is populated with the parsed file metadata; if no commit was produced, both columns are NULL with no error raised
```

### AC8: Aggregate diff captured at squash merge

```
Given the daemon's merge queue successfully creates a squash commit on `main` for a work item
When the post-merge hook runs (after the shell exits 0, before worktree reaping)
Then work_items.diff_text, diff_summary, and merge_commit_sha are populated with the squash commit's diff against its parent on `main`; capture failure does not roll back the merge but is logged as a daemon_events warning
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| Item with zero commits in worktree | active item, no commits yet | Files tab renders with "No changes yet" empty state, no error; tree empty; toolbar disabled |
| Item with worktree deleted but `merge_commit_sha` set | merged-not-archived | Resolver shells out to `git diff <sha>^..<sha>` in `project.repo_root`; tab renders normally |
| Step with no commit | step_run.diff_text IS NULL | Step appears in toolbar dropdown but selecting it shows "No changes captured for this step" |
| Diff resolver returns None for everything | nothing committed, no DB snapshot | Empty state with explanatory message; tree empty; toolbar reflects unavailable state |
| File > 5000 lines of unified diff | very large diff | File listed in tree with truncation badge; diff card shows "Diff too large for inline view — Download raw diff" with link to raw text endpoint |
| File between 500 and 5000 lines | medium diff | File auto-collapsed by default; "Show diff" toggle expands the card client-side (no server roundtrip — the diff is already in memory once `Diff2HtmlUI` rendered the aggregate response) |
| Renamed file with low similarity (treated as A+D) | git diff `--no-renames` would split | We honour git's default rename detection (similarity ≥ 50%); rename rendered as single row `old → new` |
| Binary file changed | git reports `Binary files differ` | Card renders "Binary file changed — N bytes" placeholder with no preview; counts as 1 file in summary, 0 added/0 removed |
| Untracked panel on archived item | worktree gone | Sub-panel hidden entirely (not rendered) |
| Filter input no matches | filter `xyz` | Tree shows "No files match filter"; diff cards all hidden; aggregate counters unchanged |
| `git diff` shell-out failure | git command exits non-zero | Resolver returns None; tab shows "Failed to compute diff: <reason>" inline error; daemon_events warning logged |
| Diff capture in step-done fails | git command errors after commit | step-done still succeeds (commits/marks-done are not rolled back); diff_text left NULL; warning logged |
| Diff capture in merge_queue fails | post-squash git diff errors | Merge stays committed; diff_text left NULL; daemon_events warning logged; user can re-derive via shell-out fallback while merge_commit_sha is set |
| Item with empty diff_summary list | no files changed (theoretical) | Empty state; same as zero commits |
| PDF export with diff > 5000 lines per file | large file in summary | PDF includes summary row + truncation note for that file; full content omitted |
| PDF export for item with > 100 changed files | very large changeset | PDF body includes per-file diffs for the first 100 files (alphabetical by path); the summary table at the top still lists all files; a footer note reads "…and N more files in the summary table only" |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. The Files tab is reachable via `GET /project/{pid}/item/{iid}/tab/files` for every work item, regardless of phase or archive state. The route is hardwired in `item_detail.html`, not gated by item state.
2. The legacy `/tab/artifacts` route returns 404 (or is removed from the FastAPI app entirely) — no old bookmark continues to function.
3. Removing the Artifacts route does not break any other tab. `/artifact-raw` remains functional and is referenced by the new untracked sub-panel.
4. `iw step-done` exit code and observable side effects are unchanged when diff capture fails (best-effort capture; never blocks the step lifecycle).
5. The daemon's squash-merge path is unchanged when diff capture fails (best-effort; never blocks the merge or rolls it back).
6. `step_runs` rows still satisfy the append-only convention: existing rows whose `status` was already terminal are never updated; new diff columns are written exactly once during the same `step-done` transaction that finalises the row.
7. Diff resolver returns None instead of raising when no source is available; UI handles None as an empty state.
8. Generated-file detection uses a single canonical glob list shared by frontend (auto-collapse logic) and backend (diff_summary `is_generated` flag) — no drift between the two.
9. The `dashboard/templates/fragments/item_artifacts.html` file is removed from the repo.
10. The new diff_text columns survive archival: archived items load diff from `work_items.diff_text` without touching the filesystem.

## Dependencies

- **Depends on**: None.
- **Blocks**: None.

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/diff_service.py`
- `orch/cli/step_commands.py`
- `orch/daemon/merge_queue.py`
- `dashboard/routers/items.py`
- `dashboard/templates/pages/project/item_detail.html`
- `dashboard/templates/fragments/item_files.html`
- `dashboard/templates/fragments/item_files_untracked.html`
- `dashboard/templates/fragments/item_artifacts.html`
- `dashboard/templates/components/libs/diff2html.html`
- `dashboard/templates/exports/diff_pdf.html`
- `dashboard/static/styles.css`
- `dashboard/static/files.js`
- `pyproject.toml`
- `uv.lock`
- `tests/unit/test_diff_service.py`
- `tests/unit/test_artifact_browser.py`
- `tests/integration/test_files_tab.py`
- `tests/integration/test_diff_capture.py`
- `tests/dashboard/browser/test_files_tab.py`

## TDD Approach

- **Unit tests** (`tests/unit/test_diff_service.py`):
  - Resolver routing: archived → DB; merged-not-archived → shell-out to repo_root; in-progress → shell-out to worktree; step provided → step_runs.diff_text fallback to live worktree diff; nothing available → None.
  - unidiff parsing: A / M / D / R statuses; rename detection collapses to single entry; binary file flag; generated-file flag detection against canonical glob list; counts of added/removed lines.
  - Generated-file glob list invariant: same definition used by backend and frontend (assert importable from one source of truth).
- **Integration tests** (`tests/integration/test_files_tab.py`, `test_diff_capture.py`):
  - PostgreSQL testcontainer fixture (replace `psycopg2://` → `psycopg://`, run FTS DDL after `create_all`).
  - Migration applies cleanly forward and back (autogenerated revision exercise).
  - `iw step-done` writes diff_text and diff_summary when a commit exists in the temp worktree; writes NULL when no commit; never raises when git fails.
  - Aggregate capture hook in merge_queue: simulate a squash on a fixture repo and assert work_items.diff_text/diff_summary/merge_commit_sha are populated; failure path leaves columns NULL and emits a daemon_events warning.
  - FastAPI TestClient: Files tab returns 200 with the expected fragment for active / completed / archived items; `/files/diff?step=all` returns text/plain unified diff; `/files/untracked` returns JSON only for live-worktree items; `/files/export.pdf` returns `application/pdf` with non-empty body; `/tab/artifacts` returns 404.
  - Generated-file auto-collapse flag round-trip: diff_summary entries match the canonical glob list.
- **Browser-smoke tests** (`tests/dashboard/browser/test_files_tab.py`):
  - Use `playwright-cli` against the running dashboard; navigate to a known item; click Files tab; assert tree visible, at least one diff card rendered; click step dropdown, select a non-aggregate step, confirm only that step's files appear; expand the "Other worktree files" sub-panel and confirm at least one untracked entry; click "Export PDF" and confirm a download is triggered.
- **Edge cases**: empty diff state, very large file truncation (>5000 lines), binary file placeholder, untracked panel hidden on archived item, dark-mode color-scheme sync.

## Notes

- The diff2html-ui slim bundle (~100 KB gzipped) MUST be vendored under `dashboard/static/vendor/diff2html/` and served from there — no CDN. This matches the existing pattern of vendored per-page JS libs (Highlight.js, DOMPurify, Mermaid) and is required for offline / air-gapped environments.
- PDF item-level cap: when an item touches more than 100 changed files, the PDF body renders per-file diffs only for the first 100 (alphabetical by path); the summary table at the top still lists every file, and a footer note states the count of files omitted from the body. This caps WeasyPrint render time and final PDF size to a sensible bound.
- The squash merge happens in `executor/worktree_commit.sh` (shell), not Python. The Python hook in `orch/daemon/merge_queue.py` runs after the shell exits 0 — that is the correct insertion point for `git diff <merge_sha>^..<merge_sha>` against `project.repo_root`. The shell does NOT need to be modified.
- `unidiff` is the chosen Python parser (MIT, stable, low transitive deps). It will be added to `pyproject.toml` and pinned via `uv lock`.
- WeasyPrint is already an installed dependency (`dashboard/routers/docs.py:169`). PDF export does not introduce a new heavy dependency.
- Append-only safety: existing `iw step-done` already updates the in-flight `step_run` row's `status`, `completed_at`, `duration_secs`, `report_file`, `log_content` (all populated during the same transaction that finalises the row). Adding `diff_text` and `diff_summary` writes during this same transaction is consistent with that pattern. No retroactive updates of terminal rows are introduced.
- Risk: agents in S04/S05/S06 must coordinate on the contract for `/files/diff` (raw diff text vs JSON envelope). The chosen contract is **raw `text/plain` body** so the frontend can pass it directly to `Diff2HtmlUI.draw`. JSON is reserved for `/files/untracked` and the diff_summary metadata that the tab shell needs.
- Risk: removing `_list_artifact_tree` and related helpers in `dashboard/routers/items.py` requires checking that no other tab uses them. Quick grep at S04 time will confirm.
- Removal coordination on `tests/unit/test_artifact_browser.py`: the existing test file (319 lines) has three classes — `TestDetectFileType`, `TestResolveArtifactRoot`, `TestBuildArtifactTree`. `_detect_file_type` and `_resolve_artifact_root` MUST be preserved because the preserved `/artifact-raw` route (`item_artifact_raw` at `dashboard/routers/items.py:1135`) depends on them. Only the `TestBuildArtifactTree` class is deleted (alongside the `_build_artifact_tree`, `_list_artifact_tree`, and `ArtifactNode` helpers). The S05 prompt encodes this contract.
