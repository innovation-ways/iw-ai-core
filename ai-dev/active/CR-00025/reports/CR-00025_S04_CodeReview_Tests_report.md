# CR-00025 S04 — Code Review: Tests (S03)

## What Was Done

Reviewed `tests/integration/test_evidences_ingest.py` (10 tests) and `tests/integration/test_evidences_lifecycle.py` (5 tests) against the CR-00025 design doc AC1–AC8, the testcontainer rules in `tests/CLAUDE.md`, and the checklist in the S04 prompt.

## Files Reviewed

| File | Tests | Location |
|------|-------|----------|
| `tests/integration/test_evidences_ingest.py` | 10 (unit-style, helper level) | Integration suite |
| `tests/integration/test_evidences_lifecycle.py` | 5 (CLI end-to-end via CliRunner) | Integration suite |

Note: The S03 report described `tests/unit/test_evidences_ingest.py` but no such file exists. The unit tests for `ingest_phase_from_disk` live in `tests/integration/test_evidences_ingest.py` — this is fine since they use a testcontainer.

## Finding: CRITICAL — `orch/evidences.py` formatting breaks `make quality`

`orch/evidences.py` has a single formatting violation (line 91: single quotes `'rb'` instead of double quotes `"rb"`). This causes `make quality` to fail:

```
uv run ruff format --check .
Would reformat: orch/evidences.py
1 file would be reformatted, 448 files already formatted
make: *** [Makefile:27: format] Error 1
```

**Fix required**: Apply `uv run ruff format orch/evidences.py`.

## AC Coverage Mapping

| AC | Test(s) | Status |
|----|---------|--------|
| AC1: approve ingests pre | `test_approve_ingests_pre_2_files_png_and_yaml` | ✓ Covers 2 files (PNG+yaml), SHA256, content_type, size_bytes |
| AC2: step-done ingests post (browser_verification) | `test_step_done_browser_verification_ingests_post` | ✓ |
| AC2: step-done does NOT ingest for non-browser_verification | `test_step_done_implementation_does_not_ingest` | ✓ |
| AC3: Idempotent upsert | `test_ingest_twice_overwrites_content_and_size_bytes` + `test_upsert_updates_step_id_when_step_id_changes` | ✓ Row count stays 1, new content, step_id updated |
| AC4: Hard-fail on oversize, transaction rollback | `test_oversize_raises_evidence_too_large_error_no_rows_inserted` (helper level) + `test_approve_oversize_keeps_status_draft_no_rows` (CLI level) | ✓ Helper test verifies no rows + rollback. CLI test verifies exit_code != 0 and status remains draft |
| AC5: Post-archive visibility regression guard | `test_evidences_visible_after_archive_cleanup` | ✓ See critical analysis below |
| AC6–AC8 | Backfill — covered by S12 script (not test scope) | N/A |

## AC5 Regression Test — Critical Analysis

The S04 prompt requires verifying the post-archive regression test actually exercises the archiver's cleanup path.

### Does it use `archive_work_item(cleanup=True)` (not `shutil.rmtree`)?

**Yes** — line 465: `archive_work_item(db=db_session, project_id="test-proj", item_id=item_id, archive_dir=archive_dir, cleanup=True)`

### Does it verify `ai-dev/active/<id>/` is gone before asserting `_list_evidences`?

**Yes** — line 474: `assert not pre_dir.exists()`

### Does it assert byte-identical content for every evidence file?

**Yes** — lines 503–505 (pre) and 508–511 (post) compare `ev.content == pre_content_before_archive` using SHA256 on lines 527 and 540.

### Does the docstring mention CR-00020?

**Yes** — lines 388–394 explicitly state "This test would have caught the CR-00020 gap" and "If this test ever fails, the ingestion pipeline has regressed and the bug from CR-00020 has reopened."

**Verdict**: AC5 regression test is correctly implemented.

## Testcontainer Compliance

| Rule | Evidence | Status |
|------|----------|--------|
| No port 5433 connections | grep 5433 — only found in unrelated unit-test guard files | ✓ Pass |
| No `importlib.reload(orch.config)` | Not found in either test file | ✓ Pass |
| `monkeypatch.setenv/delenv` for env vars | Line 345: `monkeypatch.setenv("IW_CORE_EVIDENCE_MAX_BYTES", "100")` | ✓ Pass |
| psycopg2 URL replacement in fixture | `tests/integration/conftest.py:93` handles this | ✓ Pass |
| FTS DDL after `Base.metadata.create_all()` | `tests/integration/conftest.py:111–118` | ✓ Pass |

## No DB Mocking

grep for `Mock(`, `MagicMock`, `patch(`, `mocker.` in both test files returned no matches. The ON CONFLICT upsert runs against a real PostgreSQL testcontainer.

## CLI Tests Use Real `CliRunner`

All 5 integration tests in `test_evidences_lifecycle.py` use `CliRunner.invoke(cli, [...])` against the real CLI command groups — not direct function calls that bypass Click machinery.

## Fixture Isolation

- Each test uses a unique item ID: X-99911 through X-99915 (no cross-contamination)
- `tmp_path` used throughout — no writes to real `ai-dev/` tree
- `shutil.rmtree` cleanup in finally blocks

## Hard-Fail Test (AC4) — Transaction Rollback

The oversize test at `test_evidences_lifecycle.py:325` asserts:
- `exit_code != 0` (line 368)
- `item.status == WorkItemStatus.draft` (line 372) — verifies rollback
- `len(rows) == 0` (line 375) — verifies no partial writes

This is correct. The helper-level test (`test_oversize_raises_evidence_too_large_error_no_rows_inserted`) additionally verifies that after `db_session.rollback()`, zero rows exist.

## Missing Edge Cases

| Edge Case | Test | Status |
|-----------|------|--------|
| Empty dir | `test_empty_dir_returns_0_no_rows` | ✓ |
| Missing dir | `test_missing_dir_returns_0_no_exception` | ✓ |
| Subdir / symlink in phase dir | `test_non_file_entries_ignored` | ✓ (skipped on non-Linux) |
| Unknown extension default MIME | `test_unknown_extension_defaults_to_octet_stream` | ✓ |
| YAML MIME registration | `test_yaml_extension_registered_as_application_yaml` | ✓ |

## Test Results

```
15 passed, 2 warnings (4.22s)

Warnings:
- SAWarning: transaction already deassociated from connection (benign, teardown ordering)
- PytestConfigWarning: Unknown config option: env (pre-existing, not from these tests)
```

## Quality Gate Results

| Gate | Result |
|------|--------|
| `make lint` (ruff) | PASS |
| `make quality` (format-check) | **FAIL** — `orch/evidences.py` needs formatting |
| `make typecheck` (mypy) | PASS |
| `make test-unit` | Not run separately (no unit tests for this module exist) |
| `make test-integration` | PASS (15 tests) |

## Verdict

**FAIL** — mandatory fix required: `orch/evidences.py` must be formatted with `uv run ruff format orch/evidences.py` before the quality gate will pass.

After formatting fix: all other checks pass. The test suite is well-designed, correctly exercises the archiver, and provides proper AC coverage with byte-identity assertions.

## Mandatory Fix Count

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | `orch/evidences.py` fails `make quality` due to single-quote formatting violation on line 91 | `uv run ruff format orch/evidences.py` |

## Notes

- The S03 report mentioned `tests/unit/test_evidences_ingest.py` but the actual file is `tests/integration/test_evidences_ingest.py`. This is not a bug — the tests are appropriately in the integration suite since they exercise the full upsert path against PostgreSQL.
- The `test_approve_oversize_keeps_status_draft_no_rows` note in the S03 report ("status-draft assertion fails because `output_error` calls `sys.exit`") is resolved — the test passes in current run (line 372 assertion holds), likely because `CliRunner.invoke` catches the exit code without propagating the `sys.exit` to the test process.