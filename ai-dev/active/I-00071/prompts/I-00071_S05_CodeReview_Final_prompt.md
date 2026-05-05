# I-00071_S05_CodeReview_Final_prompt

**Work Item**: I-00071 -- Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network state-changing commands. Allowed: testcontainers via fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item adds NO migrations. You MUST NOT run alembic upgrade/downgrade/stamp.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00071 --json`
- `ai-dev/active/I-00071/I-00071_Issue_Design.md` -- Design document
- `ai-dev/active/I-00071/I-00071_Functional.md` -- Functional design
- All implementation step reports: `ai-dev/active/I-00071/reports/I-00071_S01_*.md`, `I-00071_S03_*.md`
- All per-agent code review reports: `ai-dev/active/I-00071/reports/I-00071_S02_*.md`, `I-00071_S04_*.md`
- All files listed in S01 + S03 `files_changed`:
  - `orch/design_doc_parser.py`
  - `orch/daemon/scope_overlap.py`
  - `orch/batch_planner.py` (parity update)
  - `tests/unit/test_design_doc_parser.py`
  - `tests/unit/daemon/test_scope_overlap.py`
  - `tests/unit/test_batch_planner_dependencies.py` (parity test)

## Output Files

- `ai-dev/active/I-00071/reports/I-00071_S05_CodeReview_Final_report.md` -- Final review report

## Context

You are performing the **final cross-agent review** of all implementation work for **I-00071**.

This review looks at the complete picture — not individual steps in isolation, but how everything fits together. Per-agent reviews (S02, S04) have already run; your job is to catch cross-cutting issues they could not.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations in any file changed by S01 or S03 → **CRITICAL** finding with `"category": "conventions"`.

## Review Checklist

### 1. Completeness vs Design Document

Map each Acceptance Criterion in `I-00071_Issue_Design.md` to concrete code:

- **AC1: parser strips backticks** — confirm `parse_impacted_paths` produces bare globs for backtick-wrapped bullets AND for backtick-wrapped fenced code lines. Look for the actual stripping in `orch/design_doc_parser.py`.
- **AC2: gate strips relative test paths** — confirm `is_test_path` returns True for `tests/foo.py`, `test/foo.py`, `__tests__/foo.py`. Look for the predicate in `orch/daemon/scope_overlap.py`.
- **AC3: regression tests exist with semantic correctness** — confirm tests assert exact values (`==`, `is True`, `is False`) rather than truthy / shape.

Any AC without corresponding code → **CRITICAL** with `"category": "completeness"`.

### 2. Cross-Module Consistency

- `orch/daemon/scope_overlap.py:is_test_path` and `orch/batch_planner.py:_is_test_path` MUST behave identically (the docstring of the former says "Mirror …"). Verify both either share an implementation or have parallel definitions with the same predicate. Divergence → **HIGH**.
- The `_TEST_PATH_MARKERS` constant should match (or one defers to the other).
- The S03 parity test in `tests/unit/test_batch_planner_dependencies.py` MUST exist and pass — it is the regression guard that catches future divergence between the two helpers. Missing or trivialised → **HIGH** with `"category": "testing"`.

### 3. Integration Points

- The fix in `parse_impacted_paths` flows into `WorkItem.impacted_paths` via `orch/cli/item_commands.py:367-376`. Trace that path mentally: when a user re-registers an item with backtick-wrapped bullets, the bare globs land in the DB. Verify nothing downstream of `parse_impacted_paths` re-introduces backticks.
- The fix in `is_test_path` flows into `find_blocking_items` via `_strip_test_globs`. Trace: a candidate item with relative test paths now has those paths stripped, so the sibling-directory check no longer fires for them.

### 4. Test Coverage (Holistic)

- The two new test files cover both bugs in isolation AND a combined scenario (BATCH-00078 reproduction). Confirm.
- Existing tests in `tests/unit/test_design_doc_parser.py` and `tests/unit/daemon/test_scope_overlap.py` continue to pass — no regression.
- Existing `tests/integration/test_f_00076_gate_performance.py` and `tests/integration/daemon/test_batch_manager_scope_gate.py` continue to pass.

### 5. Architecture Compliance

- Read `orch/CLAUDE.md`. Confirm:
  - `orch/design_doc_parser.py` remains a pure module — no DB, no I/O, no logging beyond stdlib.
  - `orch/daemon/scope_overlap.py` remains pure — no DB, no logging beyond local imports.
- No new dependencies added. No imports moved between layers.

### 6. Security (Cross-Cutting)

- No hardcoded secrets, credentials, API keys.
- The parser still validates globs (`_validate_glob`) — confirm validation runs AFTER backtick stripping, not before (so a backtick-wrapped absolute path like `` `/etc/passwd` `` still raises ValueError after stripping).

## Test Verification (NON-NEGOTIABLE)

Run the **full test suite**:

```bash
make test-unit
make test-integration
```

- Both must report zero failures.
- If integration tests fail, this is a CRITICAL finding.
- Capture the exact pass counts for the result contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing AC, tests fail, broken integration, security vulnerability, lint/format violation |
| **HIGH** | Module divergence, shape-only test assertions, architectural violation |
| **MEDIUM (fixable)** | Missing edge case, naming inconsistency |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00071",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: count of CRITICAL + HIGH + MEDIUM_FIXABLE.
- `missing_requirements`: any AC without corresponding code (each is auto-CRITICAL).
- `cross_cutting`: set to `true` on findings that span multiple agents' work.
