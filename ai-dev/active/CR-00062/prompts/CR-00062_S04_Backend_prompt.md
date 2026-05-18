# CR-00062_S04_Backend_prompt

**Work Item**: CR-00062 — Add Pi (pi.dev) as a third agent runtime
**Step**: S04
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures in tests are the only exception. Read-only `docker ps / inspect / logs` allowed; everything else (`docker compose up/down/restart`, container `kill/stop/rm/restart`, `volume rm / prune`, `system / container / image prune`) is forbidden. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are NOT touching migrations. Do NOT run `alembic upgrade / downgrade / stamp` against the live orch DB.

## Input Files

- Runtime step state: `uv run iw item-status CR-00062 --json`
- Design doc: `ai-dev/active/CR-00062/CR-00062_CR_Design.md`
- Master agent tree to mirror: `agents/claude/` (31 files; same agent slugs Pi must support)
- Sync engine to extend: `orch/skills/sync_agents.py`
- CLI surface to extend: `orch/cli/skills_commands.py:94-152`
- Reference for Pi's skill/agent discovery rules: `docs/research/R-00072-pi-dashboard-embedding.md` §4

## Output Files

- New directory `agents/pi/` with .md files mirroring `agents/claude/`
- Edits to `orch/skills/sync_agents.py` (dataclass field + sync call)
- Edits to `orch/cli/skills_commands.py` (JSON output + human output + total)
- `ai-dev/active/CR-00062/reports/CR-00062_S04_Backend_report.md`

## Context

You are implementing S04 of CR-00062 — creating the master `agents/pi/` tree and extending the sync engine + CLI to copy it into `<project>/.pi/agents/` and report counts. This step runs in parallel with S03. Read the design doc's *Affected Components* table rows for `agents/pi/`, `orch/skills/sync_agents.py`, `orch/cli/skills_commands.py`, and *Acceptance Criteria* AC3 for the assertions your work must satisfy.

## Requirements

### 1. Create the `agents/pi/` master directory

For each .md file in `agents/claude/`, create a peer `.md` file in `agents/pi/` with the same agent slug as the filename (e.g., `agents/claude/backend-impl.md` → `agents/pi/backend-impl.md`).

For each file, you have two options:

a) **Frontmatter passes through unchanged**. Pi reads YAML frontmatter compatibly with Claude for the common fields (`name`, `description`, `tools`). If a Claude file's frontmatter has only those fields, the Pi copy is byte-identical.

b) **Frontmatter needs translation**. If a Claude agent file references Claude-only fields (e.g., `model` set to a Claude-specific id) or uses a Claude-specific tool name (e.g., references to `mcp__claude_...` tools), translate to Pi's equivalent or strip the field and add a one-line `<!-- pi-port: stripped <field>, reason -->` comment immediately below the frontmatter. Pi's universal skill discovery (`.pi/skills/`, `.agents/skills/`, `~/.claude/skills/`, `~/.codex/skills/`) means the body — which references skills by name — does NOT need translation.

If a particular file genuinely cannot be mapped (rare — most agent files are runtime-agnostic), stub it with:

```yaml
---
name: <slug>
description: <slug> — pi port pending
---

<!-- TODO(CR-00062-followup): port full agents/claude/<slug>.md body to Pi extension conventions. Stub created 2026-05-18. -->

See `agents/claude/<slug>.md` for the Claude version.
```

…and note the stubbed slug(s) in your report.

The directory must contain **exactly the same set of .md filenames** as `agents/claude/`. AC3 asserts the count matches.

### 2. Extend `AgentSyncResult` (`orch/skills/sync_agents.py`)

Add a new field after `claude_agents_synced`:

```python
@dataclass
class AgentSyncResult:
    claude_agents_synced: int = 0
    pi_agents_synced: int = 0
    opencode_agents_synced: int = 0
    opencode_commands_synced: int = 0
    errors: list[str] = field(default_factory=list)
```

(Order: claude → pi → opencode_* matches the documented runtime trio order and avoids splitting OpenCode's two counters.)

### 3. Extend `sync_agents_and_commands()` (`orch/skills/sync_agents.py`)

Add a third `_sync_directory(...)` call after the Claude one and before the OpenCode one:

```python
# Pi agents
count, errors = _sync_directory(
    platform_root / "agents" / "pi",
    project_path / ".pi" / "agents",
)
result.pi_agents_synced = count
result.errors.extend(errors)
```

The existing `_sync_directory()` helper already creates the target directory if missing (`target_dir.mkdir(parents=True, exist_ok=True)`), so no new code is needed for the `.pi/agents/` path.

### 4. Extend the CLI surface (`orch/cli/skills_commands.py`)

In `sync_agents_cmd`:

a) **JSON output** (lines 127–138): add a `"pi_agents"` key:

```python
json.dumps({
    "project_id": project_id,
    "claude_agents": result.claude_agents_synced,
    "pi_agents": result.pi_agents_synced,
    "opencode_agents": result.opencode_agents_synced,
    "opencode_commands": result.opencode_commands_synced,
    "errors": result.errors,
})
```

b) **Human output** (lines 141–151): add a `Pi agents: N` line after the Claude one and adjust the total:

```python
click.echo(f"Syncing agents for {project_id}...")
click.echo(f"  Claude agents: {result.claude_agents_synced}")
click.echo(f"  Pi agents: {result.pi_agents_synced}")
click.echo(f"  OpenCode agents: {result.opencode_agents_synced}")
click.echo(f"  OpenCode commands: {result.opencode_commands_synced}")
for err in result.errors:
    click.echo(f"  WARNING: {err}", err=True)
total = (
    result.claude_agents_synced
    + result.pi_agents_synced
    + result.opencode_agents_synced
    + result.opencode_commands_synced
)
click.echo(f"Total: {total} files synced.")
```

### 5. Do NOT touch `projects.toml`

Per the design's *Notes* section and the GO/NO-GO decision, no project is switched to `cli_tool = "pi"` in this CR. Leave `projects.toml` untouched.

## Project Conventions

Read `CLAUDE.md`, `orch/CLAUDE.md` (package layout, CLI command groups table). Click 8.1+ idiom matches the existing surrounding code; mirror it.

## TDD Requirement

Write a targeted RED test BEFORE implementation:

```bash
uv run pytest tests/unit/test_sync_agents_pi.py::test_sync_creates_pi_agents_directory -v
```

Expected RED: `AttributeError: 'AgentSyncResult' object has no attribute 'pi_agents_synced'`. Capture the failure line into `tdd_red_evidence`. Then implement and re-run for GREEN.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

Record in `preflight`.

## Test Verification (NON-NEGOTIABLE)

Run targeted unit tests for files you touched:

```bash
uv run pytest tests/unit/test_sync_agents_pi.py -v
```

Do NOT run the full unit or integration suite.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "backend-impl",
  "work_item": "CR-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "agents/pi/<31 .md files>",
    "orch/skills/sync_agents.py",
    "orch/cli/skills_commands.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed",
  "tdd_red_evidence": "<test id> — AttributeError: ... pi_agents_synced",
  "blockers": [],
  "notes": "list of stubbed agent slugs (if any); list of translated frontmatter fields and reasons"
}
```
