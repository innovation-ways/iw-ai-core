# I-00053_S02_CodeReview_prompt

**Work Item**: I-00053 -- Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations
**Step Being Reviewed**: S01
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status I-00053 --json`
- `ai-dev/active/I-00053/I-00053_Issue_Design.md`
- `ai-dev/active/I-00053/reports/I-00053_S01_Backend_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/I-00053/reports/I-00053_S02_CodeReview_report.md`

## Review Checklist

### 1. New parser module (`orch/design_doc_parser.py`)

- [ ] `parse_dependencies()` is a pure function — no I/O, no DB, no global state.
- [ ] Returns `Dependencies(depends_on, blocks)` typed dataclass (frozen).
- [ ] Handles every row of the Boundary Behavior table from the design:
  - "None" / "—" / empty → empty list
  - `F-00069` → `["F-00069"]`
  - `F-00069, I-00042, CR-99025` → all three
  - `F-00069 (provides ...)` → `["F-00069"]` (commentary stripped)
  - `F-00069 - reason` → `["F-00069"]`
  - Section absent → empty
  - Mixed-case heading → recognised
- [ ] Never raises on malformed input.
- [ ] ID regex covers F-/I-/CR- prefixes with 3-5 digit numbers.
- [ ] `strip_excluded_sections()` correctly removes `## Out of Scope` and `## Notes` blocks; leaves other sections intact.
- [ ] Section detection respects code fences (does NOT strip "## Out of Scope" if it appears inside ``` ... ```).
- [ ] Type hints complete; passes mypy.
- [ ] Uses `logging.getLogger(__name__)`, not `print`.

### 2. Register integration (`orch/cli/item_commands.py`)

- [ ] `parse_dependencies(design_doc_content)` called at register time.
- [ ] Self-dependency filtered with WARNING log.
- [ ] `WorkItem.depends_on` and `blocks` populated from parsed lists.
- [ ] `Blocks:` inversion: for each blocked-ID, append current item to that other item's `depends_on` (de-duplicated). Missing blocked item → WARNING log, no exception.
- [ ] No exception path can leave the DB in an inconsistent state (review the transaction boundaries — `session.add` / `session.flush` / `session.commit`).

### 3. Planner refactor (`orch/batch_planner.py`)

- [ ] `extract_affected_files()` calls `strip_excluded_sections()` before applying the regex.
- [ ] Existing test-path exclusion (`_is_test_path()`) preserved.
- [ ] No other behavior changes to `analyze_dependencies()` / `_assign_groups()` / etc.

### 4. Backwards compatibility

- [ ] Existing tests pass without modification (verify by reading S01 report's `tests_passed: true` and `test_summary`).
- [ ] Pre-existing items in the DB (`depends_on=[]`) continue to work — Phase 1 reads them, Phase 3's overlap heuristic is the fallback.

### 5. Out-of-scope items NOT shipped

- [ ] No new `iw deps` CLI command.
- [ ] No new alembic migration.
- [ ] No changes outside `orch/design_doc_parser.py`, `orch/cli/item_commands.py`, `orch/batch_planner.py`.

### 6. Conventions

- Read `CLAUDE.md`, project Python style.
- No new external dependencies.
- Type hints, mypy clean, lint clean.

## Test Verification

Run as part of review:
- `make lint`
- `make typecheck`
- `make test-unit`
- `make test-integration`

If any fail, treat as CRITICAL.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Parser raises on malformed input; register transaction left in inconsistent state; existing tests fail; out-of-scope changes leaked in |
| HIGH | Boundary Behavior row not handled; `Blocks:` inversion missing or wrong; logging incorrect |
| MEDIUM (fixable) | Subtle parser edge case; missing log message; type-hint gaps |
| MEDIUM (suggestion) | Could refactor for clarity; could reuse a helper |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00053",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
