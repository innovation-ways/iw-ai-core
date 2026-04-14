# F-00037 S06 QvGate Report

## What was done

Ran `ruff check orch/ tests/` as the S06 lint gate. Found 2 f-string errors in the migration file `orch/db/migrations/versions/20260414_add_doc_type_guides.py` — the `f` prefix was used without any placeholders. Fixed both by removing the extraneous `f` prefix.

## Files changed

- `orch/db/migrations/versions/20260414_add_doc_type_guides.py` — removed `f` prefix from 2 SQL INSERT statements (lines 131, 135)

## Test results

- `ruff check orch/ tests/` → **All checks passed** after fix

## Issues or observations

- The f-string errors were in the `upgrade()` function where raw SQL strings with `%s` placeholders were unnecessarily prefixed with `f`. The fix is purely cosmetic (no functional change).
