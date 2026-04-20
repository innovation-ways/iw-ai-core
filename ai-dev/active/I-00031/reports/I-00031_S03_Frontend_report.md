# I-00031 S03 Frontend — Step Report

## What Was Done

Fixed the "Recent Activity" links in the project dashboard to route based on `entity_type`:

- `"batch"` events → `/project/{project_id}/batch/{entity_id}`
- `"doc_job"` events → `/project/{project_id}/jobs/doc/{entity_id}`
- `"work_item"` events (and all others) → `/project/{project_id}/item/{entity_id}`

Previously all activity links unconditionally linked to work-item detail pages, causing 404s when batch or doc_job events were clicked.

## Files Changed

- `dashboard/templates/pages/project/dashboard.html` — Updated activity link routing in lines 94–103 to check `entity_type` before rendering the href

## Test Results

- `make lint` (full): 1 pre-existing error in `orch/rag/qa.py` (unrelated to this change)
- `uv run ruff check dashboard/`: all checks passed

## Issues / Observations

1. The pre-existing lint error in `orch/rag/qa.py` was not introduced by this change — it exists in the base branch.
2. `entity_type` is already passed through `ActivityEntry` dataclass from S02 backend work, so no backend changes were needed for this fix.
3. Doc job events use URL `/jobs/doc/{job_id}` — verified against `dashboard/routers/jobs_ui.py:170`.
