# F-00057 S05 Backend Report

## Step Summary

**Agent**: backend-impl
**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step**: S05 — CLI layer on top of S03's service module

## What Was Done

Built the `iw oss` CLI command group with 7 subcommands (`install`, `scan`, `prepare`, `publish`, `enable`, `disable`, `status`) that wrap the S03 service module (`orch.oss.*`). All commands use Click patterns matching existing CLI commands.

### Files Created

| File | Purpose |
|------|---------|
| `orch/cli/oss_commands.py` | Click group `oss` with 7 subcommands |
| `tests/integration/test_oss_cli.py` | Integration tests for all CLI commands |

### Files Modified

| File | Purpose |
|------|---------|
| `orch/cli/main.py` | Registered `oss` group |
| `orch/oss/config_writer.py` | Fixed bug: `project.name` → `project.display_name` |
| `tests/unit/test_oss_config_writer.py` | Updated MockProject to use `display_name` |

### Bug Fixes Applied

1. **`config_writer.py`**: The `write_project_config` function used `project.name` but `Project` model only has `display_name` and `id`. Fixed both the Jinja2 template render call and `_render_inline_config` to use `project.display_name`.

2. **`MockProject` in tests**: Updated to use `display_name` attribute matching the real `Project` model.

## Test Results

```
tests/integration/test_oss_cli.py  13 passed
tests/unit/test_oss_config_writer.py  5 passed
tests/unit/test_oss_tool_probe.py  4 passed
tests/integration/test_oss_persistence.py  7 passed
tests/integration/test_oss_scanner.py  1 passed
──────────────────────────────────────────────────────
Total: 30 passed, 0 failed
```

### mypy

```
Success: no issues found in orch/cli/oss_commands.py, orch/cli/main.py
```

### ruff

```
All checks passed in orch/cli/oss_commands.py, orch/cli/main.py,
tests/integration/test_oss_cli.py, tests/unit/test_oss_config_writer.py
```

## CLI Commands Implemented

| Command | Description |
|---------|-------------|
| `iw oss install [--dry-run] [--tier2]` | Probe or install Tier-1 tools |
| `iw oss scan --project <id> [--mode scan\|make_oss\|publish] [--json]` | Run OSS compliance scan |
| `iw oss prepare --project <id>` | Alias for scan --mode make_oss |
| `iw oss publish --project <id>` | Alias for scan --mode publish |
| `iw oss enable --project <id> [--force]` | Enable OSS and write config |
| `iw oss disable --project <id>` | Disable OSS for project |
| `iw oss status --project <id> [--json]` | Show latest scan status |

## Verification

- `uv run iw oss --help` lists all 7 subcommands ✓
- `make test-unit` passes ✓
- `make test-integration` passes (OSS tests) ✓
- `make lint` passes (ruff) ✓
- `uv run mypy orch/cli/oss_commands.py orch/cli/main.py` passes ✓
