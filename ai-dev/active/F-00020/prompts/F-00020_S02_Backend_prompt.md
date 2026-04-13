# F-00020_S02_Backend_prompt

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S02
**Agent**: Backend
**Parallel With**: None — sequential after S01

---

## Input Files

- `ai-dev/active/F-00020/F-00020_Feature_Design.md` — Design document
- `ai-dev/active/F-00020/reports/F-00020_S01_Database_report.md` — Migration step report

## Output Files

- `ai-dev/active/F-00020/reports/F-00020_S02_Backend_report.md`

## Context

You are extending the iw-ai-core Python enums and CLI commands to support `research` as
a first-class type. The Alembic migrations created in S01 have added the PostgreSQL enum
values — your job is to update the Python layer to match.

**IMPORTANT — Repository location**: All code changes go in the `iw-ai-core` repository at:
```
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core
```

## Architecture References

Read these files before implementing:

- `orch/db/models.py` — `WorkItemType` (line ~48) and `DocType` (line ~150)
- `orch/cli/utils.py` — `TYPE_TO_PREFIX`, `TYPE_TO_ID_PREFIX`, `validate_id_prefix`
- `orch/cli/id_commands.py` — `next_id` command with `click.Choice`
- `orch/cli/item_commands.py` — `register` command with `_ITEM_TYPE_MAP`
- `orch/cli/doc_commands.py` — `doc_update` command (uses `DocType` via `[e.value for e in DocType]`)

## Previous Steps

- S01 Database: Created two Alembic migrations adding `'Research'` to `work_item_type` and `'research'` to `doc_type` PostgreSQL enums.

## Requirements

### 1. `orch/db/models.py` — Add enum values

Add to `WorkItemType`:
```python
Research = "Research"
```

Add to `DocType`:
```python
research = "research"
```

### 2. `orch/cli/utils.py` — Extend type maps

In `TYPE_TO_PREFIX`:
```python
"research": "R",
```

In `TYPE_TO_ID_PREFIX`:
```python
"research": "R-",
```

### 3. `orch/cli/id_commands.py` — Extend `next-id` click.Choice

Change:
```python
type=click.Choice(["feature", "incident", "cr", "batch"]),
```
To:
```python
type=click.Choice(["feature", "incident", "cr", "batch", "research"]),
```

### 4. `orch/cli/item_commands.py` — Extend `register` command

Add to `_ITEM_TYPE_MAP`:
```python
"research": WorkItemType.Research,
```

Change the `click.Choice` for `--type` in the `register` command from:
```python
type=click.Choice(["feature", "incident", "cr"]),
```
To:
```python
type=click.Choice(["feature", "incident", "cr", "research"]),
```

Also add `"research"` to `TYPE_TO_ID_PREFIX` lookup in `validate_id_prefix` if it isn't already covered by the utils.py change.

### 5. Verify `doc_commands.py` requires no change

The `doc_update` command already uses `[e.value for e in DocType]` dynamically — adding `DocType.research` to the enum in step 1 is sufficient. Confirm this by reading the file.

## Mandatory Patterns

- All changes must be consistent: `TYPE_TO_PREFIX`, `TYPE_TO_ID_PREFIX`, `click.Choice`, `_ITEM_TYPE_MAP` must all agree on `"research"` → `"R"` prefix and `WorkItemType.Research`
- Do not change any existing behavior — only additive changes
- Type hints must remain correct (no `Any` introductions)

## TDD Requirement

Write minimal smoke tests after implementation to verify the CLI is wired correctly:

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/python -c "
from orch.db.models import WorkItemType, DocType
from orch.cli.utils import TYPE_TO_PREFIX, TYPE_TO_ID_PREFIX
assert WorkItemType.Research.value == 'Research'
assert DocType.research.value == 'research'
assert TYPE_TO_PREFIX['research'] == 'R'
assert TYPE_TO_ID_PREFIX['research'] == 'R-'
print('All smoke checks passed')
"
```

## Test Verification

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/unit/ -x --timeout=60 -q 2>/dev/null || echo "No unit tests exist yet"
.venv/bin/python -m ruff check orch/db/models.py orch/cli/utils.py orch/cli/id_commands.py orch/cli/item_commands.py
.venv/bin/python -m mypy orch/db/models.py orch/cli/utils.py orch/cli/id_commands.py orch/cli/item_commands.py
```

## Constraints

- Do NOT modify any migration files (S01's responsibility)
- Do NOT create new files — only modify the 4 listed files
- Do NOT change behavior for existing types (feature, incident, cr, batch)

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/db/models.py",
    "orch/cli/utils.py",
    "orch/cli/id_commands.py",
    "orch/cli/item_commands.py"
  ],
  "tests_passed": true,
  "test_summary": "Smoke checks passed; unit suite: N passed",
  "coverage": "N/A — additive enum/CLI changes",
  "blockers": [],
  "notes": ""
}
```
