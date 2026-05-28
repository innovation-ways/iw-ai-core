# CR-00091_S04_Backend_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
**Step**: S04
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

No container/volume/network management commands.

## ⛔ Migrations: agents generate, daemon applies

This step contains no production code and no migration changes.

## Context

Read `CLAUDE.md`, `orch/CLAUDE.md`, and the S03 code-review report. This step is **documentation and conventions only** — no new production code, no new tests. The goal is that every future database-impl agent automatically adopts the PENDING sentinel without being explicitly told.

**Design doc**: `ai-dev/active/CR-00091/CR-00091_CR_Design.md` — AC6 is this step's sole acceptance criterion.

## Deliverable 1: `CLAUDE.md` — PENDING convention rule

In the **Critical Rules** section of `CLAUDE.md`, add the following bullet immediately after the existing migration-related rules (the block starting with "NEVER apply an uncommitted Alembic migration…"):

```
- **MUST** generate new Alembic migrations with `make migration-pending MSG="describe change"` rather than calling `alembic revision --autogenerate` directly. This writes `down_revision = "PENDING"` into the generated file; `migration_rebase.py` resolves it to the real chain head at merge time. See CR-00091.
```

## Deliverable 2: `orch/CLAUDE.md` — PENDING convention rule

In `orch/CLAUDE.md`, locate the **Migrations** section (under the `db/migrations/` row in the Package Structure table or nearby). Add a note after the existing migration entry:

```
Migration generation: use `make migration-pending MSG="…"` (not `alembic revision --autogenerate` directly). Sets `down_revision = "PENDING"`; resolved at merge time. See CR-00091.
```

## Deliverable 3: `skills/iw-new-cr/SKILL.md` — migration section

Find the paragraph in `skills/iw-new-cr/SKILL.md` that describes the `migration-check` qv-gate step (search for "migration-check" or "down_revision"). Immediately before that paragraph, insert:

```markdown
> **Migration generation convention (CR-00091)**: database-impl agents MUST call
> `make migration-pending MSG="describe change"` to generate the migration file.
> This sets `down_revision = "PENDING"` as a sentinel; `migration_rebase.py` resolves
> it to the real chain head at merge time, and `make migration-check` resolves it
> before running the round-trip test. Do NOT call `alembic revision --autogenerate`
> directly — it bakes in a revision ID that may be stale by merge time.
```

## Deliverable 4: `skills/iw-new-feature/SKILL.md` — migration section

Apply the same insertion to `skills/iw-new-feature/SKILL.md`. Find the paragraph that mentions `make migration-check` and insert the same blockquote immediately before it.

## Deliverable 5: `skills/iw-new-incident/SKILL.md` — migration section

Apply the same insertion to `skills/iw-new-incident/SKILL.md`.

## Deliverable 6: `ai-dev/templates/Implementation_Prompt_Template.md` — migration note

Open `ai-dev/templates/Implementation_Prompt_Template.md`. Find any section that mentions `alembic revision --autogenerate` or migration generation. If found, add a note:

```
**Migration generation**: use `make migration-pending MSG="…"` (not `alembic revision --autogenerate`).
This sets `down_revision = "PENDING"` — resolved at merge time. See CR-00091.
```

If no such section exists, add a new **Migration Generation** subsection before the first QV-related section.

## Sync skills mirrors

After editing all skill files, run:
```bash
uv run iw sync-skills
```

This copies `skills/` to `.claude/skills/`. Commit **both** the master copies and the mirrors — per `feedback_skills_sync` memory, both must be committed together.

## Preflight

Run `make lint` after editing all files (catches Jinja2 format-filter issues in templates, ruff on any Python snippets). Fix any issues.

Do not run tests — this step has no code changes.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "backend-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|blocked",
  "files_changed": [
    "CLAUDE.md",
    "orch/CLAUDE.md",
    "skills/iw-new-cr/SKILL.md",
    "skills/iw-new-feature/SKILL.md",
    "skills/iw-new-incident/SKILL.md",
    ".claude/skills/iw-new-cr/SKILL.md",
    ".claude/skills/iw-new-feature/SKILL.md",
    ".claude/skills/iw-new-incident/SKILL.md",
    "ai-dev/templates/Implementation_Prompt_Template.md"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|fixed"
  },
  "tests_passed": true,
  "test_summary": "n/a — documentation-only step",
  "tdd_red_evidence": "n/a — documentation-only step",
  "blockers": [],
  "notes": ""
}
```
