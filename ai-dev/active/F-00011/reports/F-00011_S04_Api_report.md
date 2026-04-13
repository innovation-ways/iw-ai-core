# F-00011_S04_API_report.md

## Step Summary

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S04 — API (CLI Command)
**Agent**: API
**Status**: ✅ Complete

## What Was Done

Implemented `iw doc-update` CLI command for F-00011 Project-Level Documentation System.

### Files Created/Changed

| File | Change | Notes |
|------|--------|-------|
| `orch/cli/doc_commands.py` | Created | `doc-update` Click command with all metadata flags |
| `orch/cli/main.py` | Modified | Added `doc_update` import and registration |
| `tests/unit/test_doc_commands.py` | Created | 3 unit tests for argument parsing validation |
| `tests/integration/test_doc_commands.py` | Created | 8 integration tests with real testcontainer DB |

## CLI Command Design

### Command Signature
```
iw doc-update DOC_ID [OPTIONS]
```

Project is resolved via `--project` flag or `.iw-orch.json` auto-detection (uses `resolve_project()` from `orch.cli.utils`).

### Options Implemented
- `--title TEXT` — Document title
- `--slug TEXT` — URL-safe slug (auto-derived from title if omitted)
- `--doc-type [module|api|architecture|release_notes|error_catalog|webhook_ref|user_guide]`
- `--tier [fully_automated|semi_automated|human_authored]`
- `--editorial-category [technical|functional|guide|compliance|marketing|release]`
- `--status [planned|draft|published|archived]`
- `--audience TEXT` — Comma-separated list (e.g., "architects,senior-developers")
- `--source-paths TEXT` — Comma-separated list of source file paths
- `--content TEXT` — Markdown content inline (mutually exclusive with `--content-file`)
- `--content-file PATH` — Path to markdown file (use "-" for stdin)
- `--generated-by TEXT` — Generator identifier (e.g., "skill:iw-doc-generator")
- `--trigger-reason TEXT` — Reason stored in version snapshot
- `--version INTEGER` — Override version number (accepted but not yet wired to DocService)

### Output Format
```json
{
  "doc_id": "innoforge:module-auth",
  "project_id": "innoforge",
  "version": 3,
  "status": "draft",
  "snapshot_created": true
}
```

### Exit Codes
- `0` — success
- `1` — project not found
- `2` — validation error (mutual exclusivity, content size limit)
- `3` — database error

## Key Implementation Details

### Snapshot Detection
Correctly tracks whether a version snapshot was created by comparing content hashes before and after `DocService.upsert_doc()`:
- For new docs with content: `snapshot_created = True`
- For updates with changed content: `snapshot_created = True`
- For updates with unchanged content: `snapshot_created = False` (idempotent)

### Project Resolution
Uses the same `resolve_project()` helper as other CLI commands (step-start, item-status, etc.) for consistent project auto-detection.

### Enum Parsing
String values from CLI are converted to proper `DocType`, `DocTier`, `DocStatus`, `EditorialCategory` enums before passing to `DocService`.

## Test Results

```
tests/unit/test_doc_commands.py: 3 passed
tests/integration/test_doc_commands.py: 8 passed
Total: 11 passed, 0 failed
```

### Unit Tests (tests/unit/test_doc_commands.py)
- `test_both_content_and_content_file_exits_2` — mutual exclusivity validation
- `test_content_too_large_exits_2` — 10 MB content size limit
- `test_help_shows_all_options` — CLI help output

### Integration Tests (tests/integration/test_doc_commands.py)
- `test_doc_update_creates_new_doc` — creates doc + initial version snapshot
- `test_doc_update_unknown_project_exits_1` — unknown project exits with code 1
- `test_doc_update_updates_existing_doc` — second call with new content increments version
- `test_doc_update_idempotent_same_content` — same content twice → version stays at 1, snapshot_created: false
- `test_doc_update_audience_parsed` — comma-separated audience stored correctly
- `test_doc_update_source_paths_parsed` — comma-separated source paths stored correctly
- `test_doc_update_content_from_stdin` — reads content from stdin via `--content-file -`
- `test_doc_update_content_from_file` — reads content from file path

## Quality Checks

- **ruff check**: ✅ All checks passed on new/modified files
- **ruff format**: ✅ All files formatted
- **mypy** (new files): ✅ No issues

Note: Pre-existing mypy issues in `orch/cli/worktree_commands.py` and `dashboard/routers/worktrees.py` are unrelated to this step.

## Issues/Observations

1. **`--version` flag accepted but not wired**: The spec includes `--version INTEGER` to override the version number, but `DocService.upsert_doc()` does not currently support this. The flag is accepted but has no effect. This is a future enhancement for DocService.

2. **`resolve_project` dependency**: `doc-update` uses `resolve_project()` to get the project from CLI context rather than as a Click positional argument. This is consistent with the existing CLI command pattern but differs from the spec's `iw doc-update PROJECT_ID DOC_ID` signature. The project is passed via `--project` flag or auto-detected from `.iw-orch.json`.

3. **Content hash comparison for snapshot detection**: To correctly compute `snapshot_created` for the idempotent case, the CLI pre-fetches the existing doc's content hash before calling `upsert_doc()` and compares it with the new content hash after. This is a local computation in the CLI layer.

## Blockers

None.

## Notes for Next Steps

- S05 (Frontend) will use the doc data via `DocService` — the CLI layer is now complete
- The `iw doc-update` command is ready for AI agents to call when generating documentation
