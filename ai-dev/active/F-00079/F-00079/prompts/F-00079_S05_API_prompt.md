# F-00079_S05_API_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S05
**Agent**: api-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Migration was added in S01 and applied by the daemon. Do not run alembic against the live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/reports/F-00079_S01_Database_report.md`, `F-00079_S03_Backend_report.md`
- `dashboard/routers/items.py` — current router (Files routes go here)
- `dashboard/routers/docs.py:169` and `:861` — example WeasyPrint integration to reuse
- `orch/diff_service.py` — resolver and parser created in S03

## Output Files

- Modified: `dashboard/routers/items.py`
- Modified: `tests/unit/test_artifact_browser.py` (delete the `TestBuildArtifactTree` class only — see §5)
- `ai-dev/active/F-00079/reports/F-00079_S05_API_report.md`

## Context

You are adding the API surface for **F-00079: Files view**. Four new routes plus removal of one legacy route. Routers must remain thin — call the resolver in `orch/diff_service.py`, do not embed logic. Read `dashboard/CLAUDE.md` for routing patterns and the htmx fragment convention.

## Requirements

### 1. New: `GET /project/{project_id}/item/{item_id}/tab/files`

Renders the Files tab shell as an HTML fragment (NOT extending `base.html`).

- Returns 200 with the fragment `dashboard/templates/fragments/item_files.html` (S06 will create this template).
- Fragment context:
  - `item: WorkItem`
  - `project_id: str`
  - `summary: list[dict]` — parsed from `diff_summary` if present (live or stored), else from a fresh `parse_diff_summary(resolve_diff(...))`. List of file metadata for the **aggregate** view.
  - `step_options: list[dict]` — list of `{step_id, step_name, has_diff: bool}` for the toolbar dropdown, derived from the item's completed step_runs.
  - `worktree_alive: bool` — drives whether the untracked sub-panel renders.
  - `is_archived: bool`
  - `aggregate_added: int`, `aggregate_removed: int`, `aggregate_file_count: int`
  - `default_expand_all: bool` — `True` when `len(summary) <= 10`, else `False`.
- 404 if the item does not exist.

### 2. New: `GET /project/{project_id}/item/{item_id}/files/diff?step=<all|step_id>`

Returns raw unified diff text as `text/plain; charset=utf-8` for the requested scope.

- `step=all` → aggregate diff via `resolve_diff(item=..., step_run=None, ...)`.
- `step=<numeric_step_id>` → step-scoped diff via `resolve_diff(item=..., step_run=<looked-up StepRun>, ...)`.
- Returns 200 with the diff text; if resolver returns None, return 200 with empty body and a `X-Diff-Empty: 1` header so the client can render the empty state.
- 400 if `step` value is malformed.
- 404 if item or step_run does not exist.
- Uses `Response` with explicit `media_type="text/plain"` (no JSON wrapping).

### 3. New: `GET /project/{project_id}/item/{item_id}/files/untracked`

Returns a JSON list of untracked worktree files for the live-worktree case.

- 200 with `{"files": [{"path": str, "size_bytes": int, "file_type": str}, ...]}` when the worktree is alive.
- 200 with `{"files": []}` and a `X-Untracked-Disabled: archived` header when the item is archived.
- Uses `git status --porcelain -uall` filtered to status `??` and excludes paths under `ai-dev/active/<ITEM>/evidences/`, `ai-dev/active/<ITEM>/reports/`, and the design-doc path (those are owned by other tabs).
- 404 if item does not exist.

### 4. New: `GET /project/{project_id}/item/{item_id}/files/export.pdf?step=<all|step_id>`

Returns a WeasyPrint-rendered PDF.

- Looks up the diff via `resolve_diff(...)` and parsed summary via `parse_diff_summary(...)`.
- Renders the Jinja template `dashboard/templates/exports/diff_pdf.html` (S07 will create this). Template context (single canonical shape — keep names aligned with S07):
  - `item: WorkItem`, `project_id: str`, `step_label: str`, `aggregate_added: int`, `aggregate_removed: int`, `aggregate_file_count: int`.
  - `summary_files: list[dict]` — every file in the changeset, each entry carrying `{path, status, added, removed, is_generated, is_binary, old_path, hunks_html}`. `hunks_html` is the Pygments-rendered HTML of the file's unified diff hunks (already `Markup`-safe; pre-rendered in this route, NOT in the template). For binary files, files ≥5000 lines, and files outside the body cap (see below), `hunks_html` is `None` and the template renders the appropriate placeholder instead.
  - `truncated_files: list[dict]` — files past the body cap (alphabetical-by-path index ≥100); summary table still includes them, body section omits them. Empty list when item has ≤100 files.
- Apply the **PDF item-level cap**: render full `hunks_html` for the first 100 files alphabetical-by-path; the rest go into `truncated_files` (summary-only) and a footer note states the count.
- Pipes the rendered HTML to WeasyPrint following the pattern in `dashboard/routers/docs.py:169`/`:861`.
- Returns 200 with `Content-Type: application/pdf`, `Content-Disposition: attachment; filename="<item_id>_files_<step>.pdf"`, and the PDF bytes as the body.
- 404 if item does not exist; 500 with a clear error if WeasyPrint fails (do not silently fall back to HTML).

### 5. Remove: `GET /project/{project_id}/item/{item_id}/tab/artifacts`

- Delete the `item_tab_artifacts` route handler at `dashboard/routers/items.py:1094-1117`.
- Quick `grep` to confirm no other code references `_list_artifact_tree`, `_build_artifact_tree`, or `ArtifactNode`. If only the removed route uses them, delete the helpers and the `ArtifactNode` dataclass too. If anything else uses them (e.g., the untracked panel's `/artifact-raw` endpoint), keep them.
- **PRESERVE** `_detect_file_type` (`dashboard/routers/items.py:115`) and `_resolve_artifact_root` (`dashboard/routers/items.py:147`) — both are used by the preserved `item_artifact_raw` route handler (`dashboard/routers/items.py:1135`). Do NOT delete them when pruning the tree helpers.
- Do NOT remove `/artifact-raw` (`item_artifact_raw` at line 1120) — it is reused by the new untracked sub-panel for previewing files.
- **Update `tests/unit/test_artifact_browser.py`**: this 319-line test file has three classes — `TestDetectFileType`, `TestResolveArtifactRoot`, and `TestBuildArtifactTree`. Delete ONLY the `TestBuildArtifactTree` class (around line 145..end-of-file). Keep `TestDetectFileType` and `TestResolveArtifactRoot` intact — they cover the helpers that the preserved `/artifact-raw` endpoint depends on. After the edit, run `make test-unit` and confirm the file's remaining tests still pass.
- Update Invariant 2 confirmation: a request to `/tab/artifacts` returns 404.

### 6. Wire endpoints to the router

The new endpoints should sit near the existing `item_tab_*` handlers. Maintain the existing decorator/return-type conventions (`response_class=HTMLResponse` for the tab shell, `Response` with explicit `media_type` for the diff and PDF endpoints).

## Project Conventions

Read `dashboard/CLAUDE.md`:
- Routers are thin — validation + delegation only. Diff resolution lives in `orch/diff_service.py`, NEVER inline in the route.
- htmx fragments under `templates/fragments/` MUST NOT extend `base.html`.
- Use `request.app.state.templates` for `Jinja2Templates`.
- `dependencies.py:get_db()` provides the DB session.

`CLAUDE.md`:
- Use `playwright-cli` only for browser tests (S09's concern, not yours).
- Append plain CSS to `dashboard/static/styles.css` if Tailwind CLI cannot run.

## TDD Requirement

Routes are exercised via FastAPI TestClient in S09. For your step, write at least:
- One smoke test per route in `tests/integration/test_files_tab.py` (file may already exist after S03 — extend it, or create a stub) checking that the route returns the expected status code and content type. Full coverage of edge cases is S09's responsibility.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration` (smoke; full integration suite owned by S09)

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py",
    "tests/unit/test_artifact_browser.py",
    "tests/integration/test_files_tab.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
