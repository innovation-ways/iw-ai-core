# F-00020_S01_Database_prompt

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S01
**Agent**: Database
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00020/F-00020_Feature_Design.md` — Design document

## Output Files

- `ai-dev/active/F-00020/reports/F-00020_S01_Database_report.md`

## Context

You are creating two Alembic migrations for the **iw-ai-core** repository.

**IMPORTANT — Repository location**: All code changes go in the `iw-ai-core` repository at:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```
Do NOT modify files in the `iw-doc-plan` repository (except to write the report).

## Architecture References

- `orch/db/models.py:48` — `WorkItemType` enum (current values: Feature, Issue, ChangeRequest)
- `orch/db/models.py:150` — `DocType` enum (current values: module, api, architecture, release_notes, error_catalog, webhook_ref, user_guide, product_overview, feature_catalog)
- `orch/db/migrations/versions/d4e5f6a7b8c9_add_cancelled_batch_status.py` — Pattern reference for `ALTER TYPE … ADD VALUE`
- `orch/db/migrations/versions/20260413160000_add_doc_type_product_overview_feature_catalog.py` — Current HEAD migration (revision: `add_doc_types_functional`)
- `alembic.ini` — `script_location = orch/db/migrations`

## Previous Steps

This is the first implementation step.

## Requirements

### 1. Migration: add `Research` to `work_item_type` enum

Create file: `orch/db/migrations/versions/20260413_add_research_work_item_type.py`

```
Revision ID: add_research_work_item_type
Revises: add_doc_types_functional
```

Upgrade: `ALTER TYPE work_item_type ADD VALUE IF NOT EXISTS 'Research'`
Downgrade: no-op with comment explaining why

### 2. Migration: add `research` to `doc_type` enum

Create file: `orch/db/migrations/versions/20260413_add_research_doc_type.py`

```
Revision ID: add_research_doc_type
Revises: add_research_work_item_type
```

Upgrade: `ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'research'`
Downgrade: no-op with comment explaining why

### 3. Migration chain validation

After creating both files, verify the migration chain is correct:
```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/alembic heads
.venv/bin/alembic history --verbose | head -20
```
Confirm `add_research_doc_type` is the new head.

## Mandatory Patterns

Follow the exact pattern from `d4e5f6a7b8c9_add_cancelled_batch_status.py`:

```python
"""Add 'Research' value to work_item_type enum.

Revision ID: add_research_work_item_type
Revises: add_doc_types_functional
Create Date: 2026-04-13 00:00:00.000000

PostgreSQL does not allow removing enum values, so the downgrade is a no-op.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from collections.abc import Sequence
from alembic import op

revision: str = "add_research_work_item_type"
down_revision: str | None = "add_doc_types_functional"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE work_item_type ADD VALUE IF NOT EXISTS 'Research'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    pass
```

## TDD Requirement

Database migrations do not have unit tests — they are validated by:
1. Running `alembic heads` to confirm chain integrity
2. The integration tests in S04 which test the CLI commands that rely on these enum values

## Test Verification

After creating both migration files:

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/alembic heads
```

Expected: single head pointing to `add_research_doc_type`.

## Constraints

- Do NOT run `alembic upgrade head` against the development database
- Do NOT modify `orch/db/models.py` — that is S02's responsibility
- Do NOT create any other files
- Migration file names MUST follow the existing pattern (timestamp prefix + description)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Database",
  "work_item": "F-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/migrations/versions/20260413_add_research_work_item_type.py",
    "orch/db/migrations/versions/20260413_add_research_doc_type.py"
  ],
  "tests_passed": true,
  "test_summary": "N/A — migration chain validated via alembic heads",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
