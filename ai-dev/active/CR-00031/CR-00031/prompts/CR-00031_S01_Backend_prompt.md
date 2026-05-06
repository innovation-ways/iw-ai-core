# CR-00031_S01_Backend_prompt

**Work Item**: CR-00031 — Add CLAUDE.md Critical Rule for `make css` no-op fallback to direct CSS append
**Step**: S01
**Agent**: backend-impl

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

This step writes documentation only. No alembic invocation is permitted.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00031 --json` is authoritative.
- `ai-dev/active/CR-00031/CR-00031_CR_Design.md` — Design document (read first, especially the **Acceptance Criteria** section).
- `ai-dev/active/I-00067/reports/I-00067_self_assess_report.md` — Source incident; finding [2] is the rationale.
- `CLAUDE.md` — The single file you will modify.

## Output Files

- `ai-dev/work/CR-00031/reports/CR-00031_S01_Backend_report.md` — Step report.
- Modified: `CLAUDE.md` (one new bullet in the `## Critical Rules` section).

## Context

You are implementing the **only** code-side change for CR-00031: adding a single bullet to `CLAUDE.md`'s `## Critical Rules` section that documents the workaround when `make css` is a no-op or the Tailwind CLI cannot run.

Read the design document first. Then read the surrounding bullets in `CLAUDE.md`'s `## Critical Rules` to match their tone. The current Critical Rules block sits between roughly line 43 and line 55 of `CLAUDE.md` (between the `## Architecture` section and the `## Configuration` section). The bullets use bold keywords like `**NEVER**`, `**MUST**`, `**CRITICAL**`, and `**NEW**`.

## Requirements

### 1. Add the new bullet

Append a new bullet to the existing unordered list under `## Critical Rules`. The bullet must:

- Use a bold keyword from the existing palette — prefer `**MUST**` to match the surrounding NEVER/MUST/CRITICAL/NEW style.
- Name the **symptom** explicitly: `make css` produces "Nothing to be done for 'css'" OR the Tailwind CLI fails (e.g., `MODULE_NOT_FOUND` for `postcss-selector-parser`).
- Prescribe the **action**: append plain CSS rules directly to `dashboard/static/styles.css` (note: plain CSS is deployable as-is and does not require Tailwind compilation).
- Mark the rule as a **temporary mitigation** — include language like "until the Tailwind toolchain is repaired in worktrees" so future readers know to remove the bullet once the platform fix lands (tracked as I-00067 finding [3]).
- Reference **I-00067** inline (e.g., "(see I-00067)") so the audit trail is preserved.

A reasonable wording (you may adjust to fit the surrounding style):

> **MUST** append plain CSS rules directly to `dashboard/static/styles.css` when `make css` reports "Nothing to be done" or the Tailwind CLI fails (e.g., missing `postcss-selector-parser`) — plain CSS is served as-is, so no Tailwind recompile is required. Temporary mitigation until the Tailwind toolchain is repaired in worktrees (see I-00067).

### 2. Do not modify anything else

- Do **not** touch any other section of `CLAUDE.md`.
- Do **not** reformat existing bullets.
- Do **not** edit any other file in the repo.
- Do **not** add or modify tests — this is a doc-only change with no runtime behavior to test.

### 3. Verify the diff is bounded

After your edit, run `git diff CLAUDE.md` and confirm the only change is the addition of one bullet inside the `## Critical Rules` list. No reordering, no whitespace-only changes elsewhere.

## Project Conventions

Read `CLAUDE.md` for the project's bullet style and tone. The new bullet should read like a peer of the existing ones — directive, terse, with bold keywords.

## TDD Requirement

**Not applicable.** This change has no runtime behavior. There is nothing to assert. The acceptance criteria (AC1–AC4) are verified by the reviewer reading the diff in S02 and S03, and by the QV gates confirming no Python/lint regressions.

In your result contract, set `tests_passed: true` and `test_summary: "skipped: doc-only change, no tests applicable"`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Even for a doc-only change, run the standard pre-flight gates against the changed files:

1. **`make format`** — should be a no-op (no Python touched). If it modifies anything, investigate: it should not.
2. **`make typecheck`** — should be a no-op for `CLAUDE.md`. Confirm the run reports zero errors involving the files you touched.
3. **`make lint`** — should report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "CR-00031",
  "completion_status": "complete",
  "files_changed": [
    "CLAUDE.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "skipped: doc-only change, no tests applicable",
  "blockers": [],
  "notes": "Single bullet added to '## Critical Rules' section per AC1–AC4."
}
```
