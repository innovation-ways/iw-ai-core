# CR-00017_S07_Backend_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S07
**Agent**: backend-impl

---

## ⛔ Docker is off-limits
## ⛔ You MUST NOT run `alembic upgrade head` against the live DB

You are writing CLIs that OPERATORS will use to apply migrations. You yourself
are an agent in the workflow — you MUST NOT invoke these CLIs with
`--i-am-operator` during development. Test with mocks and testcontainers.

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — Design (AC7)
- S03/S05 reports — `safe_migrate` and `migration_pipeline` modules are available
- `orch/cli/` — existing CLI command groups (click-based, `iw` entry point)
- `orch/cli/__init__.py` — group registration
- `orch/cli/utils.py` — shared CLI helpers (if it exists)
- `orch/CLAUDE.md` — CLI conventions

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S07_Backend_report.md`
- `orch/cli/migrations_commands.py` (new)
- `orch/cli/merge_queue_commands.py` (new)
- `orch/cli/__init__.py` (register both groups)
- `tests/unit/test_migrations_cli.py` (new smoke)
- `tests/unit/test_merge_queue_cli.py` (new smoke)

## Context

Operator-facing CLIs. Wrap the S03 library and S05 pipeline in click commands with strict ack gates.

## Requirements

### 1. `iw migrations` group

```
iw migrations list-pending                       # 0 exit; table or --json
iw migrations dry-run                            # spins testcontainer; exits 0/non-0
iw migrations apply --i-am-operator              # applies to live DB; exits per AC7
```

- `list-pending`: read-only. Reads the script directory + current live-DB revision. No guards (safe). Returns the pending revisions with their descriptions.
- `dry-run`: spins a testcontainer, calls `safe_migrate.dry_run(tempdb_url)`. NO live-DB access. No guards.
- `apply`:
  - Refuses with exit code 3 if `--i-am-operator` is not passed.
  - Refuses with exit code 2 if `IW_CORE_AGENT_CONTEXT=true` in env.
  - Calls `safe_migrate.apply(live_url, batch_id=None)`.
  - Exit 0 on success, 5 on migration failure, 4 on multi-head.

### 2. `iw merge-queue` group

```
iw merge-queue status                            # 0 exit; shows frozen y/n + reason + last migration log
iw merge-queue unfreeze --ack "<reason>"         # clears frozen flag
```

- `status`: read-only; calls `migration_pipeline.is_merge_queue_frozen()` and reads the latest `pending_migration_log` + `daemon_events` entries. Table or `--json`.
- `unfreeze`:
  - Refuses with exit code 3 if `--ack "..."` (with non-empty string) missing.
  - Refuses with exit code 2 if `IW_CORE_AGENT_CONTEXT=true`.
  - Calls `migration_pipeline.set_merge_queue_frozen(active=False, reason=ack_text, acknowledged_by=getpass.getuser())`.
  - Exit 0 on success.

### 3. Canonical exit codes

Per AC7 in the design:

```
0  = success
2  = agent-context guard (AgentContextForbidden)
3  = missing operator flag
4  = multi-head state detected
5  = migration operation failed
1  = unknown / unexpected
```

Enforce these in the CLI: map exceptions from `safe_migrate` to the right code; do NOT let raw tracebacks leak to the user on expected failure modes (agent-context, missing flag, multi-head, failure). Unknown/unexpected exceptions fall through to 1.

### 4. Output formats

Both groups support `--json` for machine-readable output. Default is human-readable tables (use `click.echo` + any existing table helper; don't add a new dependency).

### 5. Register groups

In `orch/cli/__init__.py` (or wherever groups are registered — match convention):

```python
from orch.cli.migrations_commands import migrations_group
from orch.cli.merge_queue_commands import merge_queue_group
cli.add_command(migrations_group, name="migrations")
cli.add_command(merge_queue_group, name="merge-queue")
```

Verify locally: `uv run iw --help` shows `migrations` and `merge-queue` groups. `uv run iw migrations --help` works.

### 6. Unit tests

`tests/unit/test_migrations_cli.py`:

- `test_apply_refuses_without_operator_flag` — click `CliRunner`, invoke `apply` without `--i-am-operator`, assert exit 3.
- `test_apply_refuses_in_agent_context` — monkeypatch env `IW_CORE_AGENT_CONTEXT=true`, invoke `apply --i-am-operator`, assert exit 2.
- `test_list_pending_ok` — mock `safe_migrate.list_pending_revisions`, assert 0 exit + expected output.
- `test_dry_run_failure_exit_code` — mock `dry_run` to return `success=False`, assert exit 5.
- `test_multi_head_exit_code` — mock `safe_migrate.list_pending_revisions` to raise `MultipleHeadsError`, assert exit 4.

`tests/unit/test_merge_queue_cli.py`:

- `test_unfreeze_refuses_without_ack` — assert exit 3.
- `test_unfreeze_refuses_in_agent_context` — assert exit 2.
- `test_status_json_output` — assert parseable JSON on stdout.

Use click's `CliRunner` (`from click.testing import CliRunner`). Don't spin real DBs for these — mock the library calls.

### 7. No session leaks

Any DB access the CLI does (e.g. `status` reading `pending_migration_log`) must close the session in a `finally`.

## Project Conventions

- click 8.x (existing dependency).
- Shared CLI helpers in `orch/cli/utils.py` if present.
- Command-group module naming: `<group>_commands.py`.
- No hardcoded DB URLs; use `orch.config`.

## TDD Requirement

Red → Green → Refactor per step.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make lint` — pass.
3. `uv run iw --help` shows both new groups.
4. Manual test: `uv run iw merge-queue status` — exits 0, reports current (not frozen) state.
5. Manual test: `uv run iw migrations apply` (without flags) — exits 3 with a clear message about the missing flag.

## Subagent Result Contract

Standard JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S07
uv run iw step-done CR-00017 --step S07 --report ai-dev/active/CR-00017/reports/CR-00017_S07_Backend_report.md
```
