# F-00074_S01_Database_prompt

**Work Item**: F-00074 — Keep-Alive Scheduler
**Step**: S01
**Agent**: database-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers spun up by pytest fixtures, read-only `docker ps | inspect | logs`,
and invoking `./ai-core.sh` or `make` targets.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orchestration DB
(port 5433). Your job is to WRITE the migration FILE — the daemon will dry-run it
against a testcontainer at merge time and apply it post-merge.

You MAY run `alembic revision -m "..."` (writes a file only),
`alembic history | current | show` (read-only).

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/F-00074/F-00074_Feature_Design.md` — read this first
- `orch/db/models.py` — add the three new models here
- `orch/db/migrations/versions/` — migration chain; current head is `add_diagram_doc_type`
- `docs/IW_AI_Core_Database_Schema.md` — schema conventions

## Output Files

- Modified: `orch/db/models.py` (three new model classes appended)
- New: `orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py`
- `ai-dev/active/F-00074/reports/F-00074_S01_Database_report.md`

## Context

This step creates the three DB models and migration for the Keep-Alive Scheduler feature.
No application logic — that belongs in S02. Focus on schema correctness, type annotations,
and the singleton seeding of the config row in the migration.

## Requirements

### 1. Add three models to `orch/db/models.py`

Append the following at the end of `orch/db/models.py`, after the last existing model.

#### `KeepAliveConfig` (singleton, `id=1` always)

```python
class KeepAliveConfig(Base):
    __tablename__ = "keep_alive_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # always 1
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-4-6")
    window_duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    updated_at: Mapped[datetime] = mapped_column(_TIMESTAMPTZ, server_default=func.now(), onupdate=func.now(), nullable=False)

    slots: Mapped[list["KeepAliveSlot"]] = relationship("KeepAliveSlot", back_populates="config", passive_deletes=True)
```

#### `KeepAliveSlot` (one row per scheduled time)

```python
class KeepAliveSlot(Base):
    __tablename__ = "keep_alive_slots"
    __table_args__ = (UniqueConstraint("time_hhmm", name="uq_keep_alive_slots_time"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    time_hhmm: Mapped[str] = mapped_column(String(5), nullable=False)   # "HH:MM"
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(_TIMESTAMPTZ, server_default=func.now(), nullable=False)

    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("keep_alive_config.id", ondelete="CASCADE"), nullable=False, default=1)
    config: Mapped["KeepAliveConfig"] = relationship("KeepAliveConfig", back_populates="slots")
    runs: Mapped[list["KeepAliveRun"]] = relationship("KeepAliveRun", back_populates="slot", passive_deletes=True)
```

#### `KeepAliveRun` (execution log)

```python
class KeepAliveRun(Base):
    __tablename__ = "keep_alive_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slot_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("keep_alive_slots.id", ondelete="SET NULL"), nullable=True)
    slot_time: Mapped[str] = mapped_column(String(5), nullable=False)   # snapshot of "HH:MM" at fire time
    fired_at: Mapped[datetime] = mapped_column(_TIMESTAMPTZ, server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)     # success|failed|retried_success|retried_failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    slot: Mapped["KeepAliveSlot | None"] = relationship("KeepAliveSlot", back_populates="runs")
```

Use the same import set already present in `orch/db/models.py`: `Integer`, `BigInteger`, `Boolean`, `String`, `Text`, `DateTime`, `ForeignKey`, `UniqueConstraint`, `func`, `relationship`, `Mapped`, `mapped_column`, `_TIMESTAMPTZ`. Do NOT add new imports unless they are genuinely missing.

### 2. Generate and write the migration

```bash
uv run alembic revision -m "f00074_add_keepalive_tables"
```

This creates `orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py`.

Verify `down_revision` points to `add_diagram_doc_type`. If alembic picks a different parent, edit `down_revision` manually.

#### `upgrade()` must:

1. Create `keep_alive_config` table with columns: `id` (integer PK), `model` (varchar 100, not null), `window_duration_hours` (integer, not null), `updated_at` (timestamptz, server_default `now()`).
2. Create `keep_alive_slots` table with columns: `id` (bigint PK autoincrement), `time_hhmm` (varchar 5, not null), `enabled` (boolean, not null, default true), `created_at` (timestamptz, server_default `now()`), `config_id` (integer FK → `keep_alive_config.id` ON DELETE CASCADE, not null).
   - Add unique constraint `uq_keep_alive_slots_time` on `time_hhmm`.
3. Create `keep_alive_runs` table with columns: `id` (bigint PK autoincrement), `slot_id` (bigint FK → `keep_alive_slots.id` ON DELETE SET NULL, nullable), `slot_time` (varchar 5, not null), `fired_at` (timestamptz, server_default `now()`, not null), `status` (varchar 20, not null), `error` (text, nullable).
4. **Seed the singleton config row**:
   ```python
   op.execute("INSERT INTO keep_alive_config (id, model, window_duration_hours) VALUES (1, 'claude-sonnet-4-6', 5) ON CONFLICT (id) DO NOTHING")
   ```

#### `downgrade()` must:

Drop tables in reverse dependency order: `keep_alive_runs`, `keep_alive_slots`, `keep_alive_config`.

### 3. Dry-run verification

```bash
uv run iw migrations dry-run
```

Must succeed. Your migration must appear in "Revisions applied".

## Project Conventions

- Follow PEP 604 type syntax (`X | None`, not `Optional[X]`).
- `from __future__ import annotations` header in the migration file.
- `_TIMESTAMPTZ = DateTime(timezone=True)` — use this alias, do not inline `DateTime(timezone=True)`.
- Match the docstring style of adjacent migrations (one-line summary, numbered delta list, reversibility note).
- Migration filenames use the alembic-generated hash prefix: `<hash>_f00074_add_keepalive_tables.py`.

## TDD Requirement

No application tests in this step. Run the dry-run and lint as proof of correctness.

## Pre-flight Quality Gates

1. `uv run iw migrations dry-run` — must succeed
2. `make lint`
3. `make typecheck`
4. `make test-unit` — no regressions

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "database-impl",
  "work_item": "F-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/db/migrations/versions/<rev>_f00074_add_keepalive_tables.py"
  ],
  "migration_revision": "<rev>",
  "down_revision": "add_diagram_doc_type",
  "dry_run_passed": true,
  "tests_passed": true,
  "test_summary": "dry-run ok; lint ok; X unit passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
