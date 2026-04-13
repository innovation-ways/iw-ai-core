# F-00020 S03 CodeReview_Backend Report

## Summary

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S03
**Reviewing**: S02 Backend implementation
**Status**: COMPLETE — with CRITICAL blocker

## Verdict: NEEDS_FIX

The S02 implementation is correct and follows the design precisely. However, **S01 migrations were never created**, which means the PostgreSQL enum types will not have the `'Research'` and `'research'` values. The Python layer changes alone are insufficient.

---

## Findings

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 0 |
| MEDIUM (fixable) | 0 |
| MEDIUM (suggestion) | 0 |
| LOW | 0 |

### CRITICAL: Missing Alembic Migrations (S01 Incomplete)

**Finding**: S01 was supposed to create two Alembic migrations:
- `orch/db/migrations/versions/20260413_add_research_work_item_type.py` (adds `'Research'` to `work_item_type`)
- `orch/db/migrations/versions/20260413_add_research_doc_type.py` (adds `'research'` to `doc_type`)

Neither file exists in `orch/db/migrations/versions/`. Without these migrations, the PostgreSQL enum types remain unchanged, and any attempt to use `WorkItemType.Research` or `DocType.research` in the database will fail.

**Impact**: The Python enum additions are orphaned from the database. The CLI and application code will fail at runtime when trying to insert enum values that don't exist in PostgreSQL.

**Fix required**: S01 must be completed — create the two Alembic migrations and verify the chain with `alembic heads`.

---

## Review Checklist

### Correctness ✅ (except migrations)

| Item | Status | Notes |
|------|--------|-------|
| `WorkItemType.Research = "Research"` | ✅ | Capital R, matches design |
| `DocType.research = "research"` | ✅ | Lowercase, matches design |
| `TYPE_TO_PREFIX["research"] == "R"` | ✅ | Single capital letter, no dash |
| `TYPE_TO_ID_PREFIX["research"] == "R-"` | ✅ | Capital letter + dash |
| `_ITEM_TYPE_MAP["research"] == WorkItemType.Research` | ✅ | Correct mapping |
| Both `click.Choice` lists updated | ✅ | Consistently added `"research"` |
| `doc_commands.py` uses dynamic `[e.value for e in DocType]` | ✅ | No hardcoded list, verified at line 37 |

### Consistency ✅

| Item | Status | Notes |
|------|--------|-------|
| New entries follow existing casing/format | ✅ | Pattern `feature→F`, `incident→I`, `cr→CR`, `research→R` is consistent |
| `validate_id_prefix("R-00001", "research")` | ✅ | Returns `True` |
| `validate_id_prefix("F-00001", "research")` | ✅ | Returns `False` |

### Migration Quality ❌

| Item | Status | Notes |
|------|--------|-------|
| Migration files exist | ❌ | NOT CREATED |
| Chain verified via `alembic heads` | ❌ | Cannot verify |
| `IF NOT EXISTS` used | N/A | Migrations don't exist |
| Downgrade comments present | N/A | Migrations don't exist |

### Regression Risk ✅

| Item | Status | Notes |
|------|--------|-------|
| No changes to existing enum values | ✅ | Additive only |
| `click.Choice` additions are append-only | ✅ | No reordering |
| `_ITEM_TYPE_MAP` additions don't shadow keys | ✅ | `"research"` is new |

### Code Quality ✅

| Item | Status | Notes |
|------|--------|-------|
| Docstrings still accurate | ✅ | No relevant changes |
| No unnecessary imports | ✅ | Clean |
| Type hints correct | ✅ | mypy passes on all 4 files |

---

## Files Reviewed

| File | Uncommitted Change | Review Result |
|------|-------------------|---------------|
| `orch/db/models.py` | +2 lines (enum values) | ✅ Correct |
| `orch/cli/utils.py` | +2 lines (type maps) | ✅ Correct |
| `orch/cli/id_commands.py` | +1 line (click.Choice) | ✅ Correct |
| `orch/cli/item_commands.py` | +2 lines (_ITEM_TYPE_MAP + click.Choice) | ✅ Correct |

## Quality Gates

```
ruff check orch/db/models.py orch/cli/utils.py orch/cli/id_commands.py orch/cli/item_commands.py
```
✅ **PASSED** — no issues

```
mypy orch/db/models.py orch/cli/utils.py orch/cli/id_commands.py orch/cli/item_commands.py
```
✅ **PASSED** — no issues

```
pytest tests/unit/ -x -q
```
✅ **PASSED** — 631 passed, 1 warning (pre-existing TestRunStatus)

```
Smoke checks: WorkItemType.Research, DocType.research, TYPE_TO_PREFIX, TYPE_TO_ID_PREFIX
```
✅ **PASSED** — all values correct

---

## Mandatory Fixes

1. **Create S01 migrations**: Two Alembic migrations adding `'Research'` to `work_item_type` and `'research'` to `doc_type` PostgreSQL enums
2. **Verify migration chain**: Run `alembic heads` to confirm `add_research_doc_type` is the head

---

## Notes

- The alembic directory has a pre-existing issue: `73a7ae48b82b_add_doc_job_agent_columns.py` is missing the `revision` variable declaration, causing `alembic heads` to fail. This is unrelated to F-00020 but should be noted for maintainability.
- All S02 implementation changes are correct, additive, and follow existing patterns exactly.
- The `doc_commands.py` file requires no changes — it dynamically builds the `click.Choice` from `[e.value for e in DocType]`, so adding `DocType.research` was sufficient.

(End of file)
