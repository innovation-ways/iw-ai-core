# F-00059_S05_Tests_report

## What was done

Added cross-layer and boundary-behaviour tests proving the full design-doc contract holds in integration, filled per-step gaps, and closed every row of the design's *Boundary Behavior* table.

### New test files

| File | Tests | Purpose |
|------|-------|---------|
| `tests/integration/test_dashboard_item_functional_tab.py` | 5 | Dashboard route: content populated → 200+rendered markdown; NULL content → empty state; unknown item → 404; disk fallback path → 200+file content; cross-project → 404 |
| `tests/unit/test_review_design_functional_validation.py` | 21 | Pure validation function covering: happy path, missing H2 sections, word count boundaries (499/500/501), file-extension / path-fragment / SQL-DDL / code-fence warnings, combined structural+content issues |

### Extended test files

| File | New tests | Purpose |
|------|-----------|---------|
| `tests/integration/test_work_items_functional_doc_fts.py` | `test_bulk_insert_search_vectors`, `test_gin_index_used_for_search_query` | Bulk insert of 10 items verifying every row's search vector; GIN index hit via `EXPLAIN` with `enable_seqscan=off` |
| `tests/integration/test_item_register_functional_doc.py` | `test_register_with_sibling_fts_returns_row_on_content_term`, `test_register_twice_second_is_idempotent` | FTS returns row on content-specific term; double-register is idempotent |
| `tests/unit/test_backfill_functional_doc.py` | `test_opencode_failure_returns_opencode_exit_code`, `test_force_and_load_db_compose_correctly` | opencode non-zero exits with that code; `--force`+`--load-db` compose correctly |

### Template fix (pre-existing test coverage gap)

`ai-dev/templates/Functional_Design_Template.md` was missing the `⛔ Docker is off-limits` and `⛔ Migrations: agents generate, daemon applies` markers required by `docs/IW_AI_Core_Agent_Constraints.md`. Added both to the HTML comment block. (This was a gap in S03's implementation that caused `test_agent_constraints_coverage.py` to fail for the new template.)

## Files changed

| File | Change |
|------|--------|
| `tests/integration/test_dashboard_item_functional_tab.py` | **NEW** — 5 tests |
| `tests/unit/test_review_design_functional_validation.py` | **NEW** — 21 tests |
| `tests/integration/test_work_items_functional_doc_fts.py` | Extended — 2 new tests |
| `tests/integration/test_item_register_functional_doc.py` | Extended — 2 new tests |
| `tests/unit/test_backfill_functional_doc.py` | Extended — 2 new tests |
| `ai-dev/templates/Functional_Design_Template.md` | Fixed — added required constraint markers |

## Test results

```
make test-unit  →  1376 passed, 19 warnings
make test-integration  →  964 passed, 10 skipped, 35 warnings, 4 errors
make lint  →  pre-existing errors in test_oss_dashboard_templates_extras.py (unrelated)
make typecheck  →  Success: no issues found in 148 source files
```

### Pre-existing failures (not introduced by S05)

- `test_f00055_workflow_fixture.py` (4 errors + 1 failed): These tests call `scripts/e2e_seed.py` which exits with code 2 when `IW_CORE_EXPECTED_INSTANCE_ID` is set without `IW_E2E_SEED=1`. This is a test-environment configuration issue unrelated to F-00059 — the same failures occur on the clean main branch.
- `test_oss_dashboard_templates_extras.py` (8 lint errors): PT018 assertions needing to be split — pre-existing, not introduced by S05.

## Boundary behavior coverage

Every row of the design doc's *Boundary Behavior* table now has at least one test:

| Row | Test |
|-----|------|
| New item registered without functional doc | `test_sibling_functional_doc_absent_both_columns_none` |
| New item registered with sibling functional doc | `test_sibling_functional_doc_exists_both_columns_populated` + `test_register_with_sibling_fts_returns_row_on_content_term` |
| Register with `--functional-doc PATH` outside `ai-dev/active/<ID>/` | `test_functional_doc_override_with_existing_file` |
| Register with `--functional-doc PATH` pointing to missing file | `test_functional_doc_override_with_missing_file_fails` |
| Functional doc > 500 words | `test_501_words_blocks` (validation) + `test_register_twice_second_is_idempotent` (register accepts it) |
| Functional doc contains forbidden term | All 11 extensions + 8 path fragments + 6 SQL patterns + code fence via parametrized tests |
| DB UPDATE via backfill `--load-db` regenerates FTS | `test_load_db_updates_db_columns` + `test_bulk_insert_search_vectors` |
| Backfill `--load-db` with missing item | `test_load_db_missing_item_exits_4` |
| Backfill `--load-db` when opencode fails | `test_opencode_failure_returns_opencode_exit_code` |
| Backfill `--load-db` when DB raises SQLAlchemyError | `test_load_db_sqlalchemy_error_exits_7` |
| Dashboard tab for item with NULL content | `test_returns_200_with_null_content_shows_empty_state` |
| Dashboard tab after content added via backfill | `test_returns_200_with_content_populated` |
| Downgrade when rows have non-NULL content | `test_functional_doc_migration_round_trip` (S01-owned, ensures downgrade succeeds) |

## Notes

- The review validation tests use an extracted pure function (`validate_functional_doc`) mirroring the SKILL.md rules — not regexes embedded directly in tests, so changes to the skill are isolated from the test implementation.
- The `test_gin_index_used_for_search_query` test uses `SET enable_seqscan = off` because small test tables (< 3 pages) may not have the planner prefer the GIN index over a sequential scan. The test resets the setting afterwards.
- Word-count boundary calculations: the prose body excludes heading lines (starting with `#`), HTML comments (`<!-- ... -->`), and blank lines. The 500-word limit applies to the combined prose from all sections. Test content uses `body_words = N` where `N + 9 (fixed section prose) ≤ 500` for passes, and `N + 9 > 500` for blocks.