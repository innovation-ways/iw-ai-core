# CR-00025 S01 — Backend: Evidence-ingestion pipeline + CLI hooks

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S01
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

Allowed exceptions: testcontainers spun up by pytest fixtures; read-only
introspection (`docker ps`, `docker inspect`, `docker logs`); invoking
`./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no DDL**. The `work_item_evidences` table, enum, FK, and indexes
already exist (migration `d6b67d4ecb9f_add_work_item_evidences.py`, shipped
with CR-00020). Do not write a new migration. If you think you need one,
STOP and raise a blocker.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00025 --json`
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md` — design document (read first)
- `orch/db/models.py` (lines 831–881) — `WorkItemEvidence` model and `EvidencePhase` enum
- `orch/cli/item_commands.py` (lines 470–504) — current `approve` command
- `orch/cli/step_commands.py` (lines 51–83, 271–347) — `validate_browser_evidence_present` and current `step_done` command
- `orch/config.py` — `load_config()` / env-var pattern
- `dashboard/routers/items.py` (lines 700–757) — current `_list_evidences` (DO NOT MODIFY — already correct)

## Output Files

- `orch/evidences.py` — new module
- `orch/config.py` — modified (add `IW_CORE_EVIDENCE_MAX_BYTES`)
- `orch/cli/item_commands.py` — modified (hook into `approve`)
- `orch/cli/step_commands.py` — modified (hook into `step_done` for `browser_verification` only)
- `docs/IW_AI_Core_Database_Schema.md` — modified (add "Implemented in CR-00025" note)
- `CLAUDE.md` — modified (add `Evidences ingestion → orch/evidences.py` row to Quick Navigation)
- `ai-dev/active/CR-00025/reports/CR-00025_S01_Backend_report.md` — step report

## Context

You are implementing the missing data-ingestion pipeline that CR-00020
specified but never delivered. The dashboard already reads from
`work_item_evidences` (DB-first, FS fallback for in-progress post evidence)
but the table is empty in production because nothing writes to it. Your
job is to write the helper and wire it into the two lifecycle events the
design specified.

Read `CR-00025_CR_Design.md` for full background, especially "Current
Behavior" and "Desired Behavior". Read `orch/CLAUDE.md` for SQLAlchemy
2.0 sync style, psycopg v3 driver, and append-only conventions (note:
`work_item_evidences` is **upsert**, not append-only).

## Requirements

### 1. New module `orch/evidences.py`

Public function:

```python
def ingest_phase_from_disk(
    session: Session,
    project_id: str,
    work_item_id: str,
    phase: EvidencePhase,
    root: Path,                       # repo root (for pre) or cwd (for post)
    step_id: str | None = None,       # NULL for pre; concrete step_id for post
    max_bytes: int | None = None,     # default: load from config
) -> int:                             # returns count of rows upserted
```

Behaviour:

1. Compute `phase_dir = root / "ai-dev" / "active" / work_item_id / "evidences" / phase.value`.
2. If the directory does not exist or is empty, return 0 (no error).
3. Iterate `phase_dir.iterdir()`, skipping anything that is not a regular
   file (no symlinks, no subdirs).
4. For each file:
   - Read bytes (`Path.read_bytes()`).
   - If `len(content) > max_bytes`, raise `EvidenceTooLargeError(filename, size, max_bytes)` — a custom exception defined in this module. Do NOT silently skip.
   - Determine `content_type` via `mimetypes.guess_type(filename)[0]`,
     defaulting to `"application/octet-stream"`. Make sure `.yaml` / `.yml`
     map to a sensible type (`mimetypes` does not always know about YAML;
     register `application/yaml` for `.yaml` and `.yml` at module import
     via `mimetypes.add_type`).
   - Upsert into `work_item_evidences` using PostgreSQL `ON CONFLICT
     (project_id, work_item_id, phase, filename) DO UPDATE SET
     content = EXCLUDED.content, size_bytes = EXCLUDED.size_bytes,
     content_type = EXCLUDED.content_type, captured_at = now(),
     step_id = EXCLUDED.step_id`. Use SQLAlchemy's
     `from sqlalchemy.dialects.postgresql import insert` for the
     `Insert.on_conflict_do_update(...)` clause; the index target is the
     `uq_evidence_per_file` unique constraint.
5. **Do not commit.** The caller's session owns the transaction boundary.
6. Return the number of rows upserted (counts both inserts and updates).

Custom exception:

```python
class EvidenceTooLargeError(Exception):
    def __init__(self, filename: str, size: int, max_bytes: int) -> None:
        super().__init__(
            f"Evidence file '{filename}' is {size} bytes, exceeds max {max_bytes} bytes "
            f"(configure via IW_CORE_EVIDENCE_MAX_BYTES)"
        )
        self.filename = filename
        self.size = size
        self.max_bytes = max_bytes
```

The module should also expose a private helper:

```python
def _default_max_bytes() -> int:
    """Read IW_CORE_EVIDENCE_MAX_BYTES from config; default 5 MiB."""
```

### 2. Config knob in `orch/config.py`

Add `IW_CORE_EVIDENCE_MAX_BYTES` to the `Config` dataclass (or whatever
shape `load_config()` returns — match existing patterns). Default value:
`5 * 1024 * 1024` (5 MiB). Read via `os.getenv` and `int(...)` with a
clear error message on bad values. Document it in any docstring or table
that already lists the env vars (see `CLAUDE.md` "Configuration" section
if it lists them — match the style).

### 3. Hook `approve` (`orch/cli/item_commands.py`)

In the `approve` command (currently lines 470–504), inside the `with
get_session() as session:` block, **after** the `item.status =
WorkItemStatus.approved` line and **before** `session.flush()`, call:

```python
from orch.evidences import ingest_phase_from_disk, EvidenceTooLargeError
from orch.db.models import EvidencePhase

repo_root = ctx.obj.get("repo_root", "") or "."
try:
    count = ingest_phase_from_disk(
        session=session,
        project_id=project_id,
        work_item_id=item_id,
        phase=EvidencePhase.pre,
        root=Path(repo_root),
        step_id=None,
    )
except EvidenceTooLargeError as exc:
    output_error(ctx, str(exc), 1)  # transaction rolls back via context manager
```

Imports go at the top of the file. The existing `output_error` helper
already raises `click.exceptions.Exit`, which propagates out of the
`with get_session()` block; the session context manager rolls the
transaction back. Confirm this by reading `orch/db/session.py`'s
`get_session` implementation.

The new ingestion must be inside the same transaction as the status
flip. AC4 requires that an oversize file leaves the item in `draft`
status — verify this in your implementation.

### 4. Hook `step_done` (`orch/cli/step_commands.py`)

In the `step_done` command (lines 271–347), inside the `with
get_session() as session:` block, **after** the existing
`validate_browser_evidence_present` check passes and the status flip is
done, **and only when** `step.step_type == StepType.browser_verification`,
call:

```python
from orch.evidences import ingest_phase_from_disk, EvidenceTooLargeError
from orch.db.models import EvidencePhase

if step.step_type == StepType.browser_verification:
    try:
        count = ingest_phase_from_disk(
            session=session,
            project_id=project_id,
            work_item_id=item_id,
            phase=EvidencePhase.post,
            root=Path.cwd(),
            step_id=step.step_id,  # the string step_id, e.g. "S11"
        )
    except EvidenceTooLargeError as exc:
        output_error(ctx, str(exc), 1)
```

Place this block **before** the `session.flush()` that ends the with-block,
inside the same transaction as the status flip. For non-browser-verification
step types the call is skipped — see AC2 for the negative case.

### 5. Documentation updates

- `docs/IW_AI_Core_Database_Schema.md` — find the section that documents
  `work_item_evidences` (added by CR-00020). Add a one-liner:
  *"Ingestion pipeline implemented in CR-00025 — see `orch/evidences.py`.
  Prior to CR-00025 the table was empty because no code wrote to it."*
- `CLAUDE.md` Quick Navigation — add a row:
  ```
  | Evidences ingestion (CR-00025) | `orch/evidences.py` · hooks in `orch/cli/item_commands.py` (approve) and `orch/cli/step_commands.py` (step-done) |
  ```
  Place it adjacent to other `orch/` entries.

## Project Conventions

Read `orch/CLAUDE.md` for:
- SQLAlchemy 2.0 `Mapped[]` style, sync sessions
- psycopg v3 driver (`postgresql+psycopg://`, NOT psycopg2)
- Composite PK pattern `(project_id, item_id)`
- Append-only vs upsert tables (this CR uses upsert)

Match existing CLI command patterns in `orch/cli/item_commands.py` and
`orch/cli/step_commands.py` exactly — the same `output_error`, the same
`session.flush()` placement, the same `DaemonEvent` pattern (you do
**not** need to add a DaemonEvent for ingestion; the existing
`step_completed` event covers it).

## TDD Requirement

This step is **implementation only** — tests are written in S03. However:

- After implementation, run `make test-unit` and ensure no existing tests
  break (the `tests/integration/test_work_item_evidence.py` tests should
  continue to pass — they cover the model in isolation, not the new
  hooks).
- Smoke-test by creating a temp work item locally and running `iw
  approve` — but **only inside a testcontainer or a throwaway DB**, never
  against the production orch DB on port 5433.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift; re-stage if it modifies files.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Populate `preflight` in your result contract: `"ok" | "fixed" | "skipped:<reason>"`.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00025",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/evidences.py",
    "orch/config.py",
    "orch/cli/item_commands.py",
    "orch/cli/step_commands.py",
    "docs/IW_AI_Core_Database_Schema.md",
    "CLAUDE.md"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
