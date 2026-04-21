# F-00057_S07_Tests_prompt

**Work Item**: F-00057
**Step**: S07
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md` — especially *Boundary Behavior* and *Invariants*
- Reports S01, S03, S05 — files under test

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S07_Tests_report.md`
- `tests/integration/test_oss_freshness.py` (new — AC5 freshness scenarios)
- `tests/integration/test_oss_boundary.py` (new — all Boundary Behavior rows)

(Tests in `tests/integration/test_oss_migration.py`, `test_oss_scanner.py`, `test_oss_persistence.py`, `test_oss_cli.py` were authored in S01/S03/S05; this step fills gaps.)

## Context

Add the tests that cover every Boundary Behavior row + every Invariant from the design doc. Tests from prior steps cover the happy paths; your job is the edges.

Read `tests/CLAUDE.md` for mandatory patterns (testcontainer setup, FTS trigger install, no live DB, no `importlib.reload`).

## Requirements

### 1. `tests/integration/test_oss_boundary.py`

One test function per Boundary Behavior row:

- `test_scan_refuses_when_oss_disabled` — project with `oss_enabled=false` → scanner raises (or CLI exits 2); no `oss_scan` row inserted.
- `test_scan_persists_error_on_setup_failure` — force missing gitleaks (monkeypatch PATH) → `oss_scan.status='error'`, `exit_code=2`, error_message set.
- `test_scan_on_unregistered_project` — call with non-existent project_id → error, no writes.
- `test_enable_refuses_non_git_dir` — tmp_path without `.git` → error, flag unchanged.
- `test_rerun_at_same_head_creates_new_row` — scan twice without advancing HEAD → two `oss_scan` rows with same `head_sha`.
- `test_concurrent_scans_create_separate_rows` — run two `run_scan` coroutines concurrently via `asyncio.gather` → two rows, no FK violations.
- `test_missing_tier1_tool_persists_as_missing` — simulate gitleaks absent → `oss_tool_run` with `status='missing'` persisted; scan still completes.
- `test_status_on_no_scans_returns_gray` — project with no `oss_scan` rows → `status --json` returns `pill_color: "gray"`.
- `test_malformed_orchestrator_output` — monkeypatch the findings JSON reader to return garbage → `oss_scan.status='error'`, error_message explains parse failure.
- `test_enable_refuses_to_overwrite_edited_toml` — pre-write a differing `.iw/oss-publish.toml`; `iw oss enable` without `--force` → exit 2, flag unchanged, file unchanged.
- `test_enable_force_overwrites_edited_toml` — same setup + `--force` → file overwritten with rendered default, flag set to true, exit 0.

### 2. `tests/integration/test_oss_freshness.py`

- `test_stale_detection_after_commit` — scan repo at SHA A, commit to advance HEAD to B, call `status --json` → `stale: true`.
- `test_fresh_when_head_matches` — scan at HEAD, call `status --json` immediately → `stale: false`.
- `test_stale_preserves_last_pill_color` — even when stale, the returned `pill_color` is the last scan's value (just flagged as stale).

### 3. Invariant-backed tests

Add tests that directly assert each invariant from the design doc (one per invariant, can live in either new or existing test file as appropriate):

- Inv #1: deleting an `OssScan` cascades to its findings (FK `ON DELETE CASCADE`).
- Inv #2: deleting an `OssScan` cascades to its tool runs.
- Inv #3: `compute_pill_color` truth-table test with all combinations of must/should fail/human.
- Inv #4: `head_sha` is captured before subprocess start (assert timing via mocked subprocess that sleeps then commits — head_sha should be the pre-commit one).
- Inv #5: `write_project_config` output matches defaults exactly (snapshot test).
- Inv #6: deleting a project cascades through to `oss_finding` + `oss_tool_run`.
- Inv #7: `status --json` shape is stable — assert exact key set.

## Project Conventions

Read `tests/CLAUDE.md`:

- NEVER connect to live DB (port 5433). Use testcontainers.
- NEVER `importlib.reload(orch.config)`. Use `monkeypatch.delenv`.
- URL replace in testcontainers: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (copy pattern from existing integration tests).
- Use fixtures from `tests/conftest.py`.

## TDD Requirement

These tests are additive — existing happy-path tests pass; boundary/invariant tests you add must:

1. Fail against the pre-S03/S05 code (prove they're testing the right thing).
2. Pass against the merged S01+S03+S05 code.

For monkey-patching `git rev-parse` output: prefer patching `orch.oss.scanner` helpers; avoid shelling out to real git where possible. Where a real git repo is needed, use tmp_path + `subprocess.run(["git", "init"], cwd=tmp_path)` + seeded commits.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — all tests pass.
2. `make test-unit` — still pass.
3. `make lint` — pass.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "F-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_oss_boundary.py",
    "tests/integration/test_oss_freshness.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
