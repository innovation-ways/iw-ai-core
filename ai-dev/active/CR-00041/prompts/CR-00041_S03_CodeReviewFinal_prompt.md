# CR-00041_S03_CodeReviewFinal_prompt

**Work Item**: CR-00041 — Implementation prompt — test-update checklist for renamed CSS classes
**Step**: S03
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Allowed exceptions: testcontainers via pytest fixtures; read-only `docker ps/inspect/logs`; `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR makes no migration changes. Do not run any alembic command. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00041 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00041/CR-00041_CR_Design.md` — Design document
- All implementation step reports under `ai-dev/work/CR-00041/reports/CR-00041_S*_*_report.md`
- All per-agent code review reports under `ai-dev/work/CR-00041/reports/CR-00041_S*_CodeReview_report.md`
- All files listed in S01's `files_changed`:
  - `templates/design/Implementation_Prompt_Template.md`
  - `ai-dev/templates/Implementation_Prompt_Template.md`
  - `tests/unit/test_template_hints.py`

## Output Files

- `ai-dev/work/CR-00041/reports/CR-00041_S03_CodeReviewFinal_report.md` — Final review report

## Context

You are performing the **final cross-agent review** of all implementation work for CR-00041. The change is small (one prompt-template line + one test) but the integration concern is real: the new line, the new test, and the existing CR-00023 parity-tested sections must all coexist without drift between the two `Implementation_Prompt_Template.md` copies.

S02 has already done a per-agent review of S01. Your job is to catch cross-cutting issues S02 could not — primarily, the holistic interaction between the new line, the existing parity tests, and downstream consumers (the executor / agent-launch step that reads these prompts at runtime).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint          # ruff check
make format-check  # ruff format --check
```

Any NEW violations in the changed files = **CRITICAL** finding (`category: "conventions"`, file/line, exact message).

## Review Checklist

### 1. Completeness vs Design Document

- Every Acceptance Criterion (AC1, AC2, AC3) in `CR-00041_CR_Design.md` is satisfied.
- No section of the design has zero corresponding code change.
- No TODO comments, no placeholder text, no half-applied edits in either Implementation_Prompt_Template.md copy.

### 2. Cross-Copy Consistency (the central risk for this CR)

- The newly added checklist line is byte-identical between `templates/design/Implementation_Prompt_Template.md` and `ai-dev/templates/Implementation_Prompt_Template.md`.
- The line lives at the same relative position within `## Test Verification (NON-NEGOTIABLE)` in both copies.
- The existing `## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023` block is untouched in BOTH copies — verify by running `uv run pytest tests/unit/test_template_hints.py::test_implementation_pair_pre_flight_blocks_match -v`. Any failure here = **HIGH** finding (CR-00023 parity broken).
- The Subagent Result Contract block in either copy is untouched — verify the `"preflight":` object still appears and matches between the two copies (existing test `test_implementation_template_contract_has_preflight_object` covers this).

### 3. Test Discipline

- The new test function in `tests/unit/test_template_hints.py` is parametrized over the existing `IMPLEMENTATION_TEMPLATES` constant (no redefinition).
- The required substring markers (`CSS class` AND `CR-00039`) are both asserted, AND the assertion verifies the markers appear within the Test Verification section (not anywhere in the file).
- Removing the new line from EITHER copy would cause the test to fail. Probe this mentally: if the test only greps the whole file for `"CSS class"`, it would still pass if the line accidentally landed in (say) the Pre-flight section — that is a **HIGH** finding.

### 4. Scope Discipline

- Only the three allow-listed files were modified: `templates/design/Implementation_Prompt_Template.md`, `ai-dev/templates/Implementation_Prompt_Template.md`, `tests/unit/test_template_hints.py`. Run `git diff --name-only main...HEAD` and confirm the list. Any extra file is **CRITICAL**.

### 5. No Regressions in test_template_hints.py

- ALL existing assertions in `tests/unit/test_template_hints.py` continue to pass:
  - `test_in_scope_template_mentions_iw_item_status`
  - `test_out_of_scope_template_unchanged`
  - `test_implementation_template_has_preflight_section`
  - `test_implementation_template_contract_has_preflight_object`
  - `test_non_implementation_template_lacks_preflight`
  - `test_implementation_pair_pre_flight_blocks_match`

A regression in any of these = **CRITICAL** (the new edit broke an existing CR-00023 invariant).

### 6. Consumer Impact

- The executor reads these prompt templates only via `iw sync-templates` / step-launch. The new line adds prose; it does NOT introduce any new placeholder (`{ID}`, `{NN}`, etc.) that the executor would need to substitute. Confirm no new unsubstituted placeholders were introduced.
- The line is a no-op for steps that do not rename CSS classes (Backend, Database, Pipeline) — it reads as advisory and does not block.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
```

This CR changes only prompt-template prose plus one new unit-test assertion in `tests/unit/test_template_hints.py`. There are no Python runtime changes, no schema changes, and no executor changes — running `make test-integration` here would be wasted budget and is forbidden by the review rule for `*-impl` prompts (full-suite execution is owned by dedicated QV gates downstream; integration tests are not relevant to this CR). If `make test-unit` reports any new failure relative to pre-S01 green, that is a **CRITICAL** finding.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Out-of-scope edits, broken existing parity test, integration regression | Must fix |
| **HIGH** | AC failure, weak test, parity break in the new line, missing required substring | Must fix |
| **MEDIUM (fixable)** | Wording inconsistency between copies, minor test-style drift | Should fix |
| **MEDIUM (suggestion)** | Phrasing improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "CR-00041",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security|conventions",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "ac_trace": {
    "AC1": "pass|fail",
    "AC2": "pass|fail",
    "AC3": "pass|fail"
  },
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings AND every AC traces to `pass`.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
