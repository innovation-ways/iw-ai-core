# CR-00023_S03_Backend_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Allowed: testcontainers via pytest fixtures, `docker ps`/`inspect`/`logs`,
`./ai-core.sh`, `make`.

## ⛔ Migrations

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB.
Your work in this step does not require a migration; S01 already shipped one.

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design document (Implementation Plan, AC2, AC4)
- `ai-dev/active/CR-00023/reports/CR-00023_S01_Database_report.md` — S01's revision ID
- `ai-dev/active/CR-00023/reports/CR-00023_S02_CodeReview_Database_report.md` — S02 review findings
- `orch/cli/item_commands.py` — `register` command (line ~145), `parse_manifest_steps` (line 111)
- `orch/daemon/batch_manager.py` — `_build_claude_prompt` (line ~838), `_compute_qv_baselines` (line ~430), `_read_workflow_manifest` (line ~534)
- `orch/daemon/fix_cycle.py` — `_get_gate_name_and_command` (line ~675)

## Output Files

- `orch/cli/item_commands.py` — modified
- `orch/daemon/batch_manager.py` — modified
- `orch/daemon/fix_cycle.py` — modified
- `ai-dev/active/CR-00023/reports/CR-00023_S03_Backend_report.md` — step report

## Context

You're wiring three things together:

1. **Register-side ingest** — when `iw register --steps-from <manifest>` runs, capture the manifest's `command`/`gate`/`timeout` per step into the new DB columns.
2. **Manifest stamping** — after a successful register, rewrite the manifest in place to add a top-level `_note` field marking it non-authoritative.
3. **Daemon fallback** — make the three daemon read paths prefer the DB columns when populated, and fall back to the existing manifest read when columns are NULL (so items registered before CR-00023 keep working).

## Requirements

### 1. Register-side ingest (`orch/cli/item_commands.py`)

In the `register` command's `WorkflowStep(...)` construction (around line 351-363), pass three additional kwargs sourced from the manifest step entry:

```python
session.add(
    WorkflowStep(
        # ...existing fields...
        command=str(step_data["command"]) if step_data.get("command") else None,
        gate=str(step_data["gate"]) if step_data.get("gate") else None,
        timeout_secs=int(step_data["timeout"]) if step_data.get("timeout") is not None else None,
    )
)
```

Coerce types defensively (the manifest is JSON; `timeout` could arrive as int or string). On a `ValueError` from `int()` coercion, fail the register with a clear error message — do not silently NULL.

### 2. Manifest stamping (`orch/cli/item_commands.py`)

After the `session.flush()` (and before the success echo), rewrite the manifest file in place to add a `_note` key:

```python
NOTE_TEXT = (
    "This file is a design-time snapshot and may be out of date. "
    "For current step state, run: iw item-status <ID> --json. "
    "The DB is the authoritative source of truth (CR-00023)."
)

if steps_from:
    manifest_path = Path(steps_from)
    try:
        raw = json.loads(manifest_path.read_text())
        if isinstance(raw, dict) and raw.get("_note") != NOTE_TEXT:
            # Insert _note as the first key for visibility on read.
            stamped = {"_note": NOTE_TEXT, **{k: v for k, v in raw.items() if k != "_note"}}
            manifest_path.write_text(
                json.dumps(stamped, indent=2, ensure_ascii=False) + "\n"
            )
    except (OSError, json.JSONDecodeError) as exc:
        # Do not fail the register if the manifest is unwritable; warn instead.
        click.echo(
            f"Warning: could not stamp manifest with _note header: {exc}",
            err=True,
        )
```

Hard rules:

- The stamping MUST be idempotent — re-running `iw register` on an already-stamped manifest must NOT duplicate the note or alter formatting beyond the existing newline-at-EOF convention.
- Preserve all existing keys (`id`, `type`, `title`, `browser_verification`, `steps`, `scope`, etc.) with byte-identical contents — only the `_note` key is added.
- Preserve UTF-8 characters (`ensure_ascii=False`) so existing entries with non-ASCII text (em-dashes, etc.) survive the round-trip.
- The note text must mention "design-time snapshot" and "iw item-status" (AC5 verifies these substrings).

### 3. Daemon fallback wiring

Three call sites currently read `command`/`gate`/`prompt` from the manifest. Add DB-first behavior with a manifest fallback:

#### `orch/daemon/batch_manager.py:_build_claude_prompt`

Currently (line ~850-877) opens `workflow-manifest.json` and reads `s.get("prompt")`/`s.get("command")`/`s.get("gate")` for the matching step. Change to:

```python
prompt_content = ""
# DB-first lookup (CR-00023): use WorkflowStep columns when populated.
db_prompt_file = step.prompt_file
db_command = step.command
db_gate = step.gate
db_description = step.description

if db_command:
    # qv-gate path — DB has the command, skip manifest read entirely.
    gate_name = db_gate or step_id
    prompt_content = (
        f"Run the following quality gate and report results.\n\n"
        f"**Gate**: {gate_name}\n"
        f"**Command**: `{db_command}`\n"
        f"**Description**: {db_description or ''}\n\n"
        f"Execute exactly: `{db_command}`\n"
        f"Capture the output. If exit code is 0, the gate passed. "
        f"Otherwise it failed.\n"
        f"Report PASS or FAIL with the relevant output."
    )
elif db_prompt_file:
    prompt_path = design_dir / db_prompt_file
    if prompt_path.exists():
        prompt_content = prompt_path.read_text()

# Legacy fallback: items registered before CR-00023 have NULL columns.
if not prompt_content and manifest_path.exists():
    # ... existing manifest-read code unchanged ...
```

Keep the existing manifest-read code as the fallback branch — do not delete it.

#### `orch/daemon/fix_cycle.py:_get_gate_name_and_command`

Currently reads only from manifest. Change signature to accept the `WorkflowStep` and try DB first:

```python
def _get_gate_name_and_command(
    step: WorkflowStep, worktree_path: str
) -> tuple[str | None, str | None]:
    # DB-first lookup (CR-00023).
    if step.command is not None:
        return (step.gate or step.step_id), step.command
    # Legacy fallback for pre-CR-00023 items.
    # ... existing manifest-read body unchanged ...
```

#### `orch/daemon/batch_manager.py:_compute_qv_baselines`

Around line 482-488, the per-step manifest lookup is:

```python
step_manifest = next((s for s in manifest_steps if s.get("step") == step.step_id), None)
if not step_manifest:
    continue
gate = step_manifest.get("gate", step.step_id)
command = step_manifest.get("command")
if not command:
    continue
```

Change to prefer DB columns:

```python
db_gate = step.gate
db_command = step.command
if db_command:
    gate = db_gate or step.step_id
    command = db_command
else:
    # Legacy fallback.
    step_manifest = next((s for s in manifest_steps if s.get("step") == step.step_id), None)
    if not step_manifest:
        continue
    gate = step_manifest.get("gate", step.step_id)
    command = step_manifest.get("command")
    if not command:
        continue
```

The existing `manifest_steps = self._read_workflow_manifest(...)` call at line 457 stays — it's still needed for the fallback path.

### Hard Constraints

- Do NOT delete the existing manifest-read code paths. They are the fallback for legacy NULL rows (AC4).
- Do NOT change the `register` command's existing idempotency semantics (the early-return for already-registered items).
- Do NOT touch `orch/cli/item_commands.py:item_status` — that's S05's scope.
- Manifest stamping MUST NOT change the JSON formatting of existing keys (re-indenting other keys would create a noisy diff for design-package authors).

## Project Conventions

Read `orch/CLAUDE.md` for CLI module structure, `orch/daemon/` for daemon patterns,
and root `CLAUDE.md` for the "PostgreSQL as sole source of truth" principle.

## TDD Requirement

Follow Red-Green-Refactor. The Tests step (S09) writes the formal coverage; in
this step, exercise your changes locally before reporting done:

1. Run `uv run pytest tests/unit/ -k "register or item_status" -q` — should still pass.
2. Run `uv run mypy orch/cli/item_commands.py orch/daemon/batch_manager.py orch/daemon/fix_cycle.py` — must be clean.
3. Run `make lint` — must be clean.

If any pre-existing test fails because the JSON shape changed, those changes belong in S05 (not here) — flag in your report.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00023",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/item_commands.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed; mypy clean; lint clean",
  "blockers": [],
  "notes": "Manifest stamping is idempotent; daemon fallback verified by inspection (S09 writes formal coverage)."
}
```
