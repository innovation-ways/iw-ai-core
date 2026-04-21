# F-00057_S01_Database_prompt

**Work Item**: F-00057 — `iw oss` CLI + DB persistence for OSS compliance workflow
**Step**: S01
**Agent**: database-impl

---

## Input Files

- `ai-dev/active/F-00057/F-00057_Feature_Design.md` — Design document (read the Database Changes, Invariants, and Boundary Behavior sections first)

## Output Files

- `ai-dev/active/F-00057/reports/F-00057_S01_Database_report.md` — Step report
- `orch/db/migrations/versions/{autogen-hash}_add_oss_tables.py` — Alembic migration (new)
- `orch/db/models.py` — modified (add `Project.oss_enabled` + three new model classes)

## Context

You are implementing the database layer for F-00057. The feature adds an `iw oss` CLI that runs the existing `iw-oss-publish` Skill against registered projects and persists the results so a future dashboard view can query them.

Your deliverables are:
1. A new Alembic migration adding one column and three tables.
2. SQLAlchemy ORM models that match the migration exactly.

Read the design document, then read `orch/db/models.py` and one or two recent migrations in `orch/db/migrations/versions/` to match existing conventions.

## Requirements

### 1. Alembic migration

Use `uv run alembic revision --autogenerate -m "add oss compliance tables"` to generate the skeleton, then hand-edit to ensure:

- **Adds column** `project.oss_enabled BOOLEAN NOT NULL DEFAULT false`.
- **Creates table** `oss_scan` with the columns listed in the design doc's *Database Changes → `oss_scan` columns* section. Notable requirements:
  - `id BIGSERIAL PRIMARY KEY`.
  - `project_id` FK to `project.id` with `ON DELETE CASCADE`.
  - PostgreSQL enum types for `status` (`pending`/`running`/`complete`/`error`), `mode` (`scan`/`make_oss`/`publish`), `pill_color` (`green`/`yellow`/`red`/`gray`). Name the enums `ossscan_status`, `ossscan_mode`, `osspill_color`.
  - `summary_json` and any other `JSONB` columns use `postgresql.JSONB(astext_type=sa.Text())`.
  - Index `ix_oss_scan_project_started` on `(project_id, started_at DESC)`.
- **Creates table** `oss_finding` per design doc. Notable:
  - FK `scan_id` → `oss_scan.id`, `ON DELETE CASCADE`.
  - Enum types `ossfinding_severity` (`MUST`/`SHOULD`/`MAY`/`INFO`) and `ossfinding_status` (`pass`/`fail`/`skip`/`human_required`).
  - Index `ix_oss_finding_scan` on `(scan_id)` and `ix_oss_finding_scan_sev_stat` on `(scan_id, severity, status)`.
- **Creates table** `oss_tool_run` per design doc. Notable:
  - FK `scan_id` → `oss_scan.id`, `ON DELETE CASCADE`.
  - Enum type `osstoolrun_status` (`ok`/`failed`/`missing`/`skipped`).
  - Index `ix_oss_tool_run_scan` on `(scan_id)`.

- **Downgrade** must reverse all of the above: drop tables (in reverse FK order), drop enum types, drop column.

The migration must apply cleanly against a fresh DB created by testcontainer and roll back cleanly.

### 2. ORM models

In `orch/db/models.py`:

- Add `oss_enabled: Mapped[bool]` field on the existing `Project` model with `default=False, server_default="false"`.
- Add three new classes: `OssScan`, `OssFinding`, `OssToolRun` matching the migration. Use the existing model style (SQLAlchemy 2.0 typed syntax as shown by neighboring classes).
- For JSONB columns use `Mapped[dict[str, Any] | None]` + `mapped_column(JSONB, nullable=True)`.
- Enums: use `sa.Enum(..., name="...")` matching the migration enum names exactly.
- Relationships: `Project.oss_scans = relationship("OssScan", back_populates="project", cascade="all, delete-orphan")` and the inverse; similar for `OssScan.findings` and `OssScan.tool_runs`.
- **IMPORTANT**: Per CLAUDE.md, if any field is called `metadata`, rename it to avoid collision with SQLAlchemy's reserved name. None of our fields use this name, but double-check.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Hard rule: `DaemonEvent.metadata` is mapped to `event_metadata` in Python — take the lesson to naming.
- Migration tooling: Alembic with autogenerate; always test migrations apply + downgrade cleanly.
- Test DB: testcontainer Postgres — NOT the live DB on port 5433.
- SQLAlchemy 2.0 typed syntax with `Mapped[...]` and `mapped_column(...)`.

Follow all rules defined there exactly.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Extend or author an integration test that applies the migration against a testcontainer DB and asserts the tables + column exist with the right shape. Drive the migration schema from the test.
2. **GREEN**: Write the minimal migration and ORM code to make the test pass.
3. **REFACTOR**: Clean up.

Test to author: `tests/integration/test_oss_migration.py` (asserts table existence, column constraints, enum values, index presence, downgrade reversibility).

Tests that S07 will add later can assume S01's test is already present.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. Run `make test-unit` — must pass with 0 failures.
2. Run `make test-integration` — must pass with 0 failures (yours and existing).
3. Run `make lint` — must pass.
4. Do NOT report `tests_passed: true` unless ALL unit + integration tests pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/{hash}_add_oss_tables.py",
    "orch/db/models.py",
    "tests/integration/test_oss_migration.py"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Migration applied/downgraded cleanly on testcontainer; ORM models match enum names."
}
```
