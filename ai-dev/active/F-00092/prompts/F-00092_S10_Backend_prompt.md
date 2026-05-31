# F-00092_S10_Backend_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S10
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Docs-only step. No code, no Docker, no migrations.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Notes** (same-disk caveat,
  identity nuance), **Scope**, AC list.
- Reports from S03/S05/S06/S09 — final config var names, CLI commands, restore
  signature.
- `README.md`, `CLAUDE.md`, `docs/IW_AI_Core_DB_Setup.md` — current content/style.
- `/opt/postgres/data/backup_260422/README.txt` is the historical reference for the
  incident narrative (do not modify it).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S10_Backend_report.md`.
- Doc edits + the new `docs/IW_AI_Core_DB_Backup_Restore.md`.

## Context

Document the backup subsystem as a shipped product feature. This step is
**docs-only** — do not change code, config defaults, or behavior; only describe what
S01–S09 implemented.

## Requirements

### 1. `README.md`

Add a concise "Database backups" section: what it does (daily scheduled + on-demand),
the `iw db-backup` / `./ai-core.sh db backup` commands, the `IW_CORE_BACKUP_*`
settings, and a pointer to the restore guide.

### 2. `CLAUDE.md`

- Document the `IW_CORE_BACKUP_*` config vars in the Configuration section.
- Add a **⚠️ same-disk limitation** note: the default
  `IW_CORE_BACKUP_DIR=/opt/postgres/data/backups` is on the same disk as the data —
  it guards against operator mistakes, bad migrations, and container displacement
  (the actual recurring incidents), but NOT disk failure or `rm -rf` of the data
  dir; the path is configurable to move off-host. Reference the displacement
  incidents and I-00122.
- Add a **Critical Rule**: agents MUST NOT read, write, move, or delete anything in
  the backup directory.

### 3. `docs/IW_AI_Core_DB_Setup.md`

Add a "Backups" section/link cross-referencing the new restore guide and the
`IW_CORE_BACKUP_*` config, consistent with the existing production-vs-bootstrap and
2026-04-22 incident narrative.

### 4. NEW `docs/IW_AI_Core_DB_Backup_Restore.md`

A complete restore runbook covering:
- What a backup set contains (dump archive, globals SQL, manifest).
- **Safe restore** (default): `iw db-backup restore --from <set>` into a non-prod
  target, then the automatic identity check + row-count print.
- **In-place prod swap** procedure (the deliberate, override path), including the
  globals-first ordering and how to bring the restored cluster up on 5433 (tie in
  with I-00122's `db start-prod` / `IW_CORE_DB_DATA_DIR`).
- The `iw_core_instance` / `IW_CORE_EXPECTED_INSTANCE_ID` identity handling (a
  restore keeps the same instance id, so the pin still matches; how to re-pin if
  restoring to a new identity).
- RTO expectation (minutes at current ~1 GB size).
- The ⚠️ same-disk limitation and how to repoint `IW_CORE_BACKUP_DIR` off-host.
- **Globals file is a secret**: the `--globals-only` SQL contains role password
  hashes; the engine writes it `0600` inside a `0700` set directory. Document that
  operators must keep these permissions if copying a set elsewhere, and never paste
  the globals file into logs/issues.
- **Client/server version compatibility**: a restore needs a `pg_restore`/`psql`
  whose major version is ≥ the server that produced the dump; the manifest records
  the source server version — show operators how to read it and pick a matching
  client image.

## Conventions

Match the tone/structure of existing docs. Keep `CLAUDE.md` edits surgical and in
the right sections. Ensure any retained-verbatim incident facts are accurate.

## TDD Requirement

n/a — docs only.

## Pre-flight Quality Gates

`make lint` (catches template/markdown-adjacent issues if any). No code changed.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "backend-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["README.md", "CLAUDE.md", "docs/IW_AI_Core_DB_Setup.md", "docs/IW_AI_Core_DB_Backup_Restore.md"],
  "preflight": {"format": "ok|skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "n/a — docs only",
  "tdd_red_evidence": "n/a — documentation only",
  "blockers": [],
  "notes": "Confirm config var names + CLI commands match the implemented code."
}
```
