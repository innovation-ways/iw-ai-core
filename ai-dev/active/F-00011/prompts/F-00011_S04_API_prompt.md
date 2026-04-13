# F-00011_S04_API_prompt

**Work Item**: F-00011 — Project-Level Documentation System — Foundation (Phase 1)
**Step**: S04
**Agent**: API

---

## Input Files

- `ai-dev/active/F-00011/F-00011_Feature_Design.md` — Design document (read the CLI Contract section fully)
- `ai-dev/work/F-00011/reports/F-00011_S01_Database_report.md` — S01 report
- `ai-dev/work/F-00011/reports/F-00011_S02_Backend_report.md` — S02 report
- `orch/cli/` — Existing CLI command files for style reference
- `orch/cli/step_commands.py` — Primary reference for how `iw` commands call `DocService` / DB
- `CLAUDE.md` and `orch/CLAUDE.md` — Project rules

## Output Files

- `orch/cli/doc_commands.py` — New CLI command module
- `orch/cli/main.py` — Register new `doc` command group
- `ai-dev/work/F-00011/reports/F-00011_S04_API_report.md` — Step report

## Context

You are implementing the `iw doc-update` CLI command for **F-00011: Project-Level Documentation System**.

This command is the primary interface for AI agents (and humans) to write documentation content into the platform's database. It must be rock-solid: clear error messages, correct exit codes, idempotent, and well-tested.

Read `orch/cli/step_commands.py` and other CLI command files thoroughly before writing any code — match the exact patterns used (Click group, session management, error handling, output format).

## Requirements

### 1. Create `orch/cli/doc_commands.py`

Create a Click command group `doc` with a single command `update`.

```
iw doc-update PROJECT_ID DOC_ID [OPTIONS]
```

(The command is `iw doc-update` — a flat, hyphenated command consistent with existing CLI commands `iw step-done`, `iw batch-approve`, `iw item-status`. Do NOT use nested subcommand grouping. Register as a top-level Click command.)

**Arguments:**
- `PROJECT_ID` — required positional argument (string)
- `DOC_ID` — required positional argument (string)

**Options (all optional):**

| Option | Type | Description |
|--------|------|-------------|
| `--title TEXT` | str | Document title |
| `--slug TEXT` | str | URL-safe slug (auto-derived from title if omitted) |
| `--doc-type` | Choice[DocType values] | Document type enum value |
| `--tier` | Choice[DocTier values] | Automation tier |
| `--editorial-category` | Choice[EditorialCategory values] | Editorial category |
| `--status` | Choice[DocStatus values] | Document status |
| `--audience TEXT` | str | Comma-separated audience list (e.g., "architects,senior-developers") |
| `--source-paths TEXT` | str | Comma-separated source file paths |
| `--content TEXT` | str | Markdown content inline (mutually exclusive with `--content-file`) |
| `--content-file PATH` | Path | Path to markdown file; use `-` for stdin |
| `--generated-by TEXT` | str | Generator identifier (e.g., "skill:iw-doc-generator") |
| `--trigger-reason TEXT` | str | Reason stored in version snapshot |
| `--version INTEGER` | int | Override version number (default: auto-increment) |

**Mutual exclusivity**: `--content` and `--content-file` are mutually exclusive. If both provided, print error and exit with code 2.

**Content from stdin**: When `--content-file -` is provided, read from `sys.stdin`. Handle encoding correctly (UTF-8).

**Content size limit**: After reading content (from `--content`, `--content-file`, or stdin), check `len(content.encode("utf-8")) > 10 * 1024 * 1024`. If exceeded, print error to stderr and exit with code 2: `"Content exceeds maximum size (10 MB)"`.

### 2. Command Logic

```
1. Validate mutually exclusive options
2. Open DB session (same pattern as other CLI commands)
3. Look up project — if not found, print error to stderr, exit 1
4. Parse --audience as comma-separated list → List[str] (strip whitespace)
5. Parse --source-paths as comma-separated list → List[str] (strip whitespace)
6. Read content from --content or --content-file (or None if neither provided)
7. Call DocService.upsert_doc() with all provided fields
8. Print result as JSON to stdout:
   {
     "doc_id": "{project_id}:{doc_id}",
     "project_id": "{project_id}",
     "version": <int>,
     "status": "<status>",
     "snapshot_created": <bool>
   }
9. Exit 0
```

**Exit codes:**
- `0` — success
- `1` — project not found
- `2` — validation error (bad arguments, mutual exclusivity)
- `3` — database error (unexpected)

**Output**: Always JSON to stdout on success. Errors go to stderr (not stdout). This allows agent callers to parse stdout reliably.

### 3. Register in `orch/cli/main.py`

Add the `doc_update` command to the main `iw` CLI as a top-level command (same as `step_done`, `batch_approve`). Look at how other command modules are imported and added to the `iw` Click group, and follow the exact same pattern.

### 4. Wire DocService

The CLI command must import and use `DocService` from S02. Do not duplicate any DB logic in the CLI layer — all business logic stays in the service.

## Project Conventions

Read `orch/CLAUDE.md` and look at existing CLI files. Key points:
- Session management: how does `step_commands.py` open and close the DB session? Match exactly.
- Output format: does the project use `click.echo(json.dumps(...))` or `print()`? Match.
- Error handling: does it use `sys.exit()` or Click's `ctx.exit()`? Match.
- Import style: absolute imports within the `orch` package

## TDD Requirement

Write tests in `tests/unit/test_doc_commands.py` and/or `tests/integration/test_doc_commands.py`:

- `test_doc_update_creates_new_doc` — invoke CLI via `click.testing.CliRunner`, assert JSON output and DB record
- `test_doc_update_updates_existing_doc` — second call with different content, assert version incremented
- `test_doc_update_unknown_project_exits_1` — assert exit code 1 and error to stderr
- `test_doc_update_mutual_exclusion_exits_2` — both `--content` and `--content-file` → exit code 2
- `test_doc_update_content_from_stdin` — pipe content via stdin
- `test_doc_update_content_from_file` — write temp file, pass via `--content-file`
- `test_doc_update_idempotent_same_content` — same content twice → version stays at 1, `snapshot_created: false`
- `test_doc_update_audience_parsed` — `--audience "architects,senior-developers"` → list stored correctly
- `test_doc_update_source_paths_parsed` — `--source-paths "docs/arch.md,docs/api.md"` → list stored correctly

Use `CliRunner(mix_stderr=False)` to test stdout and stderr separately.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all tests must pass
2. `make quality` — ruff + mypy must pass

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "API",
  "work_item": "F-00011",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/doc_commands.py",
    "orch/cli/main.py",
    "tests/unit/test_doc_commands.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
