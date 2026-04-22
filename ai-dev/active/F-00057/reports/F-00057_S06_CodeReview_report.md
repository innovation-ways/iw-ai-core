# F-00057 S06 Code Review Report

## Step Summary

**Reviewer**: code-review-impl
**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step Reviewed**: S05 (backend-impl — CLI)
**Step**: S06

---

## What Was Reviewed

The CLI layer implemented in `orch/cli/oss_commands.py` against the design doc (`F-00057_Feature_Design.md`) and existing CLI conventions (`project_commands.py`, `doc_commands.py`).

---

## Checklist Results

### 1. Architecture Compliance ✓

- CLI layer is thin — all subcommands delegate to `orch.oss.*` without embedding business logic.
- DB session acquired via `get_session()` from `ctx.obj["get_session"]`, matching `project_commands.py`.
- Flag naming: `--project` (aliased as `project_id` param), `--json`, `--dry-run`, `--force`, `--tier2` — consistent with existing CLI patterns.
- `oss` group registered in `main.py` via `cli.add_command(oss)` at line 91.

### 2. Exit-code Correctness ✓

| Command | Expected | Code |
|---------|----------|------|
| `iw oss scan` on green/yellow | 0 | ✓ (`sys.exit(0)` at line 209 when `pill_color != "red"`) |
| `iw oss scan` on red | 1 | ✓ (`sys.exit(1)` at line 208) |
| `iw oss scan` on setup error | 2 | ✓ (all error paths exit 2) |
| `iw oss install --dry-run` | 0 always | ✓ (lines 72, 78 — both exit 0) |
| `iw oss install` | propagate | ✓ (`sys.exit(exit_code)` line 103) |
| `iw oss enable/disable/status` on success | 0 | ✓ (enable line 267, disable line 288, status line 399) |
| `iw oss enable/disable/status` on project-not-found | 2 | ✓ (enable line 242, disable line 283, status line 308) |
| `iw oss enable` on non-git-dir | 2 | ✓ (line 249) |

### 3. `--json` Contract ✓

- Shape matches AC1/AC5: `project_id`, `pill_color`, `exit_code`, `head_sha`, `stale`, `counts`, `scan_id`, `completed_at`.
- `stale` computed correctly: `git rev-parse HEAD` called in `project.repo_root`, compared to `oss_scan.head_sha` (line 346–358 in `status` command).
- Missing-data case (no prior scans): returns `pill_color: "gray"` with null companions (lines 317–342) — exits 0.

### 4. Help Discoverability ✓

`uv run iw oss --help` confirmed listing all 7 subcommands:
`disable`, `enable`, `install`, `prepare`, `publish`, `scan`, `status`.

### 5. Error Messages ✓

- Disabled project error (line 133–141): "OSS not enabled for {project_id}; run `iw oss enable --project {project_id}` first" — includes exact command.
- Project-not-found errors include the ID.
- Non-git-dir errors include the path (line 247).

### 6. Testing ✓

- `CliRunner` used (not subprocess) — correct pattern.
- Boundary behavior tests present:
  - `test_oss_scan_refuses_when_disabled` → exit 2 + no DB writes
  - `test_oss_scan_exits_2_when_project_not_found` → exit 2
  - `test_oss_enable_exits_2_on_non_git_repo` → exit 2 + no writes
  - `test_oss_status_json_shape` with no scans → gray pill + exit 0
- `--json` shape asserted in `test_oss_status_json_shape`.

### 7. Convention Checks ✓

- Typing: all Click command signatures annotated.
- `orch.oss` imports at module top (line 19), not inside functions.
- Logging: uses `logger` from `orch.oss` module; no print statements in scanned commands.

---

## Test Verification

| Check | Command | Result |
|-------|---------|--------|
| OSS CLI integration tests | `uv run pytest tests/integration/test_oss_cli.py -v` | **13 passed** |
| ruff on oss files | `uv run ruff check orch/cli/oss_commands.py orch/cli/main.py tests/integration/test_oss_cli.py` | **All checks passed** |
| mypy on oss files | `uv run mypy orch/cli/oss_commands.py orch/cli/main.py --ignore-missing-imports` | **Success: no issues** |
| Help lists 7 subcommands | `uv run iw oss --help` | **7 commands listed** |

---

## Issues Found

### Pre-existing failures (NOT introduced by S05)

The `make test-unit` run fails due to import errors in unrelated test files:
- `tests/unit/test_fix_summary_ingestion.py`: `ImportError: cannot import name '_parse_and_store_fix_summary'`
- `tests/unit/test_item_report_cli.py`: `ImportError: cannot import name 'item_report'`

These are **pre-existing** issues unrelated to F-00057 S05. The `make lint` failure on other files (`test_oss_tool_probe.py`, `test_oss_config_writer.py`, etc.) is also pre-existing — ruff/lint passes cleanly on all S05 files.

---

## Verdict

**pass**

Zero CRITICAL, HIGH, or MEDIUM_FIXABLE findings in the S05 implementation. All checklist items verified. Pre-existing test failures are out of scope for this review.