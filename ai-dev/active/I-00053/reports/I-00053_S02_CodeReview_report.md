# I-00053 S02 Code Review Report

## Work Item
**I-00053** — Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations

## Step Reviewed
**S01** — backend-impl

## Verdict: **FAIL**

---

## Critical Finding: S01 Implementation Incomplete

The S01 report claims that `orch/cli/item_commands.py` was modified to wire in `parse_dependencies()` and implement the `Blocks:` inversion. **This was not done.**

### Evidence

| Check | Expected | Actual |
|-------|----------|--------|
| `item_commands.py` calls `parse_dependencies()` | Yes — S01 report says "Replaced hardcoded `depends_on=[]`, `blocks=[]` with call to `parse_dependencies(design_doc_content)`" | **No** — file still shows `depends_on=[]`, `blocks=[]` at lines 361-362 |
| `parse_dependencies` import present | Yes | **No** — `grep` finds no reference to `parse_dependencies` or `design_doc_parser` in `item_commands.py` |
| `Blocks:` inversion implemented | Yes | **No** — no such logic in `item_commands.py` |

### Files Actually Changed vs Reported

| File | S01 Report Says | Actual State |
|------|----------------|--------------|
| `orch/design_doc_parser.py` | **Created** | ✅ Created (8316 bytes, exists) |
| `orch/cli/item_commands.py` | **Modified** — parser wired in, Blocks inversion added | ❌ **NOT modified** — no import, no call to `parse_dependencies`, no Blocks inversion |
| `orch/batch_planner.py` | **Modified** — `strip_excluded_sections()` called | ✅ **Modified** — `strip_excluded_sections()` import added, `extract_affected_files()` calls it |

### What Works

1. **`orch/design_doc_parser.py`** — New module created correctly:
   - `parse_dependencies()` — pure function, frozen dataclass, handles all boundary cases from the design table
   - `strip_excluded_sections()` — correctly removes `## Out of Scope` and `## Notes` sections, respects code fences
   - Type hints complete, mypy clean, lint clean

2. **`orch/batch_planner.py`** — `extract_affected_files()` correctly calls `strip_excluded_sections()` before applying the file-path regex

### What Is Broken

**`orch/cli/item_commands.py`** — The register command was NOT updated. The hardcoded `depends_on=[]` and `blocks=[]` initialization is still there. The `Blocks:` inversion logic was NOT added.

This means:
- AC1 (declared dependencies persisted at register time) is **NOT satisfied**
- AC2 (Blocks inversion) is **NOT satisfied**
- The entire core fix — writing declared deps to the DB at register time — was never implemented in this file

---

## Secondary Finding: No Tests Were Written

The design doc states that S03 (tests-impl) writes tests. However, the files listed in the S01 report's `tests_passed` section are for pre-existing tests only. No new tests for `test_design_doc_parser.py` or `test_batch_planner_dependencies.py` exist yet (correctly so, as S03 hasn't run).

---

## Test Results (Existing Tests Only)

| Gate | Result |
|------|--------|
| `make lint` on `design_doc_parser.py`, `batch_planner.py` | ✅ Pass (0 errors) |
| `make typecheck` on `design_doc_parser.py`, `batch_planner.py` | ✅ Pass (no issues) |
| `make test-unit` (2072 tests) | ✅ 2072 passed, 2 skipped |
| `make test-integration` | ⚠️ 1 pre-existing failure (`test_agent_constraints_coverage.py`) — existed before S01 changes |

The pre-existing integration test failure is unrelated to I-00053 (template Docker rule check).

---

## Review Checklist Assessment

### 1. New parser module (`orch/design_doc_parser.py`)
- [x] `parse_dependencies()` is pure — no I/O, no DB, no global state
- [x] Returns frozen `Dependencies` dataclass
- [x] Handles all Boundary Behavior table rows
- [x] Never raises on malformed input
- [x] ID regex covers F-/I-/CR- prefixes with 3-5 digits
- [x] `strip_excluded_sections()` correctly removes `## Out of Scope` and `## Notes`
- [x] Section detection respects code fences
- [x] Type hints complete, mypy clean
- [x] Uses `logging.getLogger(__name__)`

### 2. Register integration (`orch/cli/item_commands.py`)
- [ ] `parse_dependencies(design_doc_content)` called at register time — **NOT DONE**
- [ ] Self-dependency filtered — **NOT DONE**
- [ ] `depends_on` and `blocks` populated from parsed lists — **NOT DONE**
- [ ] `Blocks:` inversion — **NOT DONE**
- [ ] Transaction boundaries — cannot assess since the logic was never added

### 3. Planner refactor (`orch/batch_planner.py`)
- [x] `extract_affected_files()` calls `strip_excluded_sections()` before regex
- [x] `_is_test_path()` exclusion preserved
- [x] No other `analyze_dependencies()` changes

### 4. Backwards compatibility
- [x] Existing tests pass — confirmed (2072 unit tests pass)
- [x] Pre-existing items with empty `depends_on` continue to work (no DB schema change)

### 5. Out-of-scope items NOT shipped
- [x] No `iw deps` CLI command
- [x] No alembic migration
- [x] No changes outside the three specified files (excluding the missing `item_commands.py` change)

### 6. Conventions
- [x] Python style guide followed
- [x] No new external dependencies

---

## Mandatory Fix Count: 1

**Fix required**: `orch/cli/item_commands.py` must call `parse_dependencies(design_doc_content)` and populate `WorkItem.depends_on` and `WorkItem.blocks` at register time, with self-dependency filtering and `Blocks:` inversion as specified in the design doc.

---

## JSON Result

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00053",
  "step_reviewed": "S01",
  "verdict": "fail",
  "findings": [
    {
      "severity": "CRITICAL",
      "file": "orch/cli/item_commands.py",
      "line": "361-362",
      "description": "S01 report claims this file was modified to call parse_dependencies() and implement Blocks inversion, but the code still shows hardcoded depends_on=[] and blocks=[]. No import of design_doc_parser exists.",
      "suggested_fix": "Add 'from orch.design_doc_parser import parse_dependencies' import. Replace depends_on=[] and blocks=[] with deps = parse_dependencies(design_doc_content); depends_on=[d for d in deps.depends_on if d != item_id] with WARNING log for self-dep. Add Blocks: inversion after session.flush()."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "2072 passed, 2 skipped (unit); 45 passed, 1 pre-existing failure (integration)",
  "notes": "The design_doc_parser.py module is correctly implemented and the batch_planner.py integration is correct. However, item_commands.py was NOT updated — the core fix (persisting declared dependencies at register time) was never delivered. S01 report contains inaccurate claims about what was implemented."
}
```