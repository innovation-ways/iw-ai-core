# CR-00021_S09_Backend_prompt

**Work Item**: CR-00021 -- Rebase alembic down_revision at merge time
**Step**: S09
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Testcontainer fixtures only. `./ai-core.sh` / `make` fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Do NOT run `alembic upgrade/downgrade/stamp` against the live DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00021/CR-00021_CR_Design.md` — Design (canonical content for the docs updates)
- `ai-dev/active/CR-00021/reports/CR-00021_S01_Database_report.md` — schema delta (S01 already partially updated the schema doc)
- `ai-dev/active/CR-00021/reports/CR-00021_S03_Backend_report.md`, `CR-00021_S05_Backend_report.md` — module and wiring landed
- `docs/IW_AI_Core_Daemon_Design.md` — the place to document the new phase
- `docs/IW_AI_Core_Database_Schema.md` — S01 already touched this; S09 tightens narrative
- `CLAUDE.md` (root) — Quick Navigation table
- `orch/CLAUDE.md` — Daemon Modules table

## Output Files

- `docs/IW_AI_Core_Daemon_Design.md` (modified) — new "Pre-merge rebase phase" subsection
- `docs/IW_AI_Core_Database_Schema.md` (modified as needed — S01 did the raw delta; S09 polishes narrative)
- `CLAUDE.md` (modified) — Quick Navigation row added
- `orch/CLAUDE.md` (modified) — Daemon Modules table row added
- `ai-dev/active/CR-00021/reports/CR-00021_S09_Backend_report.md` — step report

## Context

Update the four documentation files so future contributors understand the merge pipeline's new shape. Do NOT introduce new architectural content beyond what the design describes — docs mirror the shipped behaviour.

## Requirements

### 1. `docs/IW_AI_Core_Daemon_Design.md` — new subsection

In the merge-queue / migration-pipeline section, insert a subsection titled **"Phase 0: Pre-merge rebase (CR-00021)"** BEFORE the existing "Phase 1: Pre-merge dry-run" subsection. Content:

- One-paragraph summary of the problem (parallel batches produce stale down_revisions) and the solution (rebase + rewrite at merge time).
- Order of operations (fetch → rebase → identify batch's own files → rewrite stale down_revision → commit) — short bullet list.
- Failure semantics:
  - Rebase conflict → `migration_rebase_failed`, queue NOT frozen.
  - Rebased dry-run fails → `migration_invalid` (existing), queue NOT frozen.
  - Only Phase 3 rollback failure freezes (unchanged).
- Reference to `orch/daemon/migration_rebase.py` and the `RebaseResult` dataclass.
- Diagram (ASCII or Mermaid) showing the 4-step flow: Rebase → Dry-run → Squash-merge → Apply.

Update the existing "Phase 1" subsection intro line to note that Phase 1 runs AFTER Phase 0 and uses the worktree's migrations directory (fixes the pre-existing dry-run-on-main-repo bug).

Update the existing failure-matrix table to include the new `migration_rebase_failed` state.

### 2. `docs/IW_AI_Core_Database_Schema.md` — narrative polish

S01 already added `migration_rebase_failed` to the `batch_item_status` enum list, added `old_revision` to `pending_migration_log` columns, and updated the `ck_pending_migration_log_phase` CHECK to 4 values. S09 tightens the narrative:

- Add a one-liner linking `old_revision` to its only consumer: "Populated by the Phase 0 rebase (CR-00021) when it rewrites a migration's `down_revision`; NULL for all other phases."
- Ensure the `batch_item_status` narrative lists all migration-related states adjacently with a one-line description each (`migration_invalid`, `migration_rolled_back`, `migration_rebase_failed`).

### 3. `CLAUDE.md` Quick Navigation

Add a row to the Quick Navigation table:

```markdown
| Pre-merge migration rebase | `orch/daemon/migration_rebase.py` · `docs/IW_AI_Core_Daemon_Design.md` |
```

Place it next to the existing migration-pipeline row.

### 4. `orch/CLAUDE.md` Daemon Modules

Add a row to the Daemon Modules table (alphabetised):

```markdown
| `migration_rebase.py` | Pre-merge rebase phase (CR-00021): fetch main, rebase branch, rewrite batch's stale migration down_revisions, commit the edit |
```

## Project Conventions

- Keep docs concise — this CR should add ≤ 2 paragraphs of narrative + 1 small diagram + a few table rows, NOT a full rewrite.
- Diagram style: match existing Mermaid / ASCII usage in the file (look above/below for precedent).
- Match the tone of surrounding content (factual, imperative, no marketing voice).
- Reference CR-00021 and/or CR-00017 inline when pointing to related changes — consistent with how CR-00019 and CR-00020 are cited elsewhere.

## TDD Requirement

Docs-only step; no tests required. However, you must verify that code references in the docs are accurate:

1. File paths exist in the worktree.
2. Class / function names match the landed code (grep for the symbols).
3. Behaviour described matches the modules as implemented (spot-check the key assertions).

## Test Verification (NON-NEGOTIABLE)

1. `make lint` / `make format` / `make typecheck` — must pass (documentation changes do not typically break these, but still run them).
2. Spot-check the docs renders correctly on GitHub preview if possible (tables, Mermaid blocks).
3. No broken cross-references to files or symbols.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "backend-impl",
  "work_item": "CR-00021",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "docs/IW_AI_Core_Daemon_Design.md",
    "docs/IW_AI_Core_Database_Schema.md",
    "CLAUDE.md",
    "orch/CLAUDE.md"
  ],
  "tests_passed": true,
  "test_summary": "lint/format/typecheck passed (no new tests required)",
  "blockers": [],
  "notes": ""
}
```
