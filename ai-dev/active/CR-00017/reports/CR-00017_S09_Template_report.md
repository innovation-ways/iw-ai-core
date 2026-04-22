# CR-00017 S09 — Template Report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S09 (template-impl)
**Date**: 2026-04-22

## What Was Done

S09 updated all agent-facing documentation to reflect the new migration contract:
**agents write migration files, daemon applies them**.

## Files Changed

### 1. `docs/IW_AI_Core_Agent_Constraints.md`
Replaced R2 placeholder with the full migration rule, with unique marker phrase
`⛔ Migrations: agents generate, daemon applies`. R3 placeholder added for future rules.

### 2. All 11 prompt templates (`ai-dev/templates/*.md`)
Added R2 section immediately after the existing R1 (Docker) section in all templates:
- `Feature_Design_Template.md`
- `Issue_Design_Template.md`
- `CR_Design_Template.md`
- `Implementation_Prompt_Template.md`
- `QualityValidation_Template.md`
- `QualityValidation_FIX_Prompt_Template.md`
- `QVBrowser_Prompt_Template.md`
- `CodeReview_Prompt_Template.md`
- `CodeReview_FIX_Prompt_Template.md`
- `CodeReview_Final_Prompt_Template.md`
- `CodeReview_FIX_Final_Prompt_Template.md`

Both marker phrases verified present in all 11 templates:
- `⛔ Docker is off-limits` (R1)
- `⛔ Migrations: agents generate, daemon applies` (R2)

### 3. All 5 CLAUDE.md files
Added R2 critical rule bullet alongside the existing R1 Docker bullet in:
- `CLAUDE.md`
- `orch/CLAUDE.md`
- `dashboard/CLAUDE.md`
- `executor/CLAUDE.md`
- `tests/CLAUDE.md`

### 4. `docs/IW_AI_Core_Migration_Checklist.md`
Complete rewrite. Previously (v1.0.0) instructed agents to run `alembic upgrade head`.
Now the checklist tells agents to:
1. Write migration file (`alembic revision --autogenerate -m "..."`)
2. Write testcontainer-based integration test
3. Commit & push
4. **Do NOT run `alembic upgrade head`** — daemon handles it via 3-phase pipeline

Includes a "For Operators" section covering `iw migrations` CLI surface.

### 5. `docs/IW_AI_Core_Tech_Stack.md`
Updated the Alembic row in the Tech Stack table to document the new migration model.
Added ASCII pipeline diagram showing Phase 1 (dry-run), Phase 2 (apply), Phase 3 (rollback).

### 6. `docs/reference/03_merge_fix_automation.md`
Replaced the stale step "Run `alembic upgrade head` to verify the migration applies cleanly"
with the new contract statement: daemon dry-runs migration automatically before merge;
if dry-run fails, batch is marked MIGRATION_INVALID and fix-cycle triggers.

## Grep Audit

Ran `grep -rn "alembic upgrade head"` across all `.md` files excluding `.git`, `.worktrees`,
`.venv`, and `ai-dev/active/`.

All remaining hits fall into one of these categories:
- **Operator-facing docs** (`docs/IW_AI_Core_Tech_Stack.md` Makefile section, `CLAUDE.md` common commands section — these document `./ai-core.sh db migrate` and `make db-migrate`, which are intentional operator entry points)
- **Policy documents** that warn against running it (e.g., `docs/IW_AI_Core_Agent_Constraints.md`, `docs/IW_AI_Core_Migration_Checklist.md`, all CLAUDE.md critical rules)
- **Unchanged operator paths** (`ai-core.sh`, `Makefile`, `scripts/e2e_dashboard_entrypoint.sh`) — per instruction, these were NOT edited

No agent-facing content was found with a stale `alembic upgrade head` reference.

## Verification

- `make lint` fails due to pre-existing SIM117 lint errors in `tests/unit/test_merge_queue.py:256` — unrelated to S09 changes; those errors existed before this work
- `uv run ruff check [all S09 modified files]` → All checks passed
- Both R1 and R2 marker phrases confirmed present in all 11 templates (100% coverage)
- Zero agent-facing stale references remaining

## Notes

- The lint failure (`tests/unit/test_merge_queue.py:256`) is a pre-existing issue in code that was not touched by S09 (SIM117: nested `with` statements should be combined). This is the lint baseline for the repo and is tracked separately.
- `ai-dev/active/CR-00017/` was excluded from grep audits as instructed (those are active work item files, not template/policy docs).
- `ai-core.sh`, `Makefile`, and `scripts/e2e_dashboard_entrypoint.sh` were NOT modified — these are operator paths where `alembic upgrade head` is intentional and correct.