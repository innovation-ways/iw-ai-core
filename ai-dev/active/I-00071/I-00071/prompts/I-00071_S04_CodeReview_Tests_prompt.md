# I-00071_S04_CodeReview_prompt

**Work Item**: I-00071 -- Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker
**Step Being Reviewed**: S03 (tests-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network state-changing commands. Allowed: testcontainers via fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This item adds NO migrations. You MUST NOT run alembic upgrade/downgrade/stamp.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00071 --json`
- `ai-dev/active/I-00071/I-00071_Issue_Design.md` -- Design document
- `ai-dev/active/I-00071/reports/I-00071_S03_Tests_report.md` -- S03 report
- All files listed in S03's `files_changed`:
  - `tests/unit/test_design_doc_parser.py`
  - `tests/unit/daemon/test_scope_overlap.py`
  - `tests/unit/test_batch_planner_dependencies.py`

## Output Files

- `ai-dev/active/I-00071/reports/I-00071_S04_CodeReview_report.md` -- Review report

## Context

You are reviewing the tests written by `tests-impl` in S03. Verify that the tests:

1. Actually reproduce the two bugs (would FAIL on pre-fix code).
2. Verify SEMANTIC correctness (specific values), not just shape.
3. Cover the BATCH-00078 regression scenario.
4. Don't accidentally edit production code.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Classify any NEW violations in S03's changed files as **CRITICAL** with `"category": "conventions"`.

## Review Checklist

### 1. Reproduction Test Validity

For each new I-00071 test:

- **Does it actually fail without the fix?** Read the test body and trace it against the pre-S01 source. If a test would pass even without S01's changes, it does NOT reproduce the bug — flag as **HIGH** finding.
- **Does it use exact equality (`==`) for paths and `is True`/`is False` for booleans?** Substring or truthy assertions are SHAPE checks — flag as **HIGH** with `"category": "testing"` and reference the I003 lesson.

Concretely:
- `test_strips_surrounding_code_span_backticks_in_bullet_lines`: must assert `result.paths == ["dashboard/CLAUDE.md", ...]` — exact list. If it asserts e.g. `assert "dashboard/CLAUDE.md" in result.paths`, that's a shape check (a backtick-wrapped string contains the substring too).
- `test_two_test_files_under_same_dir_do_not_block_each_other`: must assert `result == []` (exact). `assert not result` is acceptable but weaker.

### 2. Coverage Completeness

Cross-reference the design doc's TDD Approach section. Check each bullet was covered:

- Bullet-list backtick stripping: ✓
- Fenced-code-block backtick stripping: ✓
- Bare paths (regression — no corruption): ✓
- Mixed wrapped/bare paths: ✓
- Relative `tests/`, `test/`, `__tests__/` recognition: ✓
- Existing `is_test_path` cases still pass: ✓ (covered by existing parametrize)
- BATCH-00078 scenario reproduction: ✓
- Non-test sibling overlap still fires: ✓ (sanity counter-test)
- `batch_planner._is_test_path` parity test in `tests/unit/test_batch_planner_dependencies.py`: ✓ (asserts both helpers agree on every fixture — divergence guard)

If any bullet is missing, flag as **MEDIUM (fixable)** with `"category": "testing"`.

### 3. Test Isolation & Determinism

- No DB calls, no I/O, no monkeypatching of stdlib — these are pure-helper tests.
- No reliance on filesystem state.
- Tests should run in any order.

### 4. Naming & Style

- Test names start with `test_`.
- Test names describe behaviour, not implementation (e.g. `test_strips_surrounding_code_span_backticks_in_bullet_lines` ✓; `test_parser_works` ✗).
- Class names use CapWords (`TestImpactedPathsBacktickStripping` ✓).
- I-00071 tag in docstrings or test names so future readers can grep for the regression.

### 5. Production Code Untouched

Confirm S03 did NOT modify any of the production files (those are owned by S01):
- `orch/design_doc_parser.py`
- `orch/daemon/scope_overlap.py`
- `orch/batch_planner.py`

S03 may import from these modules in test files (`from orch.batch_planner import _is_test_path` is legitimate for the parity test) — that is NOT a violation.

If S03 modified any of these, flag as **CRITICAL** with `"category": "conventions"` (workflow violation — Tests step must not patch production code).

### 6. CLAUDE.md Compliance

- Tests live under `tests/unit/` (correct — pure helpers).
- No live-DB connections, no `importlib.reload(orch.config)`, no DB mocking.
- No `dashboard.routers.*` or `dashboard.dependencies` imports at module level.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

Confirm:
- All tests pass with zero failures.
- The new I-00071 tests are visible: `uv run pytest tests/unit/test_design_doc_parser.py tests/unit/daemon/test_scope_overlap.py -v` lists them.
- Run count is reasonable (the new tests should add at least ~8-10 cases between the two files).

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Tests don't reproduce the bug, S03 modified production code, lint/format violations |
| **HIGH** | Shape-only assertions, missing reproduction case, test would pass on broken code |
| **MEDIUM (fixable)** | Missing edge case coverage, weak assertion, naming issues |
| **MEDIUM (suggestion)** | Better organization possible, fixture extraction opportunity |
| **LOW** | Nitpicks |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00071",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE.
