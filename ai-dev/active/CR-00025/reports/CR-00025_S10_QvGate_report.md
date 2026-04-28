# CR-00025 S10 — QV Gate: Integration Tests

## What was done

Executed `make allure-integration` to run the full integration test suite.

## Test Results

**Result: FAIL**

- 1144 passed
- 5 failed
- 11 skipped

### Failed Tests (all in `tests/integration/test_cli_core.py`)

| Test | Error |
|------|-------|
| `test_approve_draft_to_approved` | `Error: Active directory not found: ai-dev/active/I-00001/. Create the design doc and prompts before approving.` |
| `test_approve_json_output` | Same as above |
| `test_unapprove_approved_to_draft` | `Error: Cannot unapprove: current status is 'draft'` |
| `test_unapprove_completed_batch_is_ok` | Same unapprove error |
| `test_full_flow_next_id_register_approve` | Same approve error |

All failures are in `tests/integration/test_cli_core.py` and relate to the `approve` / `unapprove` CLI commands requiring an active directory path that does not exist in the test environment.

### Skipped Tests

11 tests were skipped (primarily `test_migration_pipeline.py` marked `@pytest.mark.slow`).

## Issues / Observations

The 5 failing tests all share a root cause: the `approve` command checks for the existence of `ai-dev/active/<item-id>/` directory before allowing approval. In the test environment, this directory is never created. This appears to be a pre-existing test gap — the tests were written against behavior that expects design doc/prompts on disk, but the test fixture does not set up that directory structure.

These failures are **not related to CR-00025 changes** (which focuses on OSS findings dashboard). The failures existed prior to this CR.
