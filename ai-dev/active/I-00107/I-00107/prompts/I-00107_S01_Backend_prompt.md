# I-00107_S01_Backend_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
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

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This fix touches in-memory daemon state only. It MUST NOT add, modify, or run any alembic migration. If you find yourself reaching for `alembic revision`, STOP and raise a blocker — the design did not anticipate a migration here.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list and status, prefer `uv run iw item-status I-00107 --json`. The `workflow-manifest.json` file is a design-time snapshot (CR-00023).
- `ai-dev/active/I-00107/I-00107_Issue_Design.md` — Design document
- `orch/daemon/main.py` — `Daemon._reload_projects_if_stale()` lives here (approx lines 621-655)
- `orch/daemon/project_registry.py` — `ProjectRegistry.reload()`, `_build_project_config()`, `ProjectConfig` dataclass
- `orch/daemon/batch_manager.py` — for the BatchManager constructor signature `(project_id, project_config, session_factory, daemon_config)` (line 85)

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_S01_Backend_report.md` — Step report

## Context

You are implementing the fix for **I-00107: `daemon reload` (SIGHUP) does not apply `.iw-orch.json` changes for an already-running project**.

Read the design document first. The root-cause section is precise about where the gap is — `ProjectRegistry.reload()` correctly re-parses each project's `.iw-orch.json` into a fresh `ProjectConfig`, but its `changes` dict classifies the project as `"unchanged"` (because `projects.toml` itself didn't move), and `Daemon._reload_projects_if_stale()` has no handler for that case (and even its `"enabled"`/`"disabled"` branches forget to rebuild `self.managers[pid]`).

Then read `CLAUDE.md` and `orch/CLAUDE.md` for daemon architecture and conventions.

## Requirements

### 1. Detect `.iw-orch.json` content drift inside `ProjectRegistry.reload()`

Edit `orch/daemon/project_registry.py:598-643`. Today the per-project branch decides among `added`, `removed`, `disabled`, `enabled`, `unchanged` based only on presence and the `enabled` flag.

Extend it so that when both old and new `ProjectConfig` exist and both are enabled, you compare the two `ProjectConfig` objects and:

- If they are structurally identical → keep `changes[pid] = "unchanged"` (no churn).
- If they differ → emit a new change-type — recommended name: `"changed"`.

The comparison must cover ALL `ProjectConfig` fields that come from `.iw-orch.json` (overlap patterns, max_parallel, fix_cycle_max, browser_verification settings, test_config/quality_config, post_archive_commands, worktree_base, cli_tool, …). Because `ProjectConfig` is a `dataclass`, `==` already does this field-by-field. Just keep references to the old and new objects and compare with `==`. (Audit the dataclass for any field that holds an unhashable mutable container — Python's default dataclass `__eq__` handles lists/dicts/tuples fine, so this should "just work".)

Update the `"""..."""` docstring to add the new change-type to the list of possible values.

### 2. Handle the new change-type in `Daemon._reload_projects_if_stale()` AND fix the `enabled`/`disabled` branches

Edit `orch/daemon/main.py:621-655`. Add a branch for the new change-type that:

- Replaces `self.projects[project_id]` with the new `ProjectConfig`.
- Replaces `self.managers[project_id]` with a freshly constructed `BatchManager(project_id, new_cfg, self._session_factory, self.config)` — the same constructor signature already used by the `"added"` branch at line 633.
- Calls `sync_project_to_db(...)` (same as the `"added"` branch at line 638) so the DB `projects.config` JSONB column reflects the new config.
- Emits a `DaemonEvent` (see Requirement 3) — once per project, with a short summary of what changed (e.g. the list of `ProjectConfig` fields that differ; the simplest robust implementation is `sorted(f.name for f in fields(old) if getattr(old, f.name) != getattr(new, f.name))`).
- Logs an INFO line, mirroring the style of the existing `"added"`/`"disabled"` log lines.

ALSO fix the `"enabled"` and `"disabled"` branches: they currently update `self.projects[project_id]` but do NOT rebuild `self.managers[project_id]`. A re-enabled project should get a fresh BatchManager (with whatever the current `.iw-orch.json` says); a disabled project should have its manager removed from `self.managers` (so subsequent poll cycles skip it cleanly — match whatever the existing daemon loop does for missing manager entries). Verify both halves by reading the loop body in `Daemon.run()` and `_process_batch` callsites.

### 3. Emit `project_config_reloaded` daemon event

In the same branch that rebuilds the BatchManager, write a `DaemonEvent` row via the same `emit_event` helper used by the `"added"` branch (`from orch.daemon.main import emit_event`, line 639). Use:

- `event_type = "project_config_reloaded"`
- `entity_id = project_id`
- `entity_type = "project"` (match the convention used by the `project_discovered` event)
- `message`: `f"Project config reloaded for {project_id} — {len(changed_fields)} field(s) changed"`
- `metadata = {"project_id": project_id, "changed_fields": changed_fields}` (where `changed_fields` is the sorted list computed in Requirement 2)

Do NOT emit this event for `"unchanged"` projects — that would defeat the purpose of the no-churn check.

### 4. Do NOT change `is_stale()` or `_handle_reload()`

Out of scope for this fix:

- `ProjectRegistry.is_stale()` at lines 591-596 continues to track only `projects.toml`'s mtime. SIGHUP forces `_mtime = 0.0` so the reload path always runs; that path is what we're fixing. Bare-edit detection (an operator who edits `.iw-orch.json` without SIGHUP) is noted as a possible follow-up in the design's Notes section — do NOT implement it here.
- The signal handler at lines 688-692 stays as-is.

Keep the diff small. The whole fix should be on the order of 30-50 added lines across the two files.

### 5. Preserve the "preserve last-known-good on parse failure" policy

`try_load_projects_toml` already returns `None` on a malformed `projects.toml` and the existing code preserves the old registry in that case. Per-project `.iw-orch.json` parse failures are handled in `_build_project_config` (`project_registry.py:128-141`) which logs a warning and falls back to defaults. Your new branch in `_reload_projects_if_stale` must NOT crash if `_build_project_config` returned a "defaults-fallback" `ProjectConfig` — treat it the same as any other fresh config. The unit test in S03 will cover this case explicitly (`test_reload_does_not_refresh_when_only_projects_toml_unchanged_iw_orch_json_unparseable`).

### 6. TDD note

This is a Backend step that adds behaviour-implementing code. The dedicated reproduction + regression tests live in S03 (`tests-impl`), per the design's File Manifest and TDD Approach. The recommended workflow:

1. Implement the change in `orch/daemon/project_registry.py` and `orch/daemon/main.py`.
2. Run targeted existing coverage (Requirement 7 below) to verify no regression.
3. Report `tdd_red_evidence` as `"n/a — reproduction + regression tests delegated to S03 tests-impl per design doc TDD Approach"`.

This is consistent with the design's File Manifest, which assigns the new test file to S03.

### 7. Test verification

Run ONLY targeted tests; do NOT run `make test-unit` or `make test-integration` (those are the S11 / S12 QV gates).

```bash
uv run pytest tests/unit/daemon/ -v 2>&1 | tail -40
```

If any existing `tests/unit/daemon/` test fails because of your change, fix it before reporting completion. The new test file from S03 does not exist yet when S01 runs.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for daemon architecture and conventions.

Specific rules that apply here:

- `DaemonEvent.metadata` is named `event_metadata` in Python; the DB column is `metadata`. Use the SQLAlchemy attribute name when writing to the model (the existing `emit_event` helper in `orch/daemon/main.py` already handles this correctly).
- Logger style: `logger.info("Project config reloaded: %r (%d fields)", project_id, len(changed_fields))` — `%r`-style placeholders, not f-strings, for logger calls (match the existing surrounding code).
- Imports: `from dataclasses import fields` — add it to the existing `from dataclasses import ...` line in `project_registry.py` if it isn't already imported there.
- Do NOT add a new module; the fix lives in the two existing files.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, you MUST run:

1. **`make format`** — auto-fixes formatting drift. If it reformats files, inspect the diff and re-stage.
2. **`make typecheck`** — must report zero errors involving the files you touched.
3. **`make lint`** — must report zero errors involving the files you touched.

If a tool isn't available, STOP and raise a blocker.

Record results in the `preflight` field of your result contract.

## Test Verification (NON-NEGOTIABLE)

Targeted only — see Requirement 7. Do not run `make test-unit` / `make test-integration` here.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00107",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/project_registry.py",
    "orch/daemon/main.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — reproduction + regression tests delegated to S03 tests-impl per design doc TDD Approach",
  "blockers": [],
  "notes": ""
}
```
