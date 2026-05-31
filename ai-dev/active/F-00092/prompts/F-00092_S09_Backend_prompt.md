# F-00092_S09_Backend_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S09
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

The CLI calls the S03/S05 engine, which may `docker run --rm` for pg client tools.
No persistent container/volume changes. Do not back up/restore the live 5433 DB in
dev.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Scope** (CLI), AC2, AC5.
- `orch/cli/db_commands.py` — existing `db-identity` click group + how groups are
  registered in the CLI (`orch/cli/__init__.py` or the app entry).
- S03/S05 reports — engine `create_backup`, `prune`, `restore` signatures.
- `ai-core.sh` — `cmd_db` dispatch (note: F-00092 depends on **I-00122**, which
  also edits `ai-core.sh`; build on top of its changes).

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S09_Backend_report.md`.

## Context

Expose the backup engine through the `iw` CLI and `./ai-core.sh`. The convention is
hyphenated top-level click groups (e.g. `iw db-identity`), so add an **`iw db-backup`**
group.

## Requirements

### 1. `iw db-backup` click group (`orch/cli/backup_commands.py`)

- `iw db-backup create [--label TEXT]` — runs the engine **synchronously** (records
  a `manual` job when `--label`/explicit, else as invoked). MUST work even when the
  daemon is down (Invariant 5 / AC2).
- `iw db-backup list` — lists recorded backups (type, label, status, timestamp,
  size, path).
- `iw db-backup prune` — runs retention now (manual-exempt).
- `iw db-backup restore --from <set> [--target ...] [--allow-prod]` — calls the S05
  restore helper; default target is the safe non-prod target; refuses prod unless
  `--allow-prod`.
- Register the group with the main CLI (mirror how `db-identity` is registered).
- Match the project's click conventions, output style, and exit codes.

### 2. `./ai-core.sh` wrappers

Add `db backup`, `db backup-list`, `db backup-prune`, `db backup-restore`
subcommands under `cmd_db` that shell out to the corresponding `uv run iw db-backup ...`
commands, and add them to the `db` usage string. Keep shell style consistent;
`bash -n ai-core.sh` must pass.

Do NOT implement docs here (S10).

## Project Conventions

Read `CLAUDE.md`. Match `orch/cli/db_commands.py` patterns and the existing
`ai-core.sh` `cmd_db` structure.

## TDD Requirement (RED first)

Write failing CLI tests first (e.g. `iw db-backup list` output shape, `create`
records a manual row, `restore` refuses prod without `--allow-prod`) using the
project's CLI test approach; capture RED, then implement.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint`.

## Test Verification (NON-NEGOTIABLE)

Targeted only.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "backend-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/cli/backup_commands.py", "orch/cli/__init__.py", "ai-core.sh", "tests/unit/..."],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/unit/.../test_backup_cli.py::test_restore_refuses_prod — AssertionError ... // RED",
  "blockers": [],
  "notes": "Note any I-00122 ai-core.sh merge considerations."
}
```
