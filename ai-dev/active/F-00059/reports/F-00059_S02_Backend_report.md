# F-00059 S02 Backend Report

## What was done

Added the `--functional-doc` Click option to `iw register` (auto-detection + explicit override), and the `--load-db` flag to `scripts/backfill_functional_doc.py` (DB UPDATE after file creation).

### `iw register` changes (`orch/cli/item_commands.py`)

- Added `--functional-doc PATH` option on the `register` command.
- **Auto-detect**: when `design_doc` is provided, the loader computes `sibling_dir / "{item_id}_Functional.md"` and loads it if present.
- **Empty-file guard**: if the auto-detected file exists but reads as empty (`""`), both `functional_doc_path` and `functional_doc_content` are set to `None` — treating empty as absent for consistency.
- **Explicit override**: `--functional-doc PATH` resolves the path relative to `cwd`; if the file does not exist the command exits 2 with a clear error (no partial INSERT).
- All three new `WorkItem` fields (`functional_doc_path`, `functional_doc_content`, `functional_doc_search`) are populated in the INSERT.

### `scripts/backfill_functional_doc.py` changes

- Added `--load-db` flag.
- After opencode writes the file, if `--load-db` is set the script re-fetches the `WorkItem` row and `session.commit()`s the two new columns.
- Exit code 4 if the item is not found in the DB (filesystem untouched).
- Exit code 7 on `SQLAlchemyError` during the DB commit.
- Module docstring updated with the new exit code table.

## Files changed

| File | Change |
|------|--------|
| `orch/cli/item_commands.py` | Added `--functional-doc` option + auto-detect + empty-file guard |
| `scripts/backfill_functional_doc.py` | Added `--load-db` flag + DB UPDATE block |
| `tests/integration/test_item_register_functional_doc.py` | New — 5 integration cases |
| `tests/unit/test_backfill_functional_doc.py` | New — 4 unit cases |

## Test results

```
tests/unit/test_backfill_functional_doc.py          4 passed
tests/integration/test_item_register_functional_doc.py  5 passed
make lint      — specific files clean (8 pre-existing errors unrelated to this step)
make typecheck — 148 sources, no issues
make test-unit — 1337 passed
```

## Key decisions

- **Empty file → `None`**: an empty `functional_doc_content` is treated as absent (both columns `None`). This matches the design doc's intent (absent/missing → `NULL`) and is documented in the test.
- **Double `session.get()`**: the backfill script reads the item twice — once for prompt building (existing behaviour), once in `--load-db` for the UPDATE. This is intentional; the prompt requires the item before opencode runs.
- **No regression**: without `--functional-doc` and without a sibling file, register behaves identically to before.
