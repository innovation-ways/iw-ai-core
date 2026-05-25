# I-00108 S04 — Code Review Report

## Step Summary

| Field | Value |
|-------|-------|
| **Step** | S04 (`code-review-impl`) |
| **Work Item** | I-00108 — `iw doc-update` new-doc without `--tier`/`--editorial-category` crashes with raw TypeError (exit 3) instead of clean usage error (exit 2) |
| **Step Reviewed** | S03 (`tests-impl`) |
| **Reviewer** | `code-review-impl` |
| **Verdict** | **pass** |

---

## What Was Reviewed

S03 removed the `@pytest.mark.xfail(strict=True)` marker from `test_doc_update_new_doc_without_tier_is_clean_usage_error` and added two regression tests:

1. `test_doc_update_existing_doc_update_without_tier_succeeds` — pins the "update path stays optional" contract
2. `test_doc_update_new_doc_with_tier_and_category_succeeds` — pins the "new-doc happy path still works" contract

---

## Pre-Flight Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ 888 files already formatted |
| `make test-assertions` | ✅ No new assertion-scanner violations (569 files scanned) |

---

## Checklist Findings

### 1. xfail marker removed ✅

The `@pytest.mark.xfail(strict=True, reason=...)` decorator is **absent** from `test_doc_update_new_doc_without_tier_is_clean_usage_error`. The function body and its assertions are unchanged (`assert result.exit_code == 2`, `assert "tier" in (result.stderr or "").lower()`) — the contract is pinned directly now.

### 2. `test_doc_update_existing_doc_update_without_tier_succeeds` ✅

- Seeds an existing doc via a first `doc-update` call with all required flags; `assert first.exit_code == 0` is the precondition guard.
- Second call **omits** `--tier` and `--editorial-category` — the full regression pin.
- Exit code 0 is asserted (specific value).
- Semantic DB check: `doc.title == "Updated title"`, `"v2 body" in doc.content` — specific values, not shape-only.
- No `WorkItem` seeding — `ProjectDoc` is sufficient for this contract.
- In-process via `CliRunner` + `cli_get_session` — correct pattern.
- **Assertion-scanner check**: `assert "v2 body" in doc.content` — this survives a mutation that changes "v2 body" to "v2 body plus extra". However, it is checking for a specific substring in the content that was passed as `--content "# v2 body"`, so it correctly pins the update content. **MEDIUM_FIXABLE** was considered but rejected: the content string is part of the test's own input, not a generic check, and changing it to `"v2" in doc.content` would be strictly weaker.

### 3. `test_doc_update_new_doc_with_tier_and_category_succeeds` ✅

- Uses doc id `F-00201` — no clash with other tests in the file (`F-00099`, `F-00200`).
- Passes all five required flags (`--doc-type`, `--title`, `--tier`, `--editorial-category`, `--content`) — the happy path is fully exercised.
- Assertions: `data["doc_id"] == f"{test_project.id}:F-00201"` (specific string), `data["project_id"] == test_project.id`, `doc.tier.value == "human_authored"`, `doc.editorial_category.value == "technical"` — all specific values, not shape-only.
- `doc.title == "New module doc"` — specific value.
- In-process via `CliRunner` + `cli_get_session` — correct pattern.

### 4. In-process vs subprocess ✅

Both new tests use Click's `CliRunner` + `cli_get_session` injection — no subprocess invocation. Correct for the testing surface.

### 5. Scope discipline ✅

Only `tests/integration/cli/test_doc_update_contract.py` was modified. No changes to `orch/cli/doc_commands.py`, no changes to other test files, no migrations added.

### 6. Project conventions ✅

- `snake_case` function names.
- Docstrings name the contract being pinned.
- File-local `invoke` helper reused; no duplicate helpers introduced.
- No reordering of existing tests; no renaming; no doc id changes in existing tests.

### 7. TDD RED Evidence ✅

The former-xfail `test_doc_update_new_doc_without_tier_is_clean_usage_error` is now `PASSED` — this is the RED→GREEN signal from S01. The two regression tests pin deliberately preserved behaviour (update path optional, new-doc happy path). `tdd_red_evidence: "n/a — regression-guard tests pin behaviour S01 deliberately preserved"` is acceptable given the design.

---

## Test Results

```
uv run pytest tests/integration/cli/test_doc_update_contract.py -v --no-cov
```

```
tests/integration/cli/test_doc_update_contract.py::test_doc_update_second_call_on_completed_research         PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_existing_doc_update_without_tier_succeeds  PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_without_tier_is_clean_usage_error     PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_unknown_project_exit_1                      PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_doc_with_tier_and_category_succeeds    PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_non_research_does_not_autocomplete          PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_new_research_item_autocomplete               PASSED
tests/integration/cli/test_doc_update_contract.py::test_doc_update_content_and_content_file_mutually_exclusive  PASSED

8 passed in 6.48s
```

---

## Findings

| Severity | Category | File | Line | Description | Suggestion |
|----------|----------|------|------|-------------|------------|
| LOW | testing | `test_doc_update_contract.py` | ~260 | `assert second.exit_code == 0` appears twice in `test_doc_update_existing_doc_update_without_tier_succeeds` — the second occurrence is a no-op (duplicate assertion of already-checked value) | Remove the duplicate `assert second.exit_code == 0, f"stderr: {second.stderr}"` line |
| LOW | testing | `test_doc_update_contract.py` | ~306 | Same duplicate pattern in `test_doc_update_new_doc_with_tier_and_category_succeeds` | Remove the duplicate `assert result.exit_code == 0, f"stderr: {result.stderr}"` line |

**Mandatory fix count: 0** (all findings are LOW)

---

## Notes

S03 is a clean, well-scoped test change. The assertion scanner found no violations. The two regression tests are strong: they pin the optional/required asymmetry on both sides and use specific-value assertions throughout. The duplicate `assert exit_code == 0` lines are cosmetic only and do not affect correctness or signal.