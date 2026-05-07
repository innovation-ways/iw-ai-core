# CR-00036_S03_Backend_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers via pytest fixtures, read-only `docker ps`/`inspect`/`logs`, `./ai-core.sh` and `make` targets. If prohibited command seems necessary, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. This step does not add or modify any migration — S01 owns the migration. Read-only alembic introspection is fine. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S01_Database_report.md` and `CR-00036_S02_CodeReview_report.md`
- `orch/daemon/project_registry.py` — `ProjectConfig` dataclass and `_build_project_config`.
- `orch/daemon/batch_manager.py` — site that transitions BatchItem to `completed` on workflow success.
- `orch/daemon/merge_queue.py` — confirm `process_merge_queue` continues to filter on `BatchItemStatus.completed` only.
- `orch/cli/batch_commands.py` — `batch-create` command (around lines 235-360).
- `orch/cli/item_commands.py` — pattern for new subcommands.
- `dashboard/routers/items.py:496-578` — `_merge_status` and `_synthetic_merge_step`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S03_Backend_report.md`

## Context

You are implementing the backend layer for CR-00036. The schema additions from S01 already exist; your job is to wire them through the daemon, CLI, and dashboard service layer so the new flag actually changes behavior.

Read the design doc first. Pay especially close attention to "Desired Behavior" (1, 2, 4, 6, 7), AC1/AC2/AC5/AC6/AC7/AC9/AC10.

## Requirements

### 1. Parse `auto_merge` from `projects.toml`

In `orch/daemon/project_registry.py`:

- Add `auto_merge_default: bool = True` to the `ProjectConfig` dataclass (default reflects "absent → true").
- In `_build_project_config`, parse the `auto_merge` key from the `projects.toml` entry. Mirror the `self_assess` pattern (look at lines 128-138): default to `True` if absent, accept `bool` true/false, log a warning for non-bool values and fall back to `True`.
- Pass the parsed value into the `ProjectConfig(...)` constructor.

Do NOT touch the staleness/services/alembic parsing — `auto_merge` is a top-level key on the project entry, just like `self_assess`.

### 2. Gate batch-item completion in `BatchManager`

Locate the call site in `orch/daemon/batch_manager.py` where a `BatchItem` is set to `BatchItemStatus.completed` after all its workflow steps succeed (the workflow-completion handler — find it via the existing reference; do NOT use the merge_failure or stall paths).

Replace the unconditional `completed` transition with:

```python
batch_item.status = (
    BatchItemStatus.completed
    if batch.auto_merge
    else BatchItemStatus.awaiting_merge_approval
)
```

(Use whatever local variable name `batch_manager` already binds for the parent batch; if it does not load the batch, load it via `db.get(Batch, (project_id, batch_item.batch_id))` immediately above the assignment. Cache the lookup if multiple items in the same call site need the value.)

Emit a `DaemonEvent` of `event_type="batch_item_awaiting_merge_approval"` whenever the new state is set, with `event_metadata={"batch_id": ..., "work_item_id": ...}`. Match the existing event-emission pattern in this file.

Do NOT modify `process_merge_queue` — its existing filter on `BatchItemStatus.completed` is exactly the gate behavior we want (transient items are invisible to the queue).

### 3. Add the `approve_merge` service function

Create `orch/services/batch_item_approval.py` (or place it in an existing module if the project's convention puts daemon-callable services elsewhere — read `orch/CLAUDE.md` to confirm; if no such convention exists, the new module is acceptable).

Function signature:

```python
def approve_merge(db: Session, project_id: str, item_id: str) -> BatchItem:
    """Transition a BatchItem from awaiting_merge_approval to completed.

    Used by both the dashboard route POST /actions/item/{item_id}/approve-merge
    and the CLI `iw item approve-merge`. The next daemon poll cycle will pick
    the item up via the existing merge queue path.

    Raises:
        ValueError: if the item is not currently in awaiting_merge_approval.
    """
```

The function MUST:

- Use SELECT ... FOR UPDATE to lock the BatchItem row (this is the convention used elsewhere in the daemon for state transitions — see `merge_queue._merge_item` for the pattern).
- Reject (raise `ValueError`) if `bi.status != BatchItemStatus.awaiting_merge_approval`. Include the current status in the error message.
- Set `bi.status = BatchItemStatus.completed`.
- Emit a `DaemonEvent(event_type="merge_approved_by_operator", event_metadata={"batch_id": bi.batch_id, "work_item_id": bi.work_item_id})`.
- Commit and return the refreshed `BatchItem`.

### 4. Add `iw item approve-merge` CLI subcommand

In `orch/cli/item_commands.py`, add:

```python
@item.command("approve-merge")
@click.argument("item_id")
@click.option("--project", "project_id_opt", default=None, help="Override project id (default: current project)")
@click.pass_context
def approve_merge_cmd(ctx, item_id, project_id_opt):
    """Approve a manual merge for a batch item awaiting approval."""
```

Resolve project_id via the existing helper used by sibling commands (`current-project`-style). Open a session, look up the BatchItem for `(project_id, item_id)` (the BatchItem corresponds to a WorkItem; load via `BatchItem.work_item_id == item_id` AND `project_id`), call `approve_merge(...)`, and emit a one-line success message. On `ValueError`, exit code 4 and print the error.

JSON mode (when `ctx.obj["json"]` is set): print `{"item_id": ..., "status": "completed"}` on success.

### 5. Add `--auto-merge / --no-auto-merge` to `iw batch-create`

In `orch/cli/batch_commands.py` (around lines 235-260 where `--auto-publish` is declared):

```python
@click.option(
    "--auto-merge/--no-auto-merge",
    "auto_merge",
    default=None,
    help="Auto-merge each item to main on success (default: project's auto_merge default in projects.toml)",
)
```

When `auto_merge is None` (no flag passed), resolve to the project's `ProjectConfig.auto_merge_default`. Add the resolution near where `max_parallel`/`auto_publish` are first read; the existing code already has the `ProjectConfig` available via the project registry — match its access pattern.

Pass the resolved value into the `Batch(...)` constructor at the existing creation site (around line 306).

Include the resolved value in the JSON output stanza (around line 350) and in the human-readable echo (around line 357).

### 6. Update `_merge_status` and the synthetic MERGE step

In `dashboard/routers/items.py:496` (`_merge_status`):

Add a new branch (place it before the existing recoverable-status branch):

```python
if bi.status == BatchItemStatus.awaiting_merge_approval:
    return "awaiting_approval"
```

In `_synthetic_merge_step` (line 565), this just propagates — no logic change there. Confirm the resulting StepDetail has `status="awaiting_approval"` for the new state.

In `_get_log_sections` (around line 779), the merge log section uses `_merge_status(bi)` already — keep that.

### 7. Update CLI spec doc

In `docs/IW_AI_Core_CLI_Spec.md`:

- Update the `iw batch-create` synopsis (around line 391) to include `[--auto-merge | --no-auto-merge]`.
- Add a row for `--auto-merge / --no-auto-merge` in the flag table; describe default as "from project's `auto_merge` in projects.toml (default true)".
- Add a new section for `iw item approve-merge <item_id>` documenting inputs, outputs, exit codes (0 success, 4 invalid state).
- Update the JSON example to include `"auto_merge": true`.

### 8. Update daemon design doc

In `docs/IW_AI_Core_Daemon_Design.md`, in the merge-queue section, add a paragraph explaining the new gate: "When `batch.auto_merge` is false, BatchManager parks successful items in `awaiting_merge_approval` instead of `completed`. The merge queue continues to pick only `completed` items, so parked items remain invisible to it until an operator releases them via `POST /actions/item/{id}/approve-merge` or `iw item approve-merge`."

In the same doc, in the stall-monitor section (search for `IW_CORE_STALL_THRESHOLD` or `stall`), add: "The stall monitor MUST exempt `BatchItemStatus.awaiting_merge_approval` items from the stall-fail timer — this is a *waiting-on-human* state, not a *stuck* state, and operators may legitimately leave items parked for days." If the stall monitor is implemented in code (e.g., `orch/daemon/stall_monitor.py` or similar), audit the implementation and add the exemption there as well; if no such code path exists yet (i.e., stall handling is purely doc/aspirational), the doc note suffices.

### 9. Audit stall-handling code paths

Before reporting `complete`, run:

```bash
grep -rn "IW_CORE_STALL_THRESHOLD\|stall\|stalled" orch/daemon/ orch/db/models.py
```

If any code path auto-fails non-terminal `BatchItem` rows after a timeout, ensure `awaiting_merge_approval` is excluded. If no such path exists today, note that explicitly in the report (`stall_audit: "no auto-fail path exists; doc note added"`).

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md`, and `dashboard/CLAUDE.md`:

- Sync SQLAlchemy 2.0; no `async`.
- DaemonEvent metadata column is **`event_metadata`** in Python (SQLAlchemy reserves `metadata`).
- CLI helpers: shared `output_error` from `orch/cli/utils.py`.
- Composite PKs `(project_id, id)` everywhere.

## TDD Requirement

Write tests before implementation for each deliverable:

- `tests/unit/test_project_registry.py` — `auto_merge` parsing (default, true, false, non-bool).
- `tests/unit/test_batch_manager.py` — gate logic with both `auto_merge=true` and `auto_merge=false`.
- `tests/integration/test_batch_item_approval.py` — `approve_merge` happy path and rejection on wrong status.
- `tests/integration/test_cli_items.py` (or extend existing) — `iw item approve-merge` happy path + rejection.
- `tests/integration/test_cli_batches.py` — `--auto-merge`, `--no-auto-merge`, default-from-project.

## Pre-flight Quality Gates

Before reporting `complete`:

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification

`make test-unit` and `make test-integration` MUST pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00036",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
