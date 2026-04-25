# F-00062 S09 Frontend Report

## What was done

Extended the existing Worktree Health view (`/worktrees`) to display per-worktree Docker Compose stack status with actionable controls.

### Changes

**1. `dashboard/routers/worktrees.py`**
- Extended `WorktreeRow` dataclass with `container_status`, `db_port`, `app_port`, `classification`, and `batch_item_pk` fields
- Updated `_collect_worktrees()` to:
  - Call `worktree_reaper.scan()` once per render to get all container findings
  - Build a map by `batch_item_pk` for efficient lookups
  - Enrich each row with container status (running/stopped/missing/n/a) using `worktree_compose.is_alive()`
  - Reuse `worktree_reaper.classify()` for classification (active/stale/orphan)
  - Append synthetic rows for orphan containers (found in scan but no matching BatchItem)
- Added new route handlers:
  - `GET /worktrees/{batch_item_id}/logs/stream` — SSE stream of docker logs
  - `POST /worktrees/{batch_item_id}/teardown` — force teardown via `worktree_compose.down()`
  - `POST /worktrees/orphan/{container_id}/teardown` — orphan teardown via docker inspect + down

**2. `dashboard/templates/pages/system/worktrees.html`**
- Updated page description to mention container health
- Added container status guide items (running/stopped/missing/n/a) to help text

**3. `dashboard/templates/fragments/worktree_table.html`**
- Added 5 new column headers: Container, DB :Port, App :Port, Class, Actions
- Added container status badge cell (running=green, stopped=yellow, missing=gray, n/a=blank)
- Added DB port and App port cells
- Added classification badge cell (active=neutral, stale=yellow, orphan=red)
- Added actions cell with: Open dashboard link, Logs button (htmx), Teardown button (htmx POST)
- Added logs panel row (hidden, populated by htmx)
- Added orphan row CSS class highlighting

**4. `dashboard/static/tailwind.src.css`**
- Added `.row-orphan` CSS class for orphan row highlighting

**5. `tests/dashboard/test_worktrees_view.py`** (new file)
- `test_worktrees_table_fragment_has_container_column_headers` — verifies column headers present
- `test_worktrees_table_fragment_has_running_badge` — verifies running badge rendering
- `test_orphan_row_has_orphan_css_class` — verifies orphan rows have CSS class
- `test_teardown_calls_compose_down_with_correct_args` — verifies teardown endpoint behavior
- `test_worktree_row_has_container_fields` — verifies dataclass fields
- `test_worktree_row_defaults` — verifies default values

## Test Results

- `make lint` (ruff + node --check): **PASSED** (only pre-existing errors in unrelated files)
- `make test-unit`: **1527 passed, 27 warnings** — all tests pass
- `tests/dashboard/test_worktrees_view.py`: **6 passed** — new tests pass

## Files Changed

- `dashboard/routers/worktrees.py`
- `dashboard/templates/pages/system/worktrees.html`
- `dashboard/templates/fragments/worktree_table.html`
- `dashboard/static/tailwind.src.css` (extended)
- `tests/dashboard/test_worktrees_view.py` (new)

## Notes

- Performance optimization: `_collect_worktrees` makes only ONE `docker ps` call per page render via `worktree_reaper.scan()`, not N calls for N worktrees
- Orphan container detection: uses `worktree_reaper.scan()` to find containers with `iwcore.role` label that have no matching BatchItem
- The logs streaming endpoint uses asyncio subprocess with 60s timeout cap to avoid runaway connections
- The teardown endpoints emit `DaemonEvent` records for audit trail
- All docker commands are read-only (`docker ps`, `docker inspect`, `docker logs`) except teardown which calls `worktree_compose.down()` (S03 module)
