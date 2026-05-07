# F-00079_S09_Tests_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S09
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers in pytest fixtures are EXEMPT — they self-label and self-destruct via Ryuk.

## ⛔ Migrations: agents generate, daemon applies

Run migrations only inside testcontainer fixtures. Do NOT run alembic against the live DB.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00079 --json`
- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- All previous step reports (S01..S08)
- `tests/CLAUDE.md` — testing rules and conventions
- `tests/conftest.py` — fixture conventions, FTS DDL, testcontainer setup
- `tests/dashboard/browser/` — existing playwright-cli browser tests for reference

## Output Files

- New / extended: `tests/unit/test_diff_service.py`
- New: `tests/integration/test_files_tab.py`
- New: `tests/integration/test_diff_capture.py`
- New: `tests/dashboard/browser/test_files_tab.py`
- `ai-dev/active/F-00079/reports/F-00079_S09_Tests_report.md`

## Context

You are writing the test suite for **F-00079: Files view**. Coverage must satisfy **every** Acceptance Criterion (AC1..AC8) and **every** Boundary Behavior row in the design document. Read both fully before writing tests.

## Critical Test Rules (`tests/CLAUDE.md`)

- **NEVER** connect tests to the live DB on port 5433 — testcontainers only.
- **NEVER** mock the database in integration tests — FOR UPDATE locking can't be tested otherwise.
- **NEVER** call `importlib.reload(orch.config)` in tests — use `monkeypatch.delenv()` instead.
- **MUST** replace psycopg2 URLs from testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests (raw DDL is not captured by `create_all`).
- `DaemonEvent.metadata` is `event_metadata` in Python.

## Requirements

### 1. Unit tests — `tests/unit/test_diff_service.py`

Extend the smoke tests from S03 with full coverage:

- `parse_diff_summary` — fixture diffs covering: pure add, pure delete, modify, rename (≥50% similarity), binary file (Pygments-unfriendly), generated file (uv.lock), file with mixed adds/deletes; assert returned summary list shape and all fields.
- `is_generated_path` — every entry in `GENERATED_FILE_GLOBS` matches; false for normal source paths.
- `resolve_diff` branches:
  - step provided + `step_run.diff_text` set → returns the stored text without shelling out.
  - step provided + `step_run.diff_text` NULL + worktree alive → shells out.
  - aggregate, archived item → returns `work_items.diff_text`.
  - aggregate, merged-not-archived → shells out to `project.repo_root` against `merge_commit_sha`.
  - aggregate, in-progress with worktree → shells out to worktree.
  - nothing available → returns None.
- Subprocess failure injection (e.g., monkeypatch `subprocess.run` to return non-zero) → resolver returns None, never raises.

### 2. Integration tests — `tests/integration/test_diff_capture.py`

Use a temporary on-disk git repo (NOT the orchestration DB testcontainer for git ops; spin up a `tmp_path` with `git init`) plus the PostgreSQL testcontainer for ORM:

- Per-step capture in `iw step-done`:
  - Make a commit in a temp worktree, run `step-done`, assert `step_runs.diff_text` populated and `diff_summary` matches expected files.
  - No commit in the worktree → `diff_text` and `diff_summary` remain NULL; `step-done` exits 0.
  - Inject a git command failure → `step-done` still exits 0; columns NULL; warning logged (use `caplog`).
- Aggregate capture in `merge_queue.py`:
  - Simulate a successful squash on a fixture repo, invoke the post-merge hook, assert `work_items.diff_text/diff_summary/merge_commit_sha` populated.
  - Inject a git failure → merge stays committed (not rolled back); columns NULL; `daemon_events` row of type `diff_capture_failed` exists.

### 3. Integration tests — `tests/integration/test_files_tab.py`

FastAPI TestClient against a freshly-created app instance with a testcontainer DB. Cover:

- AC1: `GET /tab/files` for an active item with a worktree returns 200 and the fragment includes status badges + +N −M elements.
- AC2: `GET /files/diff?step=<step_id>` returns text/plain with only that step's diff content; `step=all` returns the aggregate.
- AC3: `GET /tab/files` for an archived item (worktree dir removed) returns 200 and the diff comes from `work_items.diff_text` (assert no shell-out by inspecting `caplog` or by patching `subprocess.run` to fail and confirming the response still succeeds).
- AC4: `GET /files/export.pdf?step=all` returns `application/pdf` with a non-empty body (>1 KB sanity check).
- AC5: `GET /files/untracked` returns the expected JSON for a live worktree; for archived item returns `{"files": []}` with the disabled header.
- AC6: a diff containing `uv.lock` produces a `diff_summary` entry with `is_generated=true`.
- AC7: confirmed via test_diff_capture.py.
- AC8: confirmed via test_diff_capture.py.
- `GET /tab/artifacts` returns 404 (Invariant 2).
- `GET /artifact-raw?path=...` continues to work (Invariant 3).

### 4. Boundary tests — incorporate every row from the design document's Boundary Behavior table

Either as standalone tests or as parametrize cases:
- Item with zero commits → empty state.
- Worktree deleted but `merge_commit_sha` set → resolver shells out to repo_root.
- Step with no commit.
- Diff resolver returns None for everything.
- File >5000 lines → tree shows truncation badge; diff card empty / "Download raw diff".
- File 500–5000 lines → auto-collapse with htmx load-on-click button.
- Renamed file with low similarity (verify behaviour matches default git rename detection).
- Binary file changed → placeholder, no preview.
- Untracked panel on archived item → not rendered.
- Filter no matches → "No files match" empty state.
- `git diff` shell-out failure → resolver None, inline error in tab.
- Empty `diff_summary` → empty state.
- PDF export with file >5000 lines → summary shows "Diff omitted" note.
- PDF export for an item with >100 changed files → response body is non-empty `application/pdf`; the rendering route partitions files alphabetical-by-path; first 100 go to `summary_files` with `hunks_html` populated, the rest go to `truncated_files` with `hunks_html=None`. Assert via the route's render-context (e.g., monkeypatch the template render to capture the context, OR inspect the resulting PDF text via `pdfminer.six` for the "N additional files omitted" footer note). Acceptable shortcut: build a synthetic `summary_files` list of 105 entries, call the route's PDF helper directly, and assert `len(summary_files) == 100` and `len(truncated_files) == 5`.
- Per-file client-side collapse: `tests/dashboard/browser/test_files_tab.py` clicks "Show diff" / "Hide diff" on a `data-large="true"` card and asserts NO `/files/diff` request fires (the toggle is purely a CSS class flip). Use `playwright-cli`'s network-trace capability or count requests before/after.

### 5. Browser smoke test — `tests/dashboard/browser/test_files_tab.py`

Use `playwright-cli` (per `CLAUDE.md`):

```bash
playwright-cli kill-all
playwright-cli open <dashboard_url>
playwright-cli snapshot
playwright-cli click <Files-tab-ref>
# Assertions: tree visible, at least one diff card rendered
playwright-cli click <step-dropdown-ref>
# Select a non-aggregate step
# Assertions: only that step's files appear
playwright-cli click <Other-worktree-files-ref>
# Assertions: untracked list visible, preview works
# Click Export PDF; assert a download starts (verify by checking response headers in TestClient if pure browser is awkward)
```

Match the existing browser-test pattern (e.g., `tests/dashboard/browser/test_chat_scroll_i00060.py` for reference).

### 6. Generated-file glob list invariance

A dedicated unit test that imports the canonical `GENERATED_FILE_GLOBS` from `orch.diff_service` and asserts the same list (or a documented subset) is referenced by the JS-bundled inline list. The simplest implementation: parse `dashboard/static/files.js` for the literal array and assert equality with the Python tuple.

## Project Conventions

Read `tests/CLAUDE.md` exhaustively. Key reminders:
- Conftest fixtures already exist for testcontainer + base session; reuse them.
- FTS DDL must run after `create_all`.
- Tests must be deterministic and isolated; never depend on order.
- Naming: `test_<module>_<scenario>` for unit; `test_<feature>_<flow>` for integration.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all green.
2. `make test-integration` — all green.
3. `make test-frontend` — all green.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "tests-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_diff_service.py",
    "tests/integration/test_files_tab.py",
    "tests/integration/test_diff_capture.py",
    "tests/dashboard/browser/test_files_tab.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X unit, Y integration, Z frontend, 0 failed",
  "blockers": [],
  "notes": ""
}
```
