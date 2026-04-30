# I-00053 S01 Backend Report

## Work Item
**I-00053** — Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations

## Step
S01 — backend-impl

## What Was Done

### New Module: `orch/design_doc_parser.py`

A new pure-parsing module with two public functions:

- **`parse_dependencies(content: str | None) -> Dependencies`** — parses `**Depends on**:` and `**Blocks**:` lines from a design doc's `## Dependencies` section. Tolerates: missing section, "None", "—", empty, comma-separated IDs, parenthetical commentary, dash-separated reasons. Never raises — logs WARNING for malformed lines.

- **`strip_excluded_sections(content: str | None) -> str`** — removes `## Out of Scope` and `## Notes` sections from doc text before file extraction. Skips code fences (paths inside \`\`\` blocks are preserved).

- ID regex: `r"\b(?:F|I|CR)-\d{3,5}\b"` — covers all valid ID formats.

### Modified: `orch/cli/item_commands.py`

- Added `import logging; logger = logging.getLogger(__name__)` at module level.
- Added `from orch.design_doc_parser import parse_dependencies` import.
- Replaced hardcoded `depends_on=[]`, `blocks=[]` with call to `parse_dependencies(design_doc_content)`.
- Added self-dependency guard — filters out `item_id` from both lists with a WARNING.
- After `session.flush()`, implements **Blocks inversion**: for each `blocked_id` in `filtered_blocks`, if that item exists in the DB, appends current item's ID to the blocked item's `depends_on` (de-duplicated); if not yet registered, logs a WARNING.

### Modified: `orch/batch_planner.py`

- Added `from orch.design_doc_parser import strip_excluded_sections` import.
- Refactored `extract_affected_files()` to call `strip_excluded_sections()` before applying the file-path regex. The existing test-file exclusion stays intact.

## Files Changed

| File | Change |
|------|--------|
| `orch/design_doc_parser.py` | **Created** — new pure-parsing module |
| `orch/cli/item_commands.py` | **Modified** — wire parser into `iw register`, implement Blocks inversion |
| `orch/batch_planner.py` | **Modified** — call `strip_excluded_sections()` in `extract_affected_files()` |

## Quality Gates

| Gate | Result |
|------|--------|
| `make format` | Pre-existing issue in `tests/unit/test_rag_module_gen.py` (unrelated) — not introduced by this change |
| `make typecheck` | Pre-existing errors in `dashboard/routers/code_qa.py` (unrelated) |
| `make lint` on touched files | **Pass** — 0 errors |
| `make test-unit` | 2130 passed, 5 failed (all pre-existing failures: `test_qv_baseline`, `test_i00049_gate_command`, `test_precommit_config`, `test_safe_migrate` × 2) |

## Pre-existing Test Failures (not introduced by this change)

The following tests were already failing before this step's changes:
- `tests/unit/orch/daemon/test_qv_baseline.py::TestGateParsers::test_integration_tests_is_not_in_gate_parsers`
- `tests/unit/test_i00049_gate_command.py::TestGATEPARSERSExcludesIntegrationTests::test_integration_tests_not_in_gate_parsers`
- `tests/unit/test_precommit_config.py::test_pre_commit_hooks_repo_rev_pinned`
- `tests/unit/test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context`
- `tests/unit/test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context`

## Hand-Verification Results

All boundary behavior table rows verified:
- `Depends on: None` → `[]` ✓
- `Depends on: —` → `[]` ✓
- `Depends on:` (empty) → `[]` ✓
- `Depends on: F-00069, I-00042, CR-99025` → `["F-00069", "I-00042", "CR-99025"]` ✓
- `Depends on: F-00069 (provides ...)` → `["F-00069"]` ✓
- `Depends on: F-00069 - reason` → `["F-00069"]` ✓
- Section absent → `[]` ✓
- Mixed case heading → recognized ✓
- `Blocks:` inversion → implemented with WARNING for unregistered targets ✓
- `Out of Scope` paths excluded from `extract_affected_files()` ✓
- `Notes` paths excluded from `extract_affected_files()` ✓
- Code-fence paths preserved inside excluded sections ✓
- `File Manifest` table paths included ✓
- BATCH-00064 scenario (false-positive from `## Out of Scope`) → fixed ✓

## Notes

- Tests are intentionally NOT written in this step — owned by S03.
- Integration tests (`make test-integration`) were not fully run due to timeout constraints in this environment. The subset that ran (`tests/integration/test_models.py`) passed (23 tests, 2 warnings).
- The pre-existing `test_rag_module_gen.py` format issue and the pre-existing typecheck errors are unrelated to this change and should be fixed separately.
