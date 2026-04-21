# F-00057_S05_Backend_prompt

**Work Item**: F-00057
**Step**: S05
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md`
- `ai-dev/active/F-00057/reports/F-00057_S03_Backend_report.md` (service module)
- `ai-dev/active/F-00057/reports/F-00057_S04_CodeReview_report.md` (review verdict)
- `orch/cli/project_commands.py` and `orch/cli/doc_commands.py` — read to match conventions

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S05_Backend_report.md`
- `orch/cli/oss_commands.py` (new)
- `orch/cli/main.py` (modified — register the `oss` group)

## Context

Build the CLI layer on top of S03's service module. The subcommands call into `orch.oss.*`; no business logic lives in the CLI.

Read at least one existing CLI group (`orch/cli/project_commands.py`) to match Click patterns: how commands are registered, how DB sessions are obtained, how `--json` vs human-readable output is handled, how errors exit with non-zero codes.

## Requirements

### 1. Click command group `iw oss`

Create `orch/cli/oss_commands.py` with a `@click.group(name="oss")` and the following subcommands:

#### `iw oss install [--dry-run] [--tier2]`

- `--dry-run` (default): call `orch.oss.tool_probe.probe_tier1()` and print a table of missing tools + install commands. Exit 0.
- without `--dry-run`: exec `.claude/skills/iw-oss-publish/scripts/install_tools.sh` (+`--tier2` if flag set); stream output; return its exit code.

#### `iw oss scan --project <id> [--mode scan|make_oss|publish] [--json]`

- Resolves `<id>` to a `Project` row; exit 2 if not found.
- Refuses to scan if `project.oss_enabled=false` — exit 2 with "run `iw oss enable` first".
- Calls `asyncio.run(orch.oss.scanner.run_scan(project, mode, ..., skill_scan_path=<resolved>))`. The CLI resolves `skill_scan_path` to iw-ai-core's canonical `.claude/skills/iw-oss-publish/scripts/scan.py` (never the synced-to-project copy) — use `orch.config` / project-root resolution to find it.
- With `--json`: prints compact JSON of the resulting `OssScan` row (see AC1 shape).
- Without `--json`: prints the markdown report path + summary lines.
- Exit code: 0 if pill_color in {green, yellow}; 1 if red; 2 on setup error.

#### `iw oss prepare --project <id>`

- Convenience alias for `iw oss scan --mode make_oss`.

#### `iw oss publish --project <id>`

- Convenience alias for `iw oss scan --mode publish`.

#### `iw oss enable --project <id> [--force]`

- Resolves project. Refuses if `project.repo_path` is not a git repo (exit 2).
- Calls `orch.oss.config_writer.write_project_config(project, force=force)`:
  - If `.iw/oss-publish.toml` is absent or identical to the rendered default → write/no-op, flip flag, exit 0.
  - If the file exists with hand-edited content and `--force` is NOT set → the service raises `ConfigFileExistsError`; CLI prints a message pointing to `--force` and exits 2 without flipping the flag.
  - With `--force` → overwrite, flip flag, exit 0.
- Sets `project.oss_enabled=True` and commits (only on success paths).
- Prints confirmation.

#### `iw oss disable --project <id>`

- Sets `project.oss_enabled=False` and commits. Leaves the `.iw/` directory untouched.

#### `iw oss status --project <id> [--json]`

- Reads the latest `OssScan` row for the project.
- With `--json`: emits the contract shape from AC1 + AC5:
  ```json
  {
    "project_id": "...",
    "pill_color": "green|yellow|red|gray",
    "exit_code": 0,
    "head_sha": "abc123",
    "stale": false,
    "counts": {
      "must_pass": 13, "must_fail": 5, "must_human_required": 0,
      "should_pass": 14, "should_fail": 26, "should_human_required": 2,
      "may_pass": 3, "may_fail": 5, "may_human_required": 0
    },
    "scan_id": 42,
    "completed_at": "2026-04-21T14:32:00Z"
  }
  ```
- `stale` is computed by comparing `oss_scan.head_sha` against `git rev-parse HEAD` in the project dir.
- If no prior scans: returns `pill_color: "gray"`, other fields nullable.
- Without `--json`: human-readable one-liner.
- Exit 0 in all success cases.

### 2. Register the group in `orch/cli/main.py`

Add a single import + `cli.add_command(oss_commands.oss)` line matching how other groups are wired.

### 3. `--help` discoverability

- `iw oss --help` lists all 7 subcommands with one-line summaries.
- Each subcommand's `--help` documents its flags.

## Project Conventions

- Click patterns: use `@click.option("--project", "project_id", required=True)`, no positional args unless already in use elsewhere.
- DB session: obtain via the existing helper (match `project_commands.py`).
- JSON output: use `click.echo(json.dumps(...))` — standard formatter.
- Exit codes: 0 success, 1 compliance failure (scan only), 2 setup/user error.

## TDD Requirement

Tests to add/extend in S07 will cover CLI→service integration. In this step, write at minimum:

- `tests/integration/test_oss_cli.py::test_oss_enable_writes_config_and_flips_flag`
- `tests/integration/test_oss_cli.py::test_oss_scan_refuses_when_disabled`
- `tests/integration/test_oss_cli.py::test_oss_status_json_shape`
- `tests/integration/test_oss_cli.py::test_oss_install_dry_run_lists_missing`

Use Click's `CliRunner` for CLI-level assertions.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make test-integration` — pass.
3. `make lint` — pass.
4. `uv run mypy orch/cli/oss_commands.py orch/cli/main.py` — pass.
5. Manually: `uv run iw oss --help` returns all 7 subcommands.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "backend-impl",
  "work_item": "F-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/cli/oss_commands.py",
    "orch/cli/main.py",
    "tests/integration/test_oss_cli.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
