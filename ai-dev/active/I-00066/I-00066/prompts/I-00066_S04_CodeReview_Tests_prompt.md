# I-00066_S04_CodeReview_Tests_prompt

**Work Item**: I-00066 -- OSS finding modal too narrow and footer buttons unclear
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. Full policy:
docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This incident touches no database state — there is no migration step.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00066 --json`.
- `ai-dev/active/I-00066/I-00066_Issue_Design.md` -- Design document
- `ai-dev/active/I-00066/reports/I-00066_S03_Tests_report.md` -- S03 report
- `tests/dashboard/test_i00066_oss_modal_styling.py` -- New test file
- The files under test:
  - `dashboard/static/tailwind.src.css`
  - `dashboard/static/styles.css`
  - `dashboard/templates/fragments/oss_finding_modal.html`

## Output Files

- `ai-dev/active/I-00066/reports/I-00066_S04_CodeReview_report.md`

## Context

You are reviewing the test file produced in step S03 by the Tests
agent for **I-00066**. The tests must demonstrably fail before the
fix and pass after, and must verify SEMANTIC values (specific
expected strings), not just shape.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the new test file → CRITICAL findings with
`category: "conventions"`.

## Review Checklist

### 1. Reproduction guarantee (CRITICAL — see I003 lesson)

For each of the four tests, verify mentally that they would FAIL on
the pre-fix `main` branch. If any test would still PASS on `main`,
that is a CRITICAL finding — the test is shape-only, not semantic.

Specifically check:

- `test_i00066_modal_inner_widened_in_source_css` asserts
  `"max-width: 80vw" in body` (semantic, specific value) AND
  `"36rem" not in body` (specific UNWANTED value absent). NOT just
  `".oss-modal-inner" in css`.
- `test_i00066_modal_inner_widened_in_compiled_css` does the same
  for `dashboard/static/styles.css` (allowing both
  `max-width:80vw` and `max-width: 80vw` to handle minified
  output).
- `test_i00066_footer_close_uses_peer_button_class` asserts
  `modal-footer-close` is a class on the FOOTER Close button
  specifically, not just somewhere in the file. The match must
  pin to the button whose text is `Close` (not the header `×`).
- `test_i00066_footer_button_class_styled_in_source_css` asserts
  the new `.modal-footer-close` rule contains BOTH `border:` and
  `padding:` declarations. NOT just that the selector exists.

### 2. Architecture / location

- Test file lives at
  `tests/dashboard/test_i00066_oss_modal_styling.py` (correct dir).
- Uses `Path(__file__).resolve().parents[2]` to locate REPO_ROOT
  (or another deterministic, no-cwd-dependent approach). Hardcoded
  absolute paths are CRITICAL.
- No DB, no network, no fixtures from `tests/conftest.py` that spin
  up testcontainers (this is a static-file test).

### 3. Test isolation

- Tests do not mutate any file (read-only).
- Tests are independent — running one does not affect another.

### 4. Project conventions

- pytest style, function-level tests, no `unittest`.
- Test names start with `test_` and are descriptive.
- Imports are organized.

### 5. No collateral damage

- Only the new test file was added.
- `tests/conftest.py`, `tests/dashboard/conftest.py`, `Makefile`,
  `pyproject.toml`, `pytest.ini` — UNCHANGED.

### 6. Run the tests

```bash
uv run pytest tests/dashboard/test_i00066_oss_modal_styling.py -x -v
make test-unit
```

All four new tests pass; broader unit suite has no regressions.

## Test Verification (NON-NEGOTIABLE)

Run the targeted file AND `make test-unit`. Report results
accurately.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Tests are shape-only (would pass on `main`); test file in wrong location; tests touch live DB; tests modify files |
| **HIGH** | Missing one of the four required tests; test asserts wrong file/path |
| **MEDIUM (fixable)** | Convention violation, formatting drift, weak assertion |
| **MEDIUM (suggestion)** | Improvement |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00066",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file",
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
