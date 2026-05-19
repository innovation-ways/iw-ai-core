# I-00095 — S03 API Report

## What was done

- Extended `GET /project/{project_id}/auto-merge/events` route to accept `sort` and `dir` query params.
- Added manual validation for both params using route-level allowlists, returning `HTTP 400` with explicit string messages for invalid values.
- Passed `sort` and `direction` through to `agg.list_recent_events(...)`.
- Added `sort` and `direction` into the fragment template context for downstream UI work.
- Kept route handler thin and did not modify unrelated endpoints.

## Files changed

- `dashboard/routers/auto_merge_ui.py`

## Test and quality results

- `make format` initially failed due formatting drift in `dashboard/routers/auto_merge_ui.py`; file was formatted and rechecked.
- `make typecheck` ✅
- `make lint` ✅
- `uv run pytest tests/dashboard/test_auto_merge_routes.py -v` executed and all targeted tests passed, but command exited non-zero due global coverage gate.
- `uv run pytest tests/dashboard/test_auto_merge_routes.py -v --no-cov` ✅ `51 passed, 0 failed` (targeted verification for this step).

## Issues / observations

- Project-wide coverage threshold is enforced even for single-file targeted runs when coverage is enabled. For this step's targeted verification requirement, `--no-cov` was used after confirming functional pass.
