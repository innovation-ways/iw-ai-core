# I-00114_S01_Backend_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Incident adds **no migrations** (event_type is TEXT; reprompt counter lives in metadata JSONB). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design document (read in full; especially Root Cause Analysis and the Fix Plan table).
- `orch/cli/__init__.py` — where Click commands are registered.
- `orch/cli/item_commands.py` — closest prior art for "emits a daemon_events row from a CLI command". Read `_emit_event` usage to match the existing pattern.
- `orch/db/models.py` — `DaemonEvent` model (note: Python attr is `event_metadata`; DB column is `metadata`).
- `orch/cli/utils.py` — shared CLI helpers (session access, output formatting).
- `orch/CLAUDE.md` — orch package conventions.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S01_Backend_report.md` — Step report.

## Context

You are implementing **S01: the `iw daemon-event` CLI command**. This is the smallest, most isolated piece of the fix — it lets the upcoming guard wrapper (S02) insert telemetry rows into `daemon_events` without writing direct SQL or bypassing the ORM.

The CLI is the single agent-to-DB bridge in this project (`orch/CLAUDE.md`). Any external script that wants to record a `daemon_events` row should go through the CLI; bypassing the CLI couples external code to DB schema details.

## Requirements

### 1. Create `orch/cli/event_commands.py`

Add a single Click command:

```bash
uv run iw daemon-event \
    --event-type step_narration_exit \
    --entity-type work_item \
    --entity-id F-00089 \
    --message "Step S05 narrated without executing — reprompting (attempt 1)" \
    --metadata '{"step_id":"S05","reprompt_attempt":1,"max_reprompts":5,"last_assistant_text":"I'\''ll now..."}'
```

Behaviour:

- Resolves `project_id` via the standard CLI `resolve_project(ctx)` helper.
- Validates that `--event-type` is a non-empty string (free-form TEXT, no enum).
- Validates that `--metadata`, if supplied, parses as JSON.
- Inserts a row into `daemon_events` with all six columns (`project_id`, `event_type`, `entity_type`, `entity_id`, `message`, `event_metadata`).
- Returns the inserted row's `id` via stdout (one line; respect `-j/--json` for machine-readable output).
- Exits 0 on success, non-zero with a clear stderr message on validation failure.

### 2. Register the command in `orch/cli/__init__.py`

Import `daemon_event` and add it to the Click group exactly like the existing commands (`step_done`, `step_fail`, etc.). Keep alphabetical ordering if the file uses one.

### 3. Match existing conventions

- Use the existing `get_session` pattern from `ctx.obj["get_session"]`.
- Use `output_error` for error paths and `click.echo` for the success line; this matches `step_commands.py` and `item_commands.py`.
- Do NOT add a new model, new helper module, or new dependency — `DaemonEvent` already exists.
- Remember: Python attribute is `event_metadata`; DB column is `metadata` (`orch/CLAUDE.md` "Gotcha").

### 4. Type hints

`metadata` parameter type: `dict[str, Any]` after JSON parsing. The function signature must match the surrounding file's style (Click decorators + typed function body).

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write a small unit test in `tests/unit/test_event_command.py` (or wherever sibling `step_commands` tests live — match the existing layout) that calls `daemon_event` via Click's `CliRunner` and asserts a row appears in `daemon_events` with the supplied fields. Run it. Confirm `AttributeError` or `ImportError` from the missing command.
2. **GREEN**: Implement the command. Re-run the test. It must pass.
3. **REFACTOR**: Extract argument parsing only if duplication justifies it; otherwise keep inline.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass against the files you touched.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_event_command.py -v
```

(or whichever file holds your test). Do NOT run `make test-unit` here — that's the downstream QV gate.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00114",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/event_commands.py",
    "orch/cli/__init__.py",
    "tests/unit/test_event_command.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_event_command.py::test_inserts_row — ModuleNotFoundError / AttributeError: no `daemon_event` in orch.cli",
  "blockers": [],
  "notes": "Document the row count / entity routing rules so S02 can call this confidently."
}
```
