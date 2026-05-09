# CR-00040_S01_Template_prompt

**Work Item**: CR-00040 -- CodeReview Templates — Anchor Reviewers to Design Doc Before Code Inspection
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

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

This step does not generate or modify any migration. The files you edit
are markdown prompt templates only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status CR-00040 --json`. The `workflow-manifest.json` file is a design-time snapshot and may be out of date (CR-00023).
- `ai-dev/work/CR-00040/CR-00040_CR_Design.md` -- Design document (especially Desired Behavior, Acceptance Criteria, and Notes)
- `templates/design/CodeReview_Prompt_Template.md` -- master copy to be edited
- `templates/design/CodeReview_Final_Prompt_Template.md` -- master copy to be edited
- `ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md` -- source of the finding being addressed (read finding [1] for context, line numbers, and the recommended phrasing)

## Output Files

- `ai-dev/work/CR-00040/reports/CR-00040_S01_Template_report.md` -- Step report

## Context

You are implementing the only implementation step of **CR-00040**. The change is small and well-scoped: edit two markdown prompt templates so that the "read the design doc" instruction becomes a prominent section instead of a buried line, then propagate the edits to every per-project mirror via `iw sync-templates`.

Read the design document FIRST (yes — the very thing this CR is about). Pay particular attention to the **Acceptance Criteria** section: AC1–AC5 are the contract you must satisfy. AC5 is especially important — the existing Docker / Migration banners and Pre-Review Lint & Format Gate sections must be preserved byte-for-byte; only the new section is added, plus minor checklist-bullet additions inside `### 5. Testing` and `### 1. Completeness vs Design Document`.

## Requirements

### 1. Add new "## Read the Design Document FIRST" section to `templates/design/CodeReview_Prompt_Template.md`

Insert the new section **between** the existing `## Context` section and the existing `## Pre-Review Lint & Format Gate` section. The new section must:

- Begin with the exact heading `## Read the Design Document FIRST` (H2, no decorations).
- Open with one short imperative sentence stating that the reviewer must do this BEFORE running lint/format and BEFORE opening any changed files.
- List 3–5 imperative bullets covering: (a) read the design doc's `## Acceptance Criteria` in full, (b) read the design doc's `## TDD Approach` in full, (c) write down every test file the design names by path, (d) carry these expectations into the `## Review Checklist` below as a first-class anchor.
- Close with a one-line consequence framing: "If the design doc explicitly names test files that should have changed and they don't appear in the implementation report's `files_changed`, that is a CRITICAL finding."
- Total length: aim for ~12–18 lines including the heading and a blank trailing line. Keep it scannable.

Then, inside the existing `## Review Checklist` → `### 5. Testing` subsection, append one new bullet phrased substantially as: "Do test files cover the assertions the design doc's TDD section calls out by name? If a TDD-section test file is missing from `files_changed`, raise a CRITICAL finding."

Do NOT alter the `## Context` paragraph itself, the `## Pre-Review Lint & Format Gate` content, the `## Severity Levels` table, or the `## Review Result Contract` JSON schema. AC5 requires those to be preserved verbatim.

### 2. Mirror the change in `templates/design/CodeReview_Final_Prompt_Template.md`

Insert the same `## Read the Design Document FIRST` section in the same position (between `## Context` and `## Pre-Review Lint & Format Gate`). Adjust the bullet wording slightly so it reflects the Final reviewer's job:

- Replace the closing line with: "Cross-check every test file mentioned in the design doc's TDD section against the `files_changed` arrays of ALL implementation step reports. Any test file the design names that does not appear anywhere is a CRITICAL finding."

Then, inside the existing `### 1. Completeness vs Design Document` checklist (already present in the Final template), append: "Are all test files the design doc's TDD section names by path actually present in some implementation step's `files_changed`? Missing entries are CRITICAL."

Same preservation rule: do not touch banners, lint/format gate, severity levels, or result contract.

### 3. Run `iw sync-templates` to propagate the change to every project

After the two master files are saved, run:

```bash
uv run iw sync-templates
```

This walks `projects.toml` and copies every file under `templates/design/` into each project's `ai-dev/templates/` mirror. Verify the run completed cleanly and the local `ai-dev/templates/CodeReview_Prompt_Template.md` and `ai-dev/templates/CodeReview_Final_Prompt_Template.md` files now contain the new section.

If `iw sync-templates` reports any error or skip, STOP and raise a blocker — partial sync is exactly the drift mode this CR is meant to prevent.

### 4. Verify byte-equivalence between masters and local mirrors

After the sync, run:

```bash
diff -u templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md
diff -u templates/design/CodeReview_Final_Prompt_Template.md ai-dev/templates/CodeReview_Final_Prompt_Template.md
```

Both diffs must be empty (exit code 0). If either is non-empty, the sync did not complete; STOP and raise a blocker.

### 5. Commit only the four files declared in `scope.allowed_paths`

The merge-time scope gate (CR-00033) will block the merge if any other file is modified. The four allowed files are:

- `templates/design/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md`

Plus the implicit `ai-dev/active/CR-00040/**` (this design folder) and `ai-dev/archive/CR-00040/**`. Do not edit any other file.

## Project Conventions

Read the project's `CLAUDE.md` for:

- The hard rule that template master copies under `templates/design/` MUST be re-synced via `iw sync-templates` after editing (see also the `feedback_templates_sync` memory).
- Markdown style: H2 (`##`) for section headings, lower-case for emphasis (`**bold imperative bullets**`), no emoji decorations except the existing `⛔` banners.
- The convention from CR-00023 that prompt-template edits are owned by the `template-impl` agent.

When in doubt, match the existing structure of the file being edited — both target templates have a clear sectioning style; copy the visual rhythm of `## Pre-Review Lint & Format Gate` (your new section is its sibling).

## TDD Requirement

This step does not add or modify any executable code. There are no Python tests to write. The "test" is direct verification of AC1–AC5 by reading the resulting files; the S02 reviewer will perform that check. Do NOT invent vacuous tests for markdown content.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, you MUST run these in order:

1. **`make format`** — auto-fixes formatting drift. Markdown is not formatted by ruff, so this should be a no-op; record `"ok"` in your `preflight` block. If it reformats anything, inspect the diff carefully — anything outside the four allowed files indicates a bug elsewhere and you should raise a blocker.
2. **`make type-check`** — must report zero NEW errors. Markdown changes don't affect mypy, so this should be a no-op; record `"ok"`.
3. **`make lint`** — must report zero NEW errors in the changed files. Markdown changes don't affect ruff, so this should be a no-op; record `"ok"`.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

This step touches no Python and no test files. Do NOT run `make test-unit` or `make test-integration` — they are owned by the QV gate steps S07 (and would be a no-op signal anyway). Record `tests_passed: true` and `test_summary: "skipped: no Python changes"` in your result contract.

## Migration Verification (Database steps only — NON-NEGOTIABLE)

N/A — this step generates no migration. Skip.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "template-impl",
  "work_item": "CR-00040",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "skipped: no Python changes",
  "blockers": [],
  "notes": "iw sync-templates completed; both diff -u checks returned empty."
}
```

- If `iw sync-templates` failed or either `diff -u` returned non-empty output, set `completion_status: blocked` and record the failure in `blockers`.
- If you find that one of the master templates already contains a `## Read the Design Document FIRST` section (e.g., a concurrent CR landed first), STOP and raise a blocker — do not silently merge or duplicate.
- `notes`: include the exact command output for `iw sync-templates` (or a one-line summary if it was clean), and confirm both `diff -u` checks were empty.
