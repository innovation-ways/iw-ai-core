# F-00020_S05_CodeReview_Final_prompt

**Work Item**: F-00020 — Add Research Work Item Type to iw-ai-core
**Step**: S05
**Agent**: code-reviewer
**Reviewing**: All implementation steps (S01–S04)

---

## Input Files

- `ai-dev/active/F-00020/F-00020_Feature_Design.md` — Design document
- `ai-dev/active/F-00020/reports/F-00020_S01_Database_report.md`
- `ai-dev/active/F-00020/reports/F-00020_S02_Backend_report.md`
- `ai-dev/active/F-00020/reports/F-00020_S03_CodeReview_Backend_report.md`
- `ai-dev/active/F-00020/reports/F-00020_S04_Tests_report.md`

## Output Files

- `ai-dev/active/F-00020/reports/F-00020_S05_CodeReview_Final_report.md`

## Context

Global review of all changes in F-00020. This is a narrow, additive feature — the risk
profile is low, but completeness and consistency across all four change points must be verified.

**Repository**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core`

## All Files Changed

| File | Agent |
|------|-------|
| `orch/db/migrations/versions/20260413_add_research_work_item_type.py` | S01 Database |
| `orch/db/migrations/versions/20260413_add_research_doc_type.py` | S01 Database |
| `orch/db/models.py` | S02 Backend |
| `orch/cli/utils.py` | S02 Backend |
| `orch/cli/id_commands.py` | S02 Backend |
| `orch/cli/item_commands.py` | S02 Backend |
| `tests/integration/test_cli_core.py` | S04 Tests |

## Global Review Checklist

### 1. Completeness — verify ALL acceptance criteria

- [ ] AC1: `iw next-id --type research` → `R-NNNNN` — test exists and passes
- [ ] AC2: `iw register R-NNNNN "title" --type research` → stored as `WorkItemType.Research` — test exists and passes
- [ ] AC3: `iw doc-update R-NNNNN --doc-type research` → stored as `DocType.research` — test exists and passes
- [ ] AC4: Prefix mismatch (R- ID registered as feature) → rejected — test exists and passes
- [ ] AC5: Concurrency — covered by existing `test_next_id_concurrent_no_duplicates` pattern (confirm it covers research or note as gap)

### 2. Consistency across all layers

- [ ] `WorkItemType.Research = "Research"` (Python) matches `'Research'` (PostgreSQL migration)
- [ ] `DocType.research = "research"` (Python) matches `'research'` (PostgreSQL migration)
- [ ] `TYPE_TO_PREFIX["research"] == "R"` — single char, capital
- [ ] `TYPE_TO_ID_PREFIX["research"] == "R-"` — consistent with `validate_id_prefix` logic
- [ ] `_ITEM_TYPE_MAP["research"] == WorkItemType.Research` — consistent
- [ ] `click.Choice` in `next-id` includes `"research"` ✓
- [ ] `click.Choice` in `register` includes `"research"` ✓
- [ ] `doc_update` uses `[e.value for e in DocType]` dynamically — no hardcoded list missed

### 3. Migration chain

- [ ] `add_doc_types_functional` → `add_research_work_item_type` → `add_research_doc_type` (head)
- [ ] Both migrations use `IF NOT EXISTS` (idempotent)
- [ ] Both downgrades are no-ops with explanatory comment

### 4. Full test suite

Run ALL tests in the iw-ai-core repository:

```bash
cd /home/sergiog/dev/iw-doc-plan/main/iw-ai-core
.venv/bin/pytest tests/ -x --timeout=180 -q
```

- [ ] All existing tests pass (no regressions)
- [ ] All 6 new tests pass
- [ ] `test_next_id_all_types` now includes `"research": "R-"`

### 5. Quality gates

```bash
.venv/bin/python -m ruff check orch/ tests/
.venv/bin/python -m mypy orch/db/models.py orch/cli/utils.py orch/cli/id_commands.py orch/cli/item_commands.py
```

- [ ] Zero ruff errors
- [ ] Zero mypy errors

### 6. Boundary coverage

From the design doc's Boundary Behavior table:

| Boundary | Test Exists |
|----------|-------------|
| First-ever research ID | test_next_id_research_sequential |
| Concurrent allocation | Covered by existing concurrent test (or noted as gap) |
| ID prefix mismatch | test_register_research_prefix_mismatch |
| Unknown type | Covered by click.Choice validation (no DB access) |
| JSON output | test_next_id_research_json_output |

### 7. Invariants

- [ ] Invariant 1: `work_item_type` and `doc_type` enums include new values
- [ ] Invariant 2: `TYPE_TO_PREFIX` and `TYPE_TO_ID_PREFIX` consistent
- [ ] Invariant 3: Concurrency safety inherited from existing `allocate_next_id` implementation
- [ ] Invariant 4: `_ITEM_TYPE_MAP["research"] == WorkItemType.Research`
- [ ] Invariant 5: All existing types unaffected

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
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
