# F-00057 S03 Backend Report

## Step Summary

**Agent**: backend-impl
**Work Item**: F-00057 — `iw oss` CLI + DB persistence
**Step**: S03 — Backend service module `orch/oss/`

## What Was Done

Implemented the `orch/oss/` service module that wraps the `iw-oss-publish` skill's Python orchestrator and persists results to the DB tables created in S01.

### Files Created

| File | Purpose |
|------|---------|
| `orch/oss/__init__.py` | Public re-exports: `run_scan`, `probe_tier1`, `write_project_config` |
| `orch/oss/scanner.py` | Async subprocess orchestration for running `scripts/scan.py` |
| `orch/oss/persistence.py` | DB writes for `OssFinding` + `OssToolRun` rows, `compute_pill_color`, `compute_summary_counts` |
| `orch/oss/tool_probe.py` | Tier-1 tool availability probe using `importlib.util.spec_from_file_location` for the hyphenated skill |
| `orch/oss/config_writer.py` | Writes `.iw/oss-publish.toml` from the skill's Jinja2 template |

### Tests Created

| Test File | Tests |
|-----------|-------|
| `tests/unit/test_oss_tool_probe.py` | 4 tests for `probe_tier1()`: all tools reported, version detection, ripgrep alias, install_cmd populated |
| `tests/unit/test_oss_config_writer.py` | 5 tests for `write_project_config()`: write absent, idempotent, raise on diff, force overwrite, creates directory |
| `tests/integration/test_oss_persistence.py` | 7 tests: `persist_findings` round-trip + 6 `compute_pill_color` cases |
| `tests/integration/test_oss_scanner.py` | 1 test: `run_scan` against a fixture git repo creates an `OssScan` row |

### Key Implementation Details

- **`scanner.py`**: Uses `asyncio.create_subprocess_exec` (not `subprocess.run`) to avoid blocking the event loop. Captures `head_sha` before subprocess start (invariant #4). Reads `.iw/oss-publish-findings.json` for full structured output.

- **`persistence.py`**: All DB writes go through SQLAlchemy ORM. Single `session.commit()` at end. Maps `pass_status` JSON value to `OssFindingStatus.pass_status` enum.

- **`tool_probe.py`**: Uses `importlib.util.spec_from_file_location` to load the hyphenated skill's `tools.py` without mutating `sys.path`. Falls back to hardcoded TIER1 list if skill not found.

- **`config_writer.py`**: Uses the skill's Jinja2 template if available; falls back to inline rendering. Raises `ConfigFileExistsError` unless `force=True` when file differs (invariant #5).

- **Type checking**: `Callable[[], Session]` and `Project` imported inside `TYPE_CHECKING` block in `scanner.py` to keep runtime imports clean.

## Test Results

```
tests/unit/test_oss_tool_probe.py      4 passed
tests/unit/test_oss_config_writer.py   5 passed
tests/integration/test_oss_persistence  7 passed (6 compute_pill_color + 1 round_trip)
tests/integration/test_oss_scanner      1 passed
──────────────────────────────────────────────────────────────
Total: 17 passed, 0 failed
```

### mypy

```
Success: no issues found in 5 source files
```

### ruff (remaining errors — intentional)

| Error | Reason | Justification |
|-------|--------|---------------|
| S607 `subprocess` with partial path | `git rev-parse` in `_get_git_head` | Intentional: `git` is always on PATH; the check is a false positive |
| S110 `try`-`except`-`pass` | Silent failure in `_get_git_head` | Intentional: missing git should not crash scanning |
| S603 `subprocess` call | `_simple_version` runs tool version commands | Intentional: only runs known tool binaries with hardcoded args |

All three remaining issues are intentional design decisions confirmed by the S02 review contract.

## Issues/Observations

1. **Pre-existing test failures**: `tests/unit/test_fix_summary_ingestion.py` and `tests/unit/test_item_report_cli.py` have import errors unrelated to this step (missing `_parse_and_store_fix_summary` and `item_report`). These existed before S03.
2. **mypy exit code**: Fixed the `StreamReader | None` union issue by adding null check; fixed `OssPillColor` assignment by explicitly constructing the enum value.
3. **Integration tests**: Both `test_oss_persistence.py` and `test_oss_scanner.py` use session-scoped testcontainers with proper teardown to avoid cross-test pollution.
4. **TDD adherence**: Tests were written first (RED), then minimal implementations were added (GREEN), then refinements made (REFACTOR).

## Files Changed Summary

```
NEW: orch/oss/__init__.py
NEW: orch/oss/scanner.py
NEW: orch/oss/persistence.py
NEW: orch/oss/tool_probe.py
NEW: orch/oss/config_writer.py
NEW: tests/unit/test_oss_tool_probe.py
NEW: tests/unit/test_oss_config_writer.py
NEW: tests/integration/test_oss_persistence.py
NEW: tests/integration/test_oss_scanner.py
MODIFIED: tests/integration/test_oss_migration.py (DOWNGRADE_SQL fix for CASCADE)
```