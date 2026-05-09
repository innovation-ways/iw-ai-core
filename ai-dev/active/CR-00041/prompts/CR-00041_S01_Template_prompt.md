# CR-00041_S01_Template_prompt

**Work Item**: CR-00041 — Implementation prompt — test-update checklist for renamed CSS classes
**Step**: S01
**Agent**: template-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR makes no migration changes. Do not run any alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00041 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/active/CR-00041/CR-00041_CR_Design.md` — Design document
- `ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md` — Source finding [3] that motivated this CR
- `templates/design/Implementation_Prompt_Template.md` — Master copy to edit
- `ai-dev/templates/Implementation_Prompt_Template.md` — Synced copy to edit (must stay byte-identical to master for the new line)
- `tests/unit/test_template_hints.py` — Parity test file to extend

## Output Files

- `ai-dev/work/CR-00041/reports/CR-00041_S01_Template_report.md` — Step report

## Context

You are implementing **CR-00041 — Implementation prompt — test-update checklist for renamed CSS classes**.

Read the design document first (`ai-dev/active/CR-00041/CR-00041_CR_Design.md`) and the cited CR-00039 self-assess finding [3] to understand the failure mode this CR closes. Then read `CLAUDE.md` for project-specific patterns and conventions, and skim `tests/unit/test_template_hints.py` to understand the existing parity-test patterns (CR-00023) — your new assertion must follow the same parametrize-over-IMPLEMENTATION_TEMPLATES style.

## Requirements

### 1. Add the CSS-class-rename checklist line to both Implementation_Prompt_Template.md copies

Edit BOTH files:

- `templates/design/Implementation_Prompt_Template.md` (master)
- `ai-dev/templates/Implementation_Prompt_Template.md` (synced copy)

Inside the existing `## Test Verification (NON-NEGOTIABLE)` section (after the existing numbered scope rules and before the next top-level `##` heading), add a new numbered item that reads (you may polish wording slightly, but the substring markers in AC2 / the new test MUST appear verbatim):

> **CSS class renames — required test update.** When the design renames a CSS class name, grep the test suite for the old class name and update every assertion to match the new name before reporting `tests_passed: true`. Stale CSS class assertions in tests are a code-review failure mode (see CR-00039 self-assess finding [3]).

Required substring markers (these are what the new unit test asserts on — keep them verbatim somewhere in the new line):

- `CSS class` (case-sensitive)
- `CR-00039` (case-sensitive)

Constraints:

- The new item MUST live INSIDE the existing `## Test Verification (NON-NEGOTIABLE)` section. Do NOT introduce a new top-level `##` heading.
- The line MUST appear in BOTH copies. The two copies must contain the new line byte-identically (the existing parity test for the Pre-flight section relies on byte-for-byte equality of edited blocks; follow the same discipline here).
- Do NOT touch the existing `## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023` section. Its parity is enforced by `test_implementation_pair_pre_flight_blocks_match`; any drift will fail that pre-existing test.
- Do NOT modify the Subagent Result Contract block.

### 2. Extend tests/unit/test_template_hints.py with a new parity assertion

Add a new parametrized test alongside the existing tests in `tests/unit/test_template_hints.py`. The test must:

- Iterate over `IMPLEMENTATION_TEMPLATES` (already defined at the top of the file — do NOT redefine it).
- For each template, read the file content and assert that:
  - The substring `CSS class` is present.
  - The substring `CR-00039` is present.
  - Both substrings appear within the `## Test Verification (NON-NEGOTIABLE)` section (i.e., after the section heading and before the next `## ` top-level heading or end-of-file).

Suggested function name: `test_implementation_template_has_css_rename_checklist`. Reference CR-00041 in the docstring so future readers can trace the assertion to its motivating CR.

Do NOT modify any other test in the file. The existing tests (`test_in_scope_template_mentions_iw_item_status`, `test_implementation_template_has_preflight_section`, `test_implementation_pair_pre_flight_blocks_match`, etc.) must continue to pass without changes.

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Test organization and fixtures
- Build and run commands

Follow all rules defined there exactly. When in doubt, match existing code in the repository — in particular, mirror the style of the existing parametrized tests in `tests/unit/test_template_hints.py`.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Add the new test (`test_implementation_template_has_css_rename_checklist`) FIRST. Run it against the unchanged templates and confirm it fails (the assertion message should clearly identify the missing substring).
2. **GREEN**: Edit both Implementation_Prompt_Template.md copies to add the new checklist line containing both required substrings inside the Test Verification section. Re-run the test and confirm it passes.
3. **REFACTOR**: Confirm the existing tests in `test_template_hints.py` still pass. Confirm the wording reads naturally and is consistent with surrounding bullets in both copies.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order
and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift. If it reformats files,
   inspect the diff and re-stage; do NOT skip.
2. **`make typecheck`** — must report zero errors involving the files you
   touched. Errors elsewhere are pre-existing — note them in your report but
   do not ignore your own.
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not
silently skip.

In your Subagent Result Contract, populate the `preflight` object recording
the result of each command:
- `"ok"` — ran cleanly, no changes / no errors
- `"fixed"` — applies to `format` only; the tool auto-fixed something
- `"skipped:<reason>"` — only if you raised a blocker explaining why

## Test Verification (NON-NEGOTIABLE)

After implementation, verify your own changes — but **DO NOT run the full
test suite**. Full-suite execution is owned by the dedicated QV gate steps
downstream.

Scope rules for this step:

1. Run only the file you modified:
   ```bash
   uv run pytest tests/unit/test_template_hints.py -v
   ```
   All tests in this file MUST pass — both the pre-existing ones (parity, Pre-flight, iw item-status hint) and your new `test_implementation_template_has_css_rename_checklist`.

2. Do NOT run `make test-integration` or `make test-unit` — those are S{NN} QV gates and will run with their own (longer) budgets downstream.

3. Run lint and type checking on your touched files (covered by the Pre-flight gates above).

4. Do NOT report `tests_passed: true` unless `tests/unit/test_template_hints.py` passes with zero failures.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "template-impl",
  "work_item": "CR-00041",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "templates/design/Implementation_Prompt_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "tests/unit/test_template_hints.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

- `completion_status`: Use `complete` when both copies carry the new line, the new test passes, and all pre-flight gates are clean.
- `blockers`: List any issues that prevented full completion.
- `notes`: Any context the next reviewer should know (e.g., minor wording polish you applied beyond the suggested phrasing).
