# CR-00017_S09_Template_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S09
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Documentation-only step. You don't need docker. The Docker rule still applies.

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- S01/S03/S05/S07 reports (for accurate command references)
- All 11 prompt templates under `ai-dev/templates/`
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`
- `docs/IW_AI_Core_Agent_Constraints.md` (from CR-00016 — add R2 here)
- `docs/IW_AI_Core_Migration_Checklist.md` — rewrite for the new contract
- `docs/IW_AI_Core_Tech_Stack.md` — update the migration-model section
- `docs/reference/03_merge_fix_automation.md` — update stale `alembic upgrade head` mention

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S09_Template_report.md`
- Updated: all 11 prompt templates
- Updated: `docs/IW_AI_Core_Agent_Constraints.md` (adds R2)
- Updated: 5 CLAUDE.md files (new Critical Rules bullet)
- Updated: `docs/IW_AI_Core_Migration_Checklist.md`
- Updated: `docs/IW_AI_Core_Tech_Stack.md`
- Updated: `docs/reference/03_merge_fix_automation.md`

## Context

S01–S08 shipped the mechanism. S09 updates every place that tells an agent (or a human setting up an agent) what to do. The rule has to be unambiguous everywhere.

## Requirements

### 1. Extend `docs/IW_AI_Core_Agent_Constraints.md` with R2

Insert a new rule block right after R1:

```markdown
### R2. ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md
```

**Unique marker phrase** used by the extended grep test: `⛔ Migrations: agents generate, daemon applies`. Include it verbatim.

### 2. Update all 11 prompt templates

For each file in `ai-dev/templates/*.md`:

- Add R2 as a section, placed alongside R1 (Docker rule from CR-00016) near the top of the document.
- R2 uses the verbatim text from §1.

Double-check both markers end up present: `⛔ Docker is off-limits` (R1) AND `⛔ Migrations: agents generate, daemon applies` (R2).

### 3. Update all 5 CLAUDE.md files

Add a new Critical Rules bullet alongside the Docker bullet from CR-00016:

```markdown
- **NEVER** run `alembic upgrade head` or any alembic command that modifies the live orchestration DB. Write migration files; the daemon applies them post-merge. See `docs/IW_AI_Core_Agent_Constraints.md` (R2). Operator-only bypass: `./ai-core.sh db migrate`, `make db-migrate`, or `uv run iw migrations apply --i-am-operator`.
```

Preserve the existing R1 bullet; R2 joins it.

### 4. Rewrite `docs/IW_AI_Core_Migration_Checklist.md`

Current checklist tells the implementer to `alembic upgrade head`. Rewrite the checklist for the new contract:

1. Write the migration file (`uv run alembic revision --autogenerate -m "..."`).
2. Write the test under `tests/integration/` that exercises the migration on a testcontainer (this the agent DOES run — testcontainer is fine).
3. Commit & push to the worktree branch.
4. **DO NOT** run `alembic upgrade head` against the live DB. The daemon will:
   - (Phase 1) dry-run the migration against a fresh testcontainer before merge.
   - (Phase 2) apply the migration to the live DB after squash-merge.
   - (Phase 3) auto-rollback if Phase 2 fails; freeze the merge queue if rollback also fails.
5. Monitor the dashboard's batch detail view for `pending_migration_log` entries if you want to see the daemon's phase outcomes.

Include a "for operators" section at the bottom with the `iw migrations` and `iw merge-queue` CLI surface.

### 5. Update `docs/IW_AI_Core_Tech_Stack.md`

Find the Alembic / Migrations section. Replace the "agents apply migrations" description with the new model. Add a short box diagram of the 3-phase pipeline (ASCII OK).

### 6. Update `docs/reference/03_merge_fix_automation.md`

Locate the step that says "Run `alembic upgrade head` to verify the migration applies cleanly" (around line 227). Replace with:

```markdown
Verification is now automatic: the daemon's merge pipeline dry-runs the
migration against a testcontainer before merging. If dry-run fails, the
batch is marked MIGRATION_INVALID and the fix-cycle is triggered.
See docs/IW_AI_Core_Migration_Checklist.md and
docs/IW_AI_Core_Agent_Constraints.md (R2).
```

### 7. Grep for stale agent-facing references

After edits, run:

```bash
grep -rn "alembic upgrade head" . \
  --include="*.md" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=.venv \
  --exclude-dir=ai-dev/active
```

Every remaining hit must be in an OPERATOR-facing context (e.g. `ai-core.sh` help text, Makefile comments, operator-facing `docs/IW_AI_Core_DB_Setup.md`). Any agent-facing hit → fix it.

### 8. Do NOT edit `ai-core.sh` or `Makefile`

Those are operator paths. `alembic upgrade head` in them is intentional and stays. Do NOT touch them.

### 9. Do NOT touch the coverage test

S11 extends the coverage test with the new marker. Don't edit the test file from S09.

## Project Conventions

- Match existing markdown style (fences, heading levels, link style).
- Preserve all existing content — this is purely additive for prompt templates and CLAUDE.md files (plus rewrites for the checklist and tech-stack docs).
- Relative links for cross-doc references.

## TDD Requirement

Documentation-only; the grep audit is the verification. No code to test.

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — pass.
2. Both marker phrases present in all 11 templates (manual grep).
3. Zero agent-facing `alembic upgrade head` hits in docs outside the operator-path files.
4. Policy doc has R1 + R2, structured for R3+.

## Subagent Result Contract

Standard template-impl JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S09
uv run iw step-done CR-00017 --step S09 --report ai-dev/active/CR-00017/reports/CR-00017_S09_Template_report.md
```
