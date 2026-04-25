# IW AI Core — Worktree Container Isolation

**Feature**: F-00062
**Reference**: R-00064 (per-worktree DB research)

---

## Overview

Each parallel AI-agent work item gets its own isolated runtime environment via a per-worktree Docker Compose stack. This prevents parallel agents from contending for the same database or service ports, enabling truly independent parallel execution.

The per-worktree stack consists of:
- A **Postgres container** (ephemeral, tmpfs data) — per-worktree database
- An **app server container** (optional, project-defined) — e.g., a Django/Node server the agent's Backend step exercises

What stays **global** (shared, not isolated):
- The **orchestration database** on port 5433 — holds all IW AI Core metadata (work items, batches, step runs, daemon events)
- The **daemon process** — single, polls all projects
- The **dashboard** — single, port 9900

Isolation is **opt-in per project** via an `ai-dev/iw-config/` directory in the project repo.

---

## The `ai-dev/iw-config/` Contract

The project repo must contain an `ai-dev/iw-config/` directory with three files. The daemon discovers this directory at startup (per-project, via `.iw-orch.json` or `projects.toml`).

**Discovery**: The daemon reads config from `<project_repo>/ai-dev/iw-config/`, NOT from the main iw-ai-core repo. Each project's worktree has its own copy.

**Legacy fallback**: If a project has no `ai-dev/iw-config/` directory, it runs in legacy mode — no per-worktree stack, no port discovery, no `${WORKTREE_*}` placeholders available to agents.

### `worktree-compose.template.yml`

Jinja2 template rendered once per batch item launch. The daemon substitutes:

| Variable | Source |
|----------|--------|
| `{{ batch_item_id }}` | `BatchItem.id` |
| `{{ worktree_path }}` | `BatchItem.worktree_info['path']` |
| `{{ project_name }}` | `ProjectConfig.name` |

**Required labels** (used by the reaper):

```yaml
labels:
  iwcore.role: per-worktree
  iwcore.batch_item: "{{ batch_item_id }}"
```

**Dynamic ports**: No `ports:` mapping. The daemon discovers published ports via `docker compose ps -q` after `up()` succeeds and stores them in `BatchItem.worktree_db_port` / `BatchItem.worktree_app_port`.

**tmpfs for ephemeral DB**:

```yaml
services:
  db:
    volumes:
      - type: tmpfs
        target: /var/lib/postgresql/data
```

**extra_hosts for host gateway**:

```yaml
services:
  db:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Rendered output path: `<worktree_path>/.iw/docker-compose-<batch_item_id>.yml`

### `worktree-env.toml`

Environment injection for the agent's process.

**`[port_to_env]`** — map discovered ports to env vars the agent sees:

```toml
[port_to_env]
5432 = "WORKTREE_DB_PORT"   # maps discovered DB host port → env var
8080 = "WORKTREE_APP_PORT"  # maps discovered app host port → env var
```

**`[env_overrides]`** — static overrides:

```toml
[env_overrides]
IW_CORE_DB_HOST = "localhost"
IW_CORE_DB_PORT = "${WORKTREE_DB_PORT}"   # substituted at runtime
IW_CORE_PER_WORKTREE_DB = "true"
```

**`[env_passthrough].keep`** — env vars from the daemon's environment to pass through (supports globs):

```toml
[env_passthrough]
keep = [
  "IW_CORE_ORCH_DB_HOST",
  "IW_CORE_ORCH_DB_PORT",
  "IW_CORE_ORCH_DB_NAME",
  "IW_CORE_ORCH_DB_USER",
  "IW_CORE_ORCH_DB_PASSWORD",
  "IW_CORE_AGENT_CONTEXT",
  "PATH",
  "HOME",
]
```

### `worktree-seed.sh`

Optional seed script run after `compose up` succeeds and before the agent launches.

**Timing**: `worktree_compose.up()` → seed script → `_launch_next_step()`

**Environment**: The script receives the worktree's `.env` (if present) in its environment, plus all `env_passthrough.keep` vars and substituted `env_overrides`.

**Failure semantics**: Non-zero exit → `BatchItem.status = setup_failed`; no step launch; `down()` is called.

**iW AI Core reference implementation** (`orch/daemon/worktree_compose.py`):

```bash
#!/bin/bash
# pg_dump from global orch DB → restore into per-worktree DB
set -e

export PGPASSWORD="$IW_CORE_ORCH_DB_PASSWORD"
pg_dump -h "$IW_CORE_ORCH_DB_HOST" -p "$IW_CORE_ORCH_DB_PORT" -U "$IW_CORE_ORCH_DB_USER" -d "$IW_CORE_ORCH_DB_NAME" \
  --schema-only | psql -h localhost -p "$WORKTREE_DB_PORT" -U postgres
```

Other projects provide their own seed script in `ai-dev/iw-config/worktree-seed.sh`.

---

## Daemon Lifecycle

### `worktree_compose.up()` — when it fires

After `worktree_setup.sh` returns successfully and before `_launch_next_step()`, the daemon calls `worktree_compose.up()` if the project has `ai-dev/iw-config/`:

```python
# orch/daemon/batch_manager.py:_launch_item()
worktree_info = self._setup_worktree(item_id)          # → setting_up
# ...
batch_item.status = 'executing'
self.db.commit()

# NEW: per-worktree compose stack
if self.project_config.has_iw_config:
    up_result = self.worktree_compose.up(batch_item, worktree_info)
    if not up_result.success:
        batch_item.status = 'setup_failed'
        self.worktree_compose.down(batch_item.id)
        return

# Phase 2: Launch first pending step
self._launch_next_step(item_id, worktree_info)
```

**Phase failure** (`up_result.success == False`) → `setup_failed`, no step launch, `down()` called.

### `worktree_compose.down()` — when it fires

Called on terminal status transitions:

- `merged` / `failed` / `skipped` / `killed` / `setup_failed`
- Via `batch_manager._complete_item()` and `_on_step_failed()`

Container naming: `iwcore-<batch_item_id>`

Persisted state:
- `BatchItem.worktree_db_port` — discovered DB host port
- `BatchItem.worktree_app_port` — discovered app host port (optional)
- `BatchItem.worktree_compose_path` — absolute path to rendered compose file

---

## The Reaper

The reaper (`orch/daemon/worktree_reaper.py`) scans for and cleans up orphaned or stale containers.

### What it scans

All containers with `label=iwcore.role=per-worktree`.

### Classification

| State | Condition |
|-------|-----------|
| **Active** | `BatchItem` exists with matching `worktree_compose_path` AND `BatchItem.status` is non-terminal |
| **Stale** | `BatchItem` exists with matching `worktree_compose_path` BUT `BatchItem.status` is terminal (merged/failed/etc.) |
| **Orphan** | No `BatchItem` with this `worktree_compose_path` exists |

### When it runs

- **Daemon startup**: `_startup_health_check()` calls `worktree_reaper.run()`
- **Periodic**: Every poll cycle, after `process_batches()` — reaper runs silently, only logs/detects

### Operator controls

Force-teardown via dashboard: Worktrees page → trash icon on the worktree row.

---

## Daemon-Restart Behavior

On restart, the daemon re-attaches to running per-worktree stacks:

```python
# orch/daemon/main.py:_reattach_worktrees()
# Queries non-terminal BatchItems with worktree_compose_path set
for batch_item in non_terminal_items:
    if compose_stack_is_running(batch_item.worktree_compose_path):
        log("Re-attached to running stack for %s", batch_item.id)
    elif compose_file_exists(batch_item.worktree_compose_path):
        # Stack vanished (host restart?) — re-run up()
        up_result = worktree_compose.up(batch_item, worktree_info)
        # ...
    else:
        # Both gone — leave as-is (operator must investigate)
```

**No double `up()`** for already-running stacks — the daemon checks `docker compose ps` before invoking `up()`.

---

## Step Prompt Placeholders

The daemon substitutes these placeholders in step prompts at launch time:

| Placeholder | Source |
|-------------|--------|
| `${WORKTREE_APP_PORT}` | `BatchItem.worktree_app_port` (str) |
| `${WORKTREE_DB_PORT}` | `BatchItem.worktree_db_port` (str) |
| `${WORKTREE_PATH}` | `BatchItem.worktree_info['path']` |
| `${BATCH_ITEM_ID}` | `BatchItem.id` |
| `${PROJECT_NAME}` | `ProjectConfig.name` |

**Legacy items** (no `worktree_compose_path`): placeholders are left as-is and raise `UnresolvedWorktreePlaceholderError` if any `${WORKTREE_*}` appears in the prompt — the daemon refuses to launch.

---

## Agent Permissions (The Contract)

| Action | Allowed? |
|--------|----------|
| Inspect `.iw/docker-compose-<id>.yml` | Yes — read-only |
| `docker compose ps\|logs\|restart` on worktree stack | Yes — via worktree's own stack |
| Edit the compose file | **No** — generated by daemon |
| `docker compose up\|down` on worktree stack | **No** — owned by daemon |
| Modify daemon's compose lifecycle | **No** |
| `make test-integration` | **Yes** — still uses testcontainers (rule unchanged) |
| `IW_CORE_PER_WORKTREE_DB=true` + alembic against per-worktree DB | **Yes** — only for per-worktree DB |

**`safe_migrate.AgentContextForbiddenError` is RELAXED** for per-worktree DB only (`IW_CORE_PER_WORKTREE_DB=true`). The live orch DB on port 5433 remains protected regardless.

---

## `.gitignore` Enforcement

The daemon **refuses to launch** a worktree for a project whose `.gitignore` is missing:

- `.env`
- `.iw/` (or `**/.iw/`)

This prevents committed secrets and rendered compose files from entering version control.

No auto-fix — operator must update the project's `.gitignore` before the project can use per-worktree isolation.

---

## Operator Runbook

### Check container status

```bash
docker ps --filter label=iwcore.role
```

### Inspect a worktree's compose file

```bash
cat <worktree>/.iw/docker-compose-<id>.yml
```

### Stream logs

```bash
docker compose -p iwcore-<batch_item_id> logs -f
```

### Force-teardown via dashboard

Navigate to `/worktrees` → click the trash icon on the worktree row.

### Debug a seed failure

1. Find the `DaemonEvent` with `phase='seed', success=false`
2. Check `DaemonEvent.event_metadata['error']` for the seed script's stderr
3. Review the project's `ai-dev/iw-config/worktree-seed.sh`

### Recover from a leaked container

```bash
docker ps --filter label=iwcore.role -q | xargs docker rm -fv
```

---

## Daemon-Host Prerequisites

| Prerequisite | Why |
|--------------|-----|
| Docker engine installed + running | Container runtime |
| `docker compose` plugin (v2) | Per-worktree stack management |
| `pg_dump` + `psql` on PATH | iw-ai-core's reference seed script |
| Project-specific seed script prereqs | Documented per-project in their `ai-dev/iw-config/` |

---

## Multi-Project Scope

This Feature ships **iw-ai-core's reference implementation only**.

- `innoforge` and `cv` get follow-up Incidents to add their own `ai-dev/iw-config/`
- Until those land, those projects use the **legacy fallback** (no per-worktree stack, no `${WORKTREE_*}` placeholders)

---

## Reference

| File | Purpose |
|------|---------|
| `orch/daemon/worktree_compose.py` | `up()`, `down()`, port discovery, Jinja2 rendering |
| `orch/daemon/worktree_reaper.py` | Label-based orphan/stale container reaper |
| `orch/daemon/batch_manager.py:_launch_item()` | Orchestrates setup → compose up → seed → launch |
| `orch/db/models.py:BatchItem` | `worktree_db_port`, `worktree_app_port`, `worktree_compose_path` columns |
| `orch/db/safe_migrate.py` | `AgentContextForbiddenError` relaxation for per-worktree DB |
| `docs/IW_AI_Core_Daemon_Design.md` | Daemon lifecycle, worktree container lifecycle section |
| `docs/IW_AI_Core_Agent_Constraints.md` | Docker off-limits rules + per-worktree DB exception |