# CR-00041_S02_CodeReview_prompt

**Work Item**: CR-00041 — Implementation prompt — test-update checklist for renamed CSS classes
**Step Being Reviewed**: S01 (template-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed exceptions: testcontainers via pytest fixtures; read-only `docker ps/inspect/logs`; `./ai-core.sh` and `make` targets. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR makes no migration changes. Do not run any alembic command. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Pre-Review: Read the design doc FIRST

Before reviewing any code, read `ai-dev/active/CR-00041/CR-00041_CR_Design.md` end-to-end. The design doc's TDD Approach section is authoritative for what S01 was supposed to deliver. CR-00039's S02 first run failed precisely because the reviewer did not consult the design doc TDD section before reviewing — do not repeat that mistake.

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00041 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00041/CR-00041_CR_Design.md` — Design document (acceptance criteria are authoritative)
- `ai-dev/work/CR-00041/reports/CR-00041_S01_Template_report.md` — S01 implementation report
- All files listed in S01's `files_changed`:
  - `templates/design/Implementation_Prompt_Template.md`
  - `ai-dev/templates/Implementation_Prompt_Template.md`
  - `tests/unit/test_template_hints.py`

## Output Files

- `ai-dev/work/CR-00041/reports/CR-00041_S02_CodeReview_report.md` — Review report

## Context

You are reviewing the implementation work done in step S01 by `template-impl` for CR-00041. The change is small: one new checklist line added to two parity-tested copies of `Implementation_Prompt_Template.md`, and one new parametrized assertion in `tests/unit/test_template_hints.py`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in S01's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check
make format-check  # ruff format --check
```

If either reports NEW violations in the changed files, classify each as a **CRITICAL** finding with `category: "conventions"`, the file/line, and the exact violation message.

## Review Checklist

### 1. AC trace (authoritative)

For each Acceptance Criterion in the design doc, confirm:

- **AC1**: Both `Implementation_Prompt_Template.md` copies contain a checklist line inside `## Test Verification (NON-NEGOTIABLE)` that names CSS-class renames as a required test-update trigger and references the design doc TDD section as authoritative. The line cites CR-00039 finding [3].
- **AC2**: `tests/unit/test_template_hints.py` contains a NEW parametrized assertion (over `IMPLEMENTATION_TEMPLATES`) that the new line is present in both copies. The assertion uses substring markers stable enough to survive minor wording polish but specific enough to break if the line is removed (`CSS class` AND `CR-00039` are both required).
- **AC3**: The new line lives INSIDE the existing `## Test Verification (NON-NEGOTIABLE)` section. NO new top-level `##` heading was introduced. The existing `## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023` section is untouched in BOTH copies (verify by running `test_implementation_pair_pre_flight_blocks_match` — it MUST still pass).

A failed AC trace is a **HIGH** finding.

### 2. Parity discipline

The new line MUST be byte-identical between the two copies. Diff the relevant section of both files:

```bash
diff <(sed -n '/^## Test Verification/,/^## /p' templates/design/Implementation_Prompt_Template.md) \
     <(sed -n '/^## Test Verification/,/^## /p' ai-dev/templates/Implementation_Prompt_Template.md)
```

Any divergence in the new line is a **HIGH** finding.

### 3. Test correctness

- The new test function MUST iterate over the existing `IMPLEMENTATION_TEMPLATES` constant — it MUST NOT redefine it.
- It MUST assert both required substrings (`CSS class` AND `CR-00039`).
- It MUST verify the substrings appear within the Test Verification section (not anywhere in the file). A test that just greps the whole file passes trivially even if the line lands in the wrong section.
- The test docstring MUST reference CR-00041.

A test that does not break when the new line is removed from one copy is a **HIGH** finding (defeats the purpose of the assertion).

### 4. Scope discipline

- Files outside `scope.allowed_paths` (declared in `workflow-manifest.json`) MUST NOT be modified. The allow-list is exactly: `templates/design/Implementation_Prompt_Template.md`, `ai-dev/templates/Implementation_Prompt_Template.md`, `tests/unit/test_template_hints.py`. Any other file modification is a **CRITICAL** finding.
- The Subagent Result Contract block in either Implementation_Prompt_Template.md copy MUST be untouched. Any edit there is **HIGH**.

### 5. Conventions

- Read `CLAUDE.md` for project conventions.
- The new test function follows the same parametrize-style and naming patterns as the existing `test_implementation_template_*` family in `tests/unit/test_template_hints.py`.

## Test Verification (NON-NEGOTIABLE)

Run the touched test file and report exact counts:

```bash
uv run pytest tests/unit/test_template_hints.py -v
```

All assertions in the file must pass — both pre-existing and the newly added one.

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Out-of-scope edits, broken parity test, regressions | Must fix before merge |
| **HIGH** | AC failure, weak test that does not enforce the rule, parity break in the new line | Must fix before merge |
| **MEDIUM (fixable)** | Wording awkward, missing CR reference in docstring | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Phrasing improvement | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00041",
  "step_reviewed": "S01",
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

- `verdict`: `pass` only if zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM_FIXABLE.
