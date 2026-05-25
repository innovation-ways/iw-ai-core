# I-00108 S03 — Tests Implementation Report

## Step Summary

**Step**: S03 (`tests-impl`)
**Work Item**: I-00108 — `iw doc-update` new-doc without `--tier`/`--editorial-category` crashes with raw TypeError (exit 3) instead of clean usage error (exit 2)
**Status**: ✅ `completion_status: complete`

---

## What Was Done

1. **Removed the `@pytest.mark.xfail(strict=True)` marker** from `test_doc_update_new_doc_without_tier_is_clean_usage_error`. The S01 fix in `orch/cli/doc_commands.py` converts this from `xfailed` → `XPASS(strict)` → now a normal `PASSED`. The test function body and its assertions remain unchanged — they now pin the desired contract directly.

2. **Added `test_doc_update_existing_doc_update_without_tier_succeeds`** — regression guard pinning the "update path stays optional" side of I-00108:
   - Seeds a doc with `--tier`/`--editorial-category`
   - Updates it without those flags — must exit 0
   - Verifies the DB row was updated (title changed, content contains `"v2 body"`)

3. **Added `test_doc_update_new_doc_with_tier_and_category_succeeds`** — regression guard pinning the new-doc happy path:
   - Creates a new doc with all required flags
   - Verifies exit code 0
   - Verifies `doc_id` is the composite PK (`{project_id}:F-00201`), `project_id` field, and that tier/editorial_category are correctly stored in the DB row

---

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/cli/test_doc_update_contract.py` | Removed xfail decorator from `test_doc_update_new_doc_without_tier_is_clean_usage_error`; added `ProjectDoc` and `select` imports; added `test_doc_update_existing_doc_update_without_tier_succeeds`; added `test_doc_update_new_doc_with_tier_and_category_succeeds` |

---

## Test Results

```
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov
```

```
tests/integration/cli/test_doc_update_contract.py::test_doc_update_second_call_on_completed_research        PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_existing_doc_update_without_tier_succeeds PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error     PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_unknown_project_exit_1                       PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_with_tier_and_category_succeeds       PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_non_research_does_not_autocomplete             PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_research_item_autocomplete                PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_content_and_content_file_mutually_exclusive   PASSED

8 passed in 6.89s
```

---

## Preflight Quality Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make format` | ✅ ok | `ruff format --check` — 888 files already formatted |
| `make lint` | ✅ ok | `ruff check` — all checks passed |
| `make test-assertions` | ✅ ok | No new assertion-scanner violations across 569 files |

---

## TDD Evidence

The reproduction test `test_doc_update_new_doc_without_tier_is_clean_usage_error` (formerly a strict xfail from CR-00073) is now a normal `PASSED` — this is the RED→GREEN signal from S01. The two regression tests were written to pin preserved behaviour (no regression to demonstrate); they pass GREEN from the start.

```
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error PASSED
```

**`tdd_red_evidence`**: `n/a — regression-guard tests pin behaviour S01 deliberately preserved (update path stays optional; new-doc happy path still works). The bug-reproducing test is the former-xfail test_doc_update_new_doc_without_tier_is_clean_usage_error which is now GREEN.`

---

## Scope Discipline

- ✅ Only `tests/integration/cli/test_doc_update_contract.py` modified
- ✅ No changes to `orch/cli/doc_commands.py` (S01's job)
- ✅ No changes to any other test file
- ✅ No migrations added (none needed)

---

## Key Technical Notes

- `ProjectDoc.id` is a composite primary key of the form `{project_id}:{doc_id}`. Tests must query by this composite key, not by `doc_id` alone. This was the cause of initial test failures.
- `doc_update` JSON output returns `doc_id` as the composite PK (e.g. `test-proj:F-00201`), not the user-supplied doc identifier. Test assertions use `data["doc_id"] == f"{test_project.id}:F-00201"` to be semantically precise.

---

## Notes

None.