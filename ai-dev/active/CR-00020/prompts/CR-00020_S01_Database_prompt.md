# CR-00020_S01_Database_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker / docker compose command. Testcontainers spun up by pytest fixtures are the ONLY allowed docker usage. Read-only `docker ps` / `docker inspect` / `docker logs` are fine. `./ai-core.sh` and `make` targets are fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

WRITE the migration file. Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. `alembic revision --autogenerate -m "..."` is allowed (file-only). `alembic history / current / show` are allowed (read-only). The daemon applies migrations post-merge. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design document (read fully, especially "Impact Analysis" and "Acceptance Criteria")
- `orch/db/models.py` — existing ORM models; follow the exact style (SQLAlchemy 2.0 `Mapped[]`, no `from __future__ import annotations`, composite PKs scoped by project_id)
- `orch/db/migrations/versions/9ef17911f546_cr_00019_add_awaiting_review_discarded_.py` — most recent migration for style reference
- `docs/IW_AI_Core_Database_Schema.md` — add the new table there per the design's File Manifest

## Output Files

- `orch/db/models.py` (modified) — add `EvidencePhase` enum + `WorkItemEvidence` model
- `orch/db/migrations/versions/<autogen_hash>_add_work_item_evidences.py` (new) — Alembic migration, up + down
- `docs/IW_AI_Core_Database_Schema.md` (modified) — add a "work_item_evidences" section describing columns, enum, FK, indexes
- `ai-dev/active/CR-00020/reports/CR-00020_S01_Database_report.md` — step report

## Context

Create the schema that will hold evidence screenshots/snapshots as durable BLOBs, ingested at `iw approve` (phase=pre) and `iw step-done` (phase=post on browser_verification steps). Ingestion and dashboard wiring happen in later steps — this step is schema only.

Read the design document first. Then read `CLAUDE.md` (root and `orch/CLAUDE.md`) for ORM conventions and the ENUM gotchas.

## Requirements

### 1. `EvidencePhase` ENUM

Add to `orch/db/models.py` with the other enums near `class StepType`:

```python
class EvidencePhase(enum.Enum):
    pre = "pre"
    post = "post"
```

### 2. `WorkItemEvidence` ORM model

Add the model. Columns (exact types + nullability):

- `id: Mapped[uuid.UUID]` — PRIMARY KEY, `default=uuid.uuid4`, `server_default=func.gen_random_uuid()`, column type `UUID(as_uuid=True)`
- `project_id: Mapped[str]` — `Text`, NOT NULL
- `work_item_id: Mapped[str]` — `Text`, NOT NULL
- `phase: Mapped[EvidencePhase]` — `SAEnum(EvidencePhase, name="evidence_phase")`, NOT NULL
- `filename: Mapped[str]` — `Text`, NOT NULL
- `content_type: Mapped[str]` — `Text`, NOT NULL
- `content: Mapped[bytes]` — `LargeBinary`, NOT NULL
- `size_bytes: Mapped[int]` — `Integer`, NOT NULL
- `captured_at: Mapped[datetime]` — `DateTime(timezone=True)`, NOT NULL, `server_default=func.now()`
- `step_id: Mapped[str | None]` — `Text`, NULLable (NULL for pre, populated for post)

Table arguments:

- `UniqueConstraint("project_id", "work_item_id", "phase", "filename", name="uq_evidence_per_file")`
- `ForeignKeyConstraint(["project_id", "work_item_id"], ["work_items.project_id", "work_items.id"], name="fk_evidence_work_item", ondelete=None)` — **NO `ondelete="CASCADE"`**. Evidences must survive deletion of the parent work_item.
- `Index("ix_evidence_project_item_phase", "project_id", "work_item_id", "phase")` — for the dashboard list query
- `__tablename__ = "work_item_evidences"`

Place the model near other work-item-scoped tables in `orch/db/models.py`.

### 3. Alembic migration

Generate via:

```bash
uv run alembic revision --autogenerate -m "add work_item_evidences"
```

Verify the autogen output contains:
- `CREATE TYPE evidence_phase AS ENUM ('pre', 'post')`
- `CREATE TABLE work_item_evidences (...)` with every column and constraint above
- The unique constraint, FK (no cascade), and index
- A matching `downgrade()` that drops the table, then the enum

If autogen is imperfect (enum ordering, server_default on UUID), edit the migration file to match exactly. Run it against a testcontainer (via `make test-integration` or the `pg_engine` fixture) to confirm `upgrade()` + `downgrade()` round-trip cleanly.

**Do not run `alembic upgrade head` against the live DB on port 5433.**

### 4. Schema documentation

Add a subsection to `docs/IW_AI_Core_Database_Schema.md` describing the new table: columns, enum values, unique constraint, FK-without-cascade rationale (durability past archive), and the dashboard listing index.

## Project Conventions

- Sync SQLAlchemy 2.0, `Mapped[]` declarative style; do not add `from __future__ import annotations` to `orch/db/models.py`.
- Driver is psycopg v3 (`postgresql+psycopg://`). The migration must be psycopg-compatible.
- Enum names use snake_case strings in the DB (`"evidence_phase"`), Python members mirror the values (`pre`, `post`).
- Indexes named `ix_<table>_<cols>`; constraints named `uq_*` / `fk_*` / `ck_*`.
- Test containers must run FTS DDL after `create_all()` — unchanged by this step.

## TDD Requirement

This is a schema step — tests live in S07. For S01 you must:

1. Confirm `alembic upgrade` + `downgrade` round-trip cleanly against a testcontainer (use `make test-integration` or write a quick scratch test that spins up `PostgresContainer` and applies the migration).
2. Confirm `Base.metadata.create_all()` on a fresh DB reflects the new table with all constraints and indexes.

Do NOT write test files in S01 — S07 owns the full test suite. Just verify upgrade/downgrade works before handoff.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-integration` — must pass (the migration round-trip is exercised via the `pg_engine` fixture).
2. Run `make lint`, `make format`, `make typecheck` — must pass against your changes.
3. Report accurately in the JSON contract.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "CR-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<hash>_add_work_item_evidences.py",
    "docs/IW_AI_Core_Database_Schema.md"
  ],
  "tests_passed": true,
  "test_summary": "integration X passed; upgrade/downgrade round-trip verified",
  "blockers": [],
  "notes": "migration revision hash: <hash>"
}
```
