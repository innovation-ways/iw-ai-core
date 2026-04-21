# F-00057_S06_CodeReview_prompt

**Work Item**: F-00057
**Step Being Reviewed**: S05 (backend-impl — CLI)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md`
- `ai-dev/active/F-00057/reports/F-00057_S05_Backend_report.md`
- Files listed in S05 report (`orch/cli/oss_commands.py`, `orch/cli/main.py`, `tests/integration/test_oss_cli.py`)
- Reference: `orch/cli/project_commands.py` to compare against existing CLI style

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S06_CodeReview_report.md`

## Context

Review the CLI layer. Key checks: does it match existing CLI patterns, are exit codes correct, is `--json` output stable, do subcommands delegate to `orch.oss.*` without embedding business logic?

## Review Checklist

### 1. Architecture Compliance

- CLI layer contains NO business logic; every subcommand is a thin call into `orch.oss.*`.
- DB session acquired the same way as `project_commands.py`.
- Flags match existing CLI naming (`--project` not `--project-id`, matching what's used elsewhere).
- `oss` group is registered in `main.py` without disturbing other groups.

### 2. Exit-code correctness

For each subcommand, verify exit codes match the design doc:

- `iw oss scan`: 0 on green/yellow, 1 on red, 2 on setup error (tool missing, project not found, disabled).
- `iw oss install --dry-run`: 0 always.
- `iw oss install` (without dry-run): propagates installer's exit code.
- `iw oss enable/disable/status`: 0 on success; 2 on project-not-found / non-git-dir.

### 3. `--json` contract

- Shape exactly matches AC1 and AC5.
- Keys stable (no refactor can silently rename them — dashboard consumers will break).
- `stale` computed correctly (compare `oss_scan.head_sha` to live `git rev-parse HEAD`).
- Missing-data case (no prior scans) returns `pill_color: "gray"` with null companions — never throws.

### 4. Help discoverability

- `iw oss --help` lists all 7 subcommands.
- Each subcommand's `--help` documents flags.
- One-line summaries are terse but informative.

### 5. Error messages

- `iw oss scan --project X` with disabled project: message names the exact command to run next (`iw oss enable --project X`).
- Project-not-found errors include the ID.
- Non-git-dir errors include the path.

### 6. Testing

- `CliRunner` used (not subprocess).
- Tests cover the Boundary Behavior rows from the design:
  - scan on disabled project → exit 2 + no DB writes
  - unregistered project → exit 2
  - enable on non-git dir → exit 2 + no writes
  - status with no scans → gray pill + exit 0
- `--json` shape asserted in at least one test per shape-producing command.

### 7. Convention checks

- Typing: all Click command signatures annotated.
- Module imports: `orch.oss` imports are at top of `oss_commands.py`, not inside functions (except where needed to avoid circular imports).
- Logging: match existing CLI logger pattern.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make test-integration` — pass.
3. `make lint` — pass.
4. Manually (in the review's sandbox): `uv run iw oss --help` lists all 7 subcommands.

## Review Result Contract

Standard JSON. `verdict: pass` only if zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
