# F-00081_S02_Backend_prompt

**Work Item**: F-00081 -- Per-Item / Per-Step Agent + Model Override
**Step**: S02
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures are exempt. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

S01 owns the migration. You inherit `agent_runtime_options` and the new FK columns. Do NOT touch alembic or the live DB.

## Input Files

- `uv run iw item-status F-00081 --json` — runtime step state.
- `ai-dev/active/F-00081/F-00081_Feature_Design.md` — the design.
- `ai-dev/active/F-00081/reports/F-00081_S01_Database_report.md` — what S01 actually created (read this; do not assume).
- Existing files you will modify or read:
  - `orch/daemon/project_registry.py` (line 117 reads `cli_tool` from `.iw-orch.json`).
  - `orch/daemon/batch_manager.py` (line ~989 reads `cli_tool`; line ~1109 builds the launch command).
  - `orch/daemon/fix_cycle.py` (line ~1449 reads `cli_tool`; line ~1456 / ~1483 builds the launch command).
  - `orch/db/models.py` — the new `AgentRuntimeOption` and the FK columns S01 added.
  - `orch/daemon/state_machine.py` and the rest of `orch/daemon/` for context only.
- `projects.toml` — for the new `model` field (and existing `cli_tool`).

## Output Files

- `ai-dev/active/F-00081/reports/F-00081_S02_Backend_report.md` — step report.
- New files:
  - `orch/agent_runtime/__init__.py`
  - `orch/agent_runtime/resolver.py` — pure cascade-resolution function.
  - `orch/agent_runtime/audit.py` — DaemonEvent emission helper for override changes (single + bulk).
- Edits:
  - `orch/daemon/project_registry.py` — read `cli_tool` and `model` from `projects.toml` (entry-level), with `.iw-orch.json` `cli_tool` as fallback for backwards compat. Extend `ProjectConfig` dataclass with `model: str` field.
  - `orch/daemon/batch_manager.py:1109` — call resolver, inject `--model <m>` into the launched command, write `agent_runtime_option_id` onto the new `step_runs` row.
  - `orch/daemon/fix_cycle.py:1456` and `:1483` — same.

## Context

You are implementing the Python backend for **F-00081**. The catalogue table and the FK columns already exist (S01). Your job is the runtime resolution + launch-command injection + audit emission. Read the design doc carefully — especially the cascade order, AC1–AC5, AC7, and the "Boundary Behavior" table (every row must have at least one test).

## Requirements

### 1. Resolver — `orch/agent_runtime/resolver.py`

A small pure function (no DB I/O of its own — caller passes the SQLAlchemy session and the relevant rows). Signature:

```python
def resolve_runtime(
    session: Session,
    *,
    step: WorkflowStep,
    item: WorkItem,
    project: ProjectConfig,
) -> AgentRuntimeOption:
    """Cascade: step.agent_runtime_option_id → item.agent_runtime_option_id
       → projects.toml (cli_tool, model) lookup → catalogue is_default=true.
       Disabled rows in the chain are skipped (treated as None) with a warning log.
       If everything fails, raise RuntimeError — this should be impossible because
       the migration enforces exactly one is_default=true row.
    """
```

Skipping a disabled override is important — see the "Override points to disabled row" boundary case.

### 2. Project registry extension — `orch/daemon/project_registry.py`

- Read `cli_tool` from the `projects.toml` entry first (key: `entry.get("cli_tool")`); fall back to `iw_config.get("cli_tool", "opencode")` from `.iw-orch.json` for backwards compatibility.
- Read `model` from the `projects.toml` entry (`entry.get("model")`); fall back to `"minimax"`.
- Add `model: str` to the `ProjectConfig` dataclass alongside `cli_tool`.
- At project load time, log a warning (do NOT crash) if the configured `(cli_tool, model)` pair does not exist in `agent_runtime_options` — boundary case "Project default in projects.toml references a missing pair".

### 3. Launch-command refactor

In **batch_manager.py:1109** and **fix_cycle.py:1456 / 1483**:

1. Call the resolver to obtain the `AgentRuntimeOption` row.
2. Build the command with `--model`:
   - opencode: `opencode run "$(cat <prompt>)" --model <model> --dangerously-skip-permissions`
     - **VERIFY** the exact OpenCode flag shape against the locally installed binary before committing. Run `opencode --help | grep -i model` (read-only) to confirm. If the flag form differs (e.g. `--model anthropic/claude-sonnet-4-6` vs `--model claude-sonnet-4-6`), document this in your report and adjust accordingly.
   - claude: `claude -p "$(cat <prompt>)" --model <model> --dangerously-skip-permissions`
3. When the StepRun row is created (currently around batch_manager.py:1031 / 1208 and fix_cycle.py's StepRun-creation site), set `agent_runtime_option_id = option.id` (and continue to set `cli_tool` to the resolved cli_tool string for backwards compatibility with existing reports).
4. Pass `model` into `_build_agent_env` so per-CLI env vars (`OPENCODE_MODEL`, `ANTHROPIC_MODEL`) are also set as a belt-and-braces fallback in case the CLI flag is silently ignored.

### 4. DaemonEvent emission — `orch/agent_runtime/audit.py`

A single helper:

```python
def emit_runtime_override_changed(
    session: Session,
    *,
    project_id: str,
    item_id: str,
    scope: str,                 # "item" | "step" | "bulk"
    step_ids: list[str] | None, # populated for step + bulk; None for item-only
    old_option_id: int | None,
    new_option_id: int | None,
    actor: str,
) -> None:
    """Emit ONE daemon_events row regardless of how many steps were affected (AC6).
       event_type='runtime_override_changed'.
    """
```

The API layer (S04) calls this exactly once per request, even when the bulk endpoint touches N steps.

### 5. Coverage

You write tests for the resolver and the audit helper in S02 (TDD). The integration tests covering the launch-command refactor and the cascade end-to-end live in S06.

Suggested unit test locations:
- `tests/unit/test_agent_runtime_resolver.py` — table-driven cascade tests.
- `tests/unit/test_agent_runtime_audit.py` — DaemonEvent shape.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`:

- Sync SQLAlchemy. The resolver and audit helper take a Session, never open one themselves.
- `DaemonEvent.metadata` is named `event_metadata` in Python — SQLAlchemy reserves `metadata`.
- Daemon code lives in `orch/daemon/`. The new `orch/agent_runtime/` package is a sibling — it should NOT import from `orch/daemon/` (the daemon imports from it).

## TDD Requirement

Red-Green-Refactor. Resolver tests first, then implement; audit-helper tests first, then implement; only after the unit tests are green should you wire the launch-site refactor.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before completion: `make format` → `make typecheck` → `make lint`.

## Test Verification (NON-NEGOTIABLE)

`make test-unit` and `make test-integration` must pass.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "backend-impl",
  "work_item": "F-00081",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/agent_runtime/__init__.py",
    "orch/agent_runtime/resolver.py",
    "orch/agent_runtime/audit.py",
    "orch/daemon/project_registry.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "tests/unit/test_agent_runtime_resolver.py",
    "tests/unit/test_agent_runtime_audit.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": "Note any deviation from the assumed --model flag form here."
}
```
