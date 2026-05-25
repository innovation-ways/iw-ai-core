# I-00108 S01 — Backend Implementation Report

## Step Summary

**Step**: S01 (`backend-impl`)
**Work Item**: I-00108 — `iw doc-update` new-doc without `--tier`/`--editorial-category` crashes with raw TypeError (exit 3) instead of clean usage error (exit 2)
**Status**: ✅ `completion_status: complete`

---

## What Was Done

Added a single pre-check branch in `orch/cli/doc_commands.py::doc_update` that intercepts the new-doc-with-missing-required-args failure before it can reach `DocService.create_doc()` and be swallowed as an exit-3 "Database error".

The new branch fires only when `svc.get_doc(project_id, doc_id)` returns `None` (new-doc path) **and** (`tier is None` OR `editorial_category is None`). It calls `output_error(ctx, "...", 2)` with a message that names both missing flags. The update path (existing doc) is completely unaffected.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/cli/doc_commands.py` | Added 7-line pre-check: `if existing is None and (tier is None or editorial_category is None): output_error(ctx, "...", 2)` — inserted between `existing = svc.get_doc(...)` and `old_content_hash` computation |

No other files touched. No changes to `orch/doc_service.py`, no Click option changes, no test file changes.

---

## Test Results

```
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov
```

```
test_doc_update_content_and_content_file_mutually_exclusive_exit_2 PASSED
test_doc_update_unknown_project_exit_1                         PASSED
test_doc_update_second_call_on_completed_research             PASSED
test_doc_update_non_research_does_not_autocomplete            PASSED
test_doc_update_new_doc_without_tier_is_clean_usage_error     FAILED [XPASS(strict)]
test_doc_update_new_research_item_autocomplete                PASSED

5 passed, 1 FAILED (XPASS(strict)) in 6.97s
```

**XPASS(strict) is the expected GREEN signal.** The strict xfail test `test_doc_update_new_doc_without_tier_is_clean_usage_error` asserts `exit_code == 2` and `"tier" in stderr` — both now pass because:
- The exit code is 2 (not 3)
- stderr reads: `Error: Creating a new doc requires --tier and --editorial-category (no existing doc 'F-00099' to update)`

S03 (`tests-impl`) will remove the `@pytest.mark.xfail(strict=True)` marker, after which the test will report as a normal `PASSED` instead of `XPASS(strict)`.

---

## Preflight Quality Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ✅ ok | `ruff format --check` — nothing to fix |
| `make type-check` | ✅ ok | `uv run mypy orch/cli/doc_commands.py` — zero issues |
| `make lint` | ✅ ok | `ruff check orch/cli/doc_commands.py` — all checks passed |

---

## TDD Evidence

The reproduction test (`test_doc_update_new_doc_without_tier_is_clean_usage_error`) was authored by CR-00073 as a `@pytest.mark.xfail(strict=True)` pinning the desired post-fix contract *before* the fix existed. The fix turns it from `xfailed` to `XPASS(strict)` — that unexpected-pass **is** the RED→GREEN demonstration:

```
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error FAILED [XPASS(strict)]
TODO(file-incident): doc-update accepts a new-doc upsert that omits --tier/--editorial-category,
then crashes with a raw TypeError from DocService.create_doc() surfaced as exit 3 'Database error'.
The contract should be a clean exit 2 usage error naming the missing options.
Operator follow-up: file an Incident; the orch/cli fix is out of scope for this test-only CR.
```

The strict xfail test passed the assertions (`exit_code == 2`, `"tier" in stderr`) — the fix delivered exactly what the contract pinned.

---

## Scope Discipline

- ✅ Only `orch/cli/doc_commands.py` modified
- ✅ No Click `required=True` added (would break update path)
- ✅ No changes to `orch/doc_service.py` (its `create_doc` signature is intentional)
- ✅ No test file touched (S03 owns the xfail marker removal)
- ✅ No migrations added (none needed)

---

## Notes for S03

S03 (`tests-impl`) must:
1. Remove `@pytest.mark.xfail(strict=True)` from `test_doc_update_new_doc_without_tier_is_clean_usage_error` so the pass is recorded as normal GREEN.
2. Add `test_doc_update_existing_doc_update_without_tier_succeeds` regression test pinning the update-path-optional behaviour.
3. Optionally add `test_doc_update_new_doc_with_tier_and_category_succeeds` for the happy-path create case.

The fix is already committed (`de63a620`).