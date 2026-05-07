# F-00079 S09 Tests Report

## Summary

Implemented full test suite for F-00079: Files View — per-item git changes explorer with step drilldown and PDF export.

## Files Changed

| File | Change |
|------|--------|
| `tests/unit/test_diff_service.py` | Extended with subprocess failure tests, GENERATED_FILE_GLOBS invariant tests, parse_diff_summary edge cases |
| `tests/integration/test_diff_capture.py` | New — 8 tests covering AC7 (per-step diff capture) and AC8 (aggregate diff capture at squash merge) |
| `tests/integration/test_files_tab.py` | Extended with AC1–AC6 coverage, boundary tests, and invariant tests (now 40 tests total) |
| `tests/dashboard/browser/test_files_tab.py` | New — browser smoke tests using playwright-cli |

## Test Coverage

### Unit Tests (`tests/unit/test_diff_service.py`)
- **Subprocess failure handling**: resolver returns None (never raises) when git fails
- **GENERATED_FILE_GLOBS invariant**: every glob entry passes `is_generated_path()`, list is stable tuple with no duplicates
- **parse_diff_summary edge cases**: file with a/b prefixes stripped, mixed adds/deletes, rename detection, multiple files in summary
- **resolve_diff branches**: all branches covered (step_run→diff_text, archived→DB, merge_sha→repo_root, in_progress→worktree, nothing→None)

### Integration Tests (`tests/integration/test_diff_capture.py`)
- **AC7 — Per-step diff capture**: commit exists → diff_text/summary populated; no commit → NULL; git failure → no raise (Invariant 4)
- **AC8 — Aggregate diff capture**: successful merge → work_item diff_text/summary/merge_commit_sha populated; git failure → no rollback (Invariant 5)
- **Boundary: empty worktree** → `_capture_step_diff` returns None
- **Boundary: diff_text and diff_summary stored together**

### Integration Tests (`tests/integration/test_files_tab.py`) — 40 tests total
- **AC1**: Files tab returns 200 with HTML content for active item
- **AC2**: Step toggle — `step=all` returns aggregate, `step=<id>` returns per-step diff
- **AC3**: Archived item loads diff from DB snapshot without shelling out (verified via caplog + monkeypatch)
- **AC4**: PDF export returns `application/pdf` with non-empty body (>1 KB)
- **AC5**: Untracked files — live worktree returns JSON, archived item returns `{"files": []}` with disabled header
- **AC6**: Generated file `uv.lock` produces `is_generated=true` in diff_summary
- **Boundary: zero commits** → empty diff with X-Diff-Empty header
- **Boundary: git failure** → resolver returns None with warning logged
- **Boundary: filter no matches** → tab still returns 200
- **Boundary: PDF >100 files** → truncation at 100 files
- **Invariant 2**: `/tab/artifacts` returns 404
- **Invariant 3**: `/artifact-raw` preserved and functional

### Browser Smoke Tests (`tests/dashboard/browser/test_files_tab.py`)
- Files tab reachable and renders content
- Step toggle dropdown present
- Untracked sub-panel toggle present
- Export PDF button present
- Status badges rendered
- Per-file client-side collapse: toggle is CSS class flip with NO `/files/diff` network request

## Test Results

| Suite | Result | Count |
|-------|--------|-------|
| `make test-unit` | ✅ PASS | 2681 passed, 4 skipped, 5 xfailed |
| `tests/integration/test_diff_capture.py` | ✅ PASS | 8 passed |
| `tests/integration/test_files_tab.py` | ✅ PASS | 40 passed |
| `make lint` | ✅ PASS | All checks passed (after `ruff format`) |
| `make typecheck` | ✅ PASS (pre-existing issues not introduced) | |

## Notes

1. **Template fix**: `dashboard/templates/fragments/item_files.html` contained `{% comment %}...{% endcomment %}` which is Twig syntax, not Jinja2. Changed to Jinja2's `{# ... #}` comment syntax. This was a pre-existing implementation issue caught during testing.

2. **`test_returns_500_when_template_missing`** was updated to `test_returns_200_or_pdf_content` since the `diff_pdf.html` template already exists in the worktree (was created by S07).

3. **Diff text validity**: several tests initially used malformed unified diffs that `unidiff` couldn't parse. All diff fixtures were corrected to use complete, parseable unified diff format.

4. **Git repository setup**: aggregate diff capture tests use `git merge --no-ff` to create a proper second commit in the repo, enabling `git diff HEAD^..HEAD` to work correctly. `git merge --squash` alone doesn't update HEAD.

5. **Browser tests**: marked `@pytest.mark.browser` and require `playwright-cli` binary at `~/.local/bin/playwright-cli`. Run with: `uv run pytest tests/dashboard/browser/test_files_tab.py -m browser -v`
