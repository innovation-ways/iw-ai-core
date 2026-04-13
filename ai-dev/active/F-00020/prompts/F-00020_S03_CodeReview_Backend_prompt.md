# F-00020_S03_CodeReview_Backend_prompt

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S03
**Reviewing**: S02 Backend implementation
**Agent**: code-reviewer

---

## Input Files

- `ai-dev/active/F-00020/F-00020_Feature_Design.md` — Design document
- `ai-dev/active/F-00020/reports/F-00020_S02_Backend_report.md` — Backend implementation report
- All files modified in S02 (see below)

## Output Files

- `ai-dev/active/F-00020/reports/F-00020_S03_CodeReview_Backend_report.md`

## Context

Review the Backend implementation for F-00020. The scope is narrow: enum additions and
CLI `click.Choice` + map extensions in iw-ai-core.

**Repository**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core`

## Files to Review

- `orch/db/models.py` — `WorkItemType.Research` and `DocType.research` additions
- `orch/cli/utils.py` — `TYPE_TO_PREFIX` and `TYPE_TO_ID_PREFIX` additions
- `orch/cli/id_commands.py` — `click.Choice` extension
- `orch/cli/item_commands.py` — `_ITEM_TYPE_MAP` and `click.Choice` extension
- Migration files from S01:
  - `orch/db/migrations/versions/20260413_add_research_work_item_type.py`
  - `orch/db/migrations/versions/20260413_add_research_doc_type.py`

## Review Checklist

### Correctness

- [ ] `WorkItemType.Research = "Research"` (capital R, matches PostgreSQL enum value)
- [ ] `DocType.research = "research"` (lowercase, matches PostgreSQL enum value)
- [ ] `TYPE_TO_PREFIX["research"] == "R"` (single capital letter, no dash)
- [ ] `TYPE_TO_ID_PREFIX["research"] == "R-"` (capital letter + dash)
- [ ] `_ITEM_TYPE_MAP["research"] == WorkItemType.Research`
- [ ] Both `click.Choice` lists updated consistently
- [ ] `doc_commands.py` uses `[e.value for e in DocType]` dynamically — verify no hardcoded list that was missed

### Consistency

- [ ] New entries follow the same casing and format as existing entries
- [ ] The pattern `feature→F`, `incident→I`, `cr→CR`, `research→R` is consistent
- [ ] ID validation logic (`validate_id_prefix`) correctly handles `R-` prefix for research items

### Migration quality

- [ ] Both migration files follow the project's established pattern (docstring, revision IDs, `IF NOT EXISTS`)
- [ ] Chain is correct: `add_research_work_item_type` → `add_research_doc_type` (head)
- [ ] No existing types or tables were modified

### Regression Risk

- [ ] No changes to existing enum values (no renames, no removals)
- [ ] `click.Choice` additions are append-only (no reordering that could affect existing callers)
- [ ] `_ITEM_TYPE_MAP` additions do not shadow existing keys

### Code Quality

- [ ] All docstrings and module-level comments still accurate after changes
- [ ] No unnecessary imports introduced
- [ ] Type hints remain correct

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Data corruption risk or security issue |
| HIGH | Broken functionality or convention violation |
| MEDIUM (fixable) | Concrete quality issue with specific fix |
| MEDIUM (suggestion) | General improvement without specific fix |
| LOW | Style suggestion |

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Backend",
  "work_item": "F-00020",
  "completion_status": "complete",
  "verdict": "PASS|NEEDS_FIX",
  "findings": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_suggestion": 0,
    "low": 0
  },
  "mandatory_fix_count": 0,
  "finding_details": [],
  "notes": ""
}
```
