# F-00085 — S01 Database Report

## What was done

- Added two new ORM models in `orch/db/models.py`:
  - `MergeAutoVerdict` → table `merge_auto_verdicts`
  - `AutoMergeProjectConfig` → table `auto_merge_project_config`
- Implemented required constraints and FK behavior:
  - `merge_auto_verdicts` composite PK: `(project_id, daemon_event_id)`
  - `merge_auto_verdicts.verdict` check: `IN ('pending','correct','wrong','partial')`
  - `auto_merge_project_config.phase` check: `phase IS NULL OR phase IN (0, 1)`
  - Cascading FKs to `projects(id)` on both tables where required
  - `runtime_option_id` FK to `agent_runtime_options(id)` with `ON DELETE SET NULL`
  - Timestamp defaults via `server_default=func.now()` and `_TIMESTAMPTZ`
- Generated and finalized Alembic migration:
  - `orch/db/migrations/versions/678ac4dd44b7_f00085_observability_and_control.py`
  - `down_revision = "d1e2f3gpt53c"` (current head)
  - `upgrade()` creates both tables
  - `downgrade()` drops both tables

## Files changed

- `orch/db/models.py`
- `orch/db/migrations/versions/678ac4dd44b7_f00085_observability_and_control.py`

## Test and verification results

- `make format`: PASS (after one auto-format pass with `uv run ruff format .`)
- `make typecheck`: PASS
- `make lint`: PASS
- `make migration-check`: PASS
  - Includes migration round-trip validation tests in this project
- Targeted run:
  - `uv run pytest tests/integration/test_migrations_round_trip.py -v --no-cov`: **3 passed**

## TDD note

- `tdd_red_evidence`: **n/a — schema-only step; behavioural tests live in S13**

## Issues / observations

- Running the targeted pytest command *without* `--no-cov` fails due to global coverage gate (`fail-under=50`) even when migration tests pass; rerun with `--no-cov` succeeded as expected for targeted verification.
- Per step instruction, S01 intentionally did **not** add new daemon event-type string constants. These should be added in S04/S06:
  - `auto_merge_health_probe`
  - `auto_merge_config_updated`
