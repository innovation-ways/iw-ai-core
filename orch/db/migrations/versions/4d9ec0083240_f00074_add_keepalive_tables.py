"""f00074_add_keepalive_tables

Revision ID: 4d9ec0083240
Revises: add_diagram_doc_type
Create Date: 2026-04-30 17:59:16.448968

Add three tables for the Keep-Alive Scheduler:
1. keep_alive_config — singleton global settings (id=1)
2. keep_alive_slots — one row per scheduled time slot
3. keep_alive_runs — execution log per firing

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d9ec0083240"
down_revision: str | None = "add_diagram_doc_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. keep_alive_config — singleton (id=1)
    op.execute(
        "CREATE TABLE keep_alive_config ("
        "  id integer PRIMARY KEY,"
        "  model varchar(100) NOT NULL DEFAULT 'claude-sonnet-4-6',"
        "  window_duration_hours integer NOT NULL DEFAULT 5,"
        "  updated_at timestamptz NOT NULL DEFAULT now()"
        ")"
    )

    # 2. keep_alive_slots
    op.execute(
        "CREATE TABLE keep_alive_slots ("
        "  id bigserial PRIMARY KEY,"
        "  time_hhmm varchar(5) NOT NULL,"
        "  enabled boolean NOT NULL DEFAULT true,"
        "  created_at timestamptz NOT NULL DEFAULT now(),"
        "  config_id integer NOT NULL DEFAULT 1"
        ")"
    )
    op.execute(
        "ALTER TABLE keep_alive_slots "
        "ADD CONSTRAINT fk_keep_alive_slots_config "
        "FOREIGN KEY (config_id) REFERENCES keep_alive_config(id) ON DELETE CASCADE"
    )
    op.execute(
        "ALTER TABLE keep_alive_slots ADD CONSTRAINT uq_keep_alive_slots_time UNIQUE (time_hhmm)"
    )

    # 3. keep_alive_runs
    op.execute(
        "CREATE TABLE keep_alive_runs ("
        "  id bigserial PRIMARY KEY,"
        "  slot_id bigint,"
        "  slot_time varchar(5) NOT NULL,"
        "  fired_at timestamptz NOT NULL DEFAULT now(),"
        "  status varchar(20) NOT NULL,"
        "  error text"
        ")"
    )
    op.execute(
        "ALTER TABLE keep_alive_runs "
        "ADD CONSTRAINT fk_keep_alive_runs_slot "
        "FOREIGN KEY (slot_id) REFERENCES keep_alive_slots(id) ON DELETE SET NULL"
    )

    # Seed the singleton config row
    op.execute(
        "INSERT INTO keep_alive_config (id, model, window_duration_hours) "
        "VALUES (1, 'claude-sonnet-4-6', 5) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS keep_alive_runs")
    op.execute("DROP TABLE IF EXISTS keep_alive_slots")
    op.execute("DROP TABLE IF EXISTS keep_alive_config")
