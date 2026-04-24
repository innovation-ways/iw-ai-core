# CR-00020_S03_Backend_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`. S01 wrote the migration; do NOT generate a new one here.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design
- `ai-dev/active/CR-00020/reports/CR-00020_S01_Database_report.md` — S01 report (schema exists now)
- `orch/cli/item_commands.py` — existing `approve` command at line ~389 (hook point)
- `orch/cli/step_commands.py` — existing `step_done` command (hook point, add after `validate_browser_evidence_present`)
- `orch/config.py` — existing `load_config()`
- `orch/cli/utils.py` — `output_error` helper

## Output Files

- `orch/evidences.py` — NEW pure ingest helper module
- `orch/config.py` — MODIFIED: add `IW_CORE_EVIDENCE_MAX_BYTES`
- `orch/cli/item_commands.py` — MODIFIED: hook ingest into `approve` (phase=pre)
- `orch/cli/step_commands.py` — MODIFIED: hook ingest into `step_done` (phase=post, browser_verification only)
- `ai-dev/active/CR-00020/reports/CR-00020_S03_Backend_report.md` — step report

## Context

Wire the schema from S01 into the CLI lifecycle. The design's "Desired Behavior" section is authoritative. Read it and the ACs carefully before starting — especially AC3 (idempotent upsert), AC4 (size limit with transaction rollback), and AC8 (missing-dir is a no-op).

## Requirements

### 1. `orch/evidences.py` — new module

Pure helper — takes a live session and paths, no CLI coupling. Signature:

```python
@dataclass(frozen=True)
class IngestResult:
    ingested_filenames: list[str]
    skipped_oversize: list[tuple[str, int]]  # (filename, size_bytes) — only populated if raise_on_oversize=False
    # Never includes directories or non-regular files.


class EvidenceOversizeError(Exception):
    """Raised when a file exceeds max_bytes. Callers should let this propagate so the
    surrounding transaction rolls back."""


def ingest_phase_from_disk(
    session: Session,
    *,
    project_id: str,
    work_item_id: str,
    phase: EvidencePhase,
    base_dir: Path,                   # e.g. <repo>/ai-dev/active/<id>/evidences/pre
    step_id: str | None = None,
    max_bytes: int,
) -> IngestResult:
    """Upsert every regular file in base_dir into work_item_evidences.

    - Non-existent base_dir  → IngestResult([], []). No error.
    - Empty base_dir         → IngestResult([], []). No error.
    - Subdirectory entries, symlinks pointing outside base_dir, non-regular files
                              → skipped silently (don't ingest, don't count).
    - Any file > max_bytes   → raise EvidenceOversizeError BEFORE any upsert for this call.
                                That means: if ANY file is oversize, NO files are ingested
                                from this invocation (AC4).
    - content_type           → mimetypes.guess_type(filename) or 'application/octet-stream'.
    - Upsert                 → PostgreSQL ON CONFLICT (project_id, work_item_id, phase, filename)
                                DO UPDATE SET content=EXCLUDED.content,
                                              content_type=EXCLUDED.content_type,
                                              size_bytes=EXCLUDED.size_bytes,
                                              captured_at=now().
                                The existing row's UUID is preserved.
    """
```

Implementation notes:

- Use `sqlalchemy.dialects.postgresql.insert(WorkItemEvidence).on_conflict_do_update(...)` for the upsert.
- Iterate via `sorted(base_dir.iterdir())` so ingest order is deterministic (tests depend on this).
- Skip entries where `entry.is_file()` is False (this rejects dirs, symlinks-to-dirs, devices).
- **First pass**: stat every file. If any exceeds `max_bytes`, raise `EvidenceOversizeError(filename, size)` and exit — do not start inserts. Two-pass avoids partial ingest even inside one session.
- **Second pass**: read + insert. `session.execute(insert_stmt)` per file (small enough count that a batch isn't needed).

### 2. `IW_CORE_EVIDENCE_MAX_BYTES` in `orch/config.py`

Add to the existing `load_config()` logic:

- Env var name: `IW_CORE_EVIDENCE_MAX_BYTES`
- Default: `5 * 1024 * 1024` (5242880)
- Exposed on the returned config object (whatever shape `load_config()` uses — follow the existing pattern).
- Validation: if set but not a positive int, raise the same error style the other config vars use.

### 3. `orch/cli/item_commands.py` — hook into `approve`

Inside the existing `with get_session() as session:` block in `approve`, AFTER the status flip and BEFORE `session.flush()`:

```python
# Ingest pre-evidences into the DB so they survive archive.
repo_root = ctx.obj.get("repo_root") or Path.cwd()
pre_dir = Path(repo_root) / "ai-dev" / "active" / item_id / "evidences" / "pre"
try:
    ingest_phase_from_disk(
        session,
        project_id=project_id,
        work_item_id=item_id,
        phase=EvidencePhase.pre,
        base_dir=pre_dir,
        step_id=None,
        max_bytes=load_config().evidence_max_bytes,
    )
except EvidenceOversizeError as exc:
    output_error(ctx, f"Evidence {exc.filename} is {exc.size_bytes} bytes; limit is {exc.max_bytes}", 1)
```

- The ingest MUST run inside the same `with get_session()` block so a failure rolls back the status flip (AC4).
- If `evidence_max_bytes` is not the actual attribute name in the config dataclass, use whatever the final attribute name is.

### 4. `orch/cli/step_commands.py` — hook into `step_done`

In `step_done`, AFTER `validate_browser_evidence_present(...)` passes (which is already a browser-only check) and BEFORE the outer `session.flush()`:

```python
if step.step_type == StepType.browser_verification:
    post_dir = Path.cwd() / "ai-dev" / "active" / item_id / "evidences" / "post"
    try:
        ingest_phase_from_disk(
            session,
            project_id=project_id,
            work_item_id=item_id,
            phase=EvidencePhase.post,
            base_dir=post_dir,
            step_id=step_id,
            max_bytes=load_config().evidence_max_bytes,
        )
    except EvidenceOversizeError as exc:
        output_error(ctx, f"Evidence {exc.filename} is {exc.size_bytes} bytes; limit is {exc.max_bytes}", 1)
```

- Use `Path.cwd()` (not `repo_root`) — daemon-launched agents run with `cwd=worktree_path`, so cwd is the correct base.
- The check `step.step_type == StepType.browser_verification` short-circuits for every other step type. AC8's "no regression for non-browser steps" relies on this.
- Non-browser steps never run the ingest, so `evidences/` never triggers a cost.

### 5. Error messages

Use human-readable `output_error` messages:
- `"Evidence ok.png is 100 bytes; limit is 5242880"` — exact format used by AC4's human assertion.

## Project Conventions

- `from __future__ import annotations` is OK in `orch/evidences.py` (it's not `orch/db/models.py`).
- Type hints on all public functions + dataclasses.
- No new dependencies — `sqlalchemy.dialects.postgresql.insert` ships with SQLAlchemy.
- Log at DEBUG when ingest runs; INFO when ingest actually inserts/updates a row; ERROR only on the oversize path (which becomes `output_error`).

## TDD Requirement

S07 owns the full test suite. For S03, your implementation must be testable; write the helper so unit tests can pass a `Session` (including a real testcontainer session) without any CLI coupling.

Before completion, run the existing unit suite to catch regressions:

```bash
make test-unit
```

Do NOT write S07's tests here. If you discover your design needs a small helper test to validate a single function, put it in `tests/unit/test_evidences_ingest.py` — but S07 will expand it.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` must pass with your changes.
2. `make lint`, `make format`, `make typecheck` must pass.
3. Do not mark `tests_passed: true` unless unit tests are green.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/evidences.py",
    "orch/config.py",
    "orch/cli/item_commands.py",
    "orch/cli/step_commands.py"
  ],
  "tests_passed": true,
  "test_summary": "unit tests: X passed",
  "blockers": [],
  "notes": ""
}
```
