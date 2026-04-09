# F-00001_S01_Backend_prompt

**Work Item**: F-00001 -- Batch Archive with Post-Merge Actions
**Step**: S01
**Agent**: Backend

---

## Input Files

- `ai-dev/design/active/F-00001/F-00001_Feature_Design.md` -- Design document

## Output Files

- `ai-dev/work/F-00001/reports/F-00001_S01_Backend_report.md` -- Step report

## Context

You are implementing the batch archiver service for **Batch Archive with Post-Merge Actions**.

Read the design document first to understand the full scope and your step's deliverables. Then read `CLAUDE.md` for project-specific patterns and conventions.

## Requirements

### 1. Create `orch/archive/batch_archiver.py`

Create a new module that orchestrates batch-level archiving. This module will be called from a background thread by the dashboard endpoint (implemented in S03).

**Function signature:**

```python
def archive_batch(
    project_id: str,
    batch_id: str,
    archive_dir: Path | str | None = None,
) -> ArchiveResult:
```

This function must:

1. **Open its own DB session** — it runs in a background thread, so it MUST NOT share sessions with the calling thread. Use `SessionLocal()` from `orch.db.session`.

2. **Validate state** — Load the batch, verify it is in `completed` or `completed_with_errors` status. If not, raise `ValueError`.

3. **Transition batch to `archived`** — Set `batch.status = BatchStatus.archived` and `batch.updated_at = now()`. Commit this immediately so the UI reflects the change.

4. **Run post-archive commands** — Load the project from DB, read `project.config.get("post_archive_commands", [])`. For each command string:
   - Run with `subprocess.run(cmd, shell=True, cwd=project.repo_root, capture_output=True, text=True, timeout=300)`
   - Log stdout/stderr
   - If a command fails (non-zero exit), log the error but **continue** — command failure must NOT prevent archiving
   - Collect results (command, returncode, stdout, stderr) for the result object

5. **Archive merged work items** — Query all `BatchItem` rows for this batch. For each item with `status == BatchItemStatus.merged`, call `archive_work_item()` from `orch.archive.archiver`. Skip items that are not merged (e.g., failed items in `completed_with_errors` batches).

6. **Emit daemon event** — After all work is done, create a `DaemonEvent` with `event_type="batch_archived"` so the SSE stream can notify the user.

7. **Return an `ArchiveResult` dataclass** containing:
   - `batch_id: str`
   - `items_archived: list[str]` — IDs of successfully archived items
   - `items_skipped: list[str]` — IDs of non-merged items that were skipped
   - `commands_run: list[CommandResult]` — results of each post-archive command
   - `success: bool` — True if batch was archived (even if some commands failed)
   - `error: str | None` — error message if the archive failed entirely

**`CommandResult` dataclass:**
```python
@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
```

### 2. Error handling

- Wrap the entire function in try/except — if an unexpected error occurs, log it and emit a `batch_archive_failed` daemon event so the user gets an error toast.
- Each post-archive command has a 300-second timeout. If it times out, log the timeout and continue.
- If `archive_work_item()` raises for a specific item, log the error, add to `items_skipped`, and continue with other items.

### 3. Logging

Use `logging.getLogger(__name__)` and log:
- INFO: "Archiving batch {batch_id} for project {project_id}"
- INFO: "Running post-archive command: {cmd}"
- WARNING: "Post-archive command failed: {cmd} (rc={returncode})"
- INFO: "Archived {n} items, skipped {m} items"
- ERROR: "Batch archive failed: {error}" (only on unexpected exceptions)

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Framework-specific patterns (ORM style, API patterns, etc.)
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write failing tests first that define the expected behavior
2. **GREEN**: Write the minimal implementation to make tests pass
3. **REFACTOR**: Improve code structure while keeping all tests green

Do not skip the RED phase. Tests must exist before implementation code.

### Test file: `tests/unit/test_batch_archiver.py`

Write unit tests that mock the DB session and `subprocess.run`:

- `test_archive_batch_completed` — happy path, all items merged, commands succeed
- `test_archive_batch_completed_with_errors` — mixed merged/failed items
- `test_archive_batch_invalid_status` — batch in `executing` status → ValueError
- `test_archive_batch_no_post_commands` — no `post_archive_commands` in config
- `test_archive_batch_command_failure` — command returns non-zero, archive still completes
- `test_archive_batch_command_timeout` — command times out, archive still completes
- `test_archive_batch_item_archive_error` — one item fails to archive, others still archived
- `test_archive_batch_emits_event` — verify DaemonEvent with `event_type="batch_archived"` is created

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run the project's unit test command (check Makefile or `CLAUDE.md` for the exact command)
2. Run lint and type checking (check Makefile or `CLAUDE.md` for the exact command)
3. Do **NOT** report `tests_passed: true` unless ALL unit tests pass with zero failures
4. If tests fail, fix them before reporting completion

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00001",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/archive/batch_archiver.py",
    "tests/unit/test_batch_archiver.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
