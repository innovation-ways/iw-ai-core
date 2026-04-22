# CR-00017 S10 — Code Review Report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S10 (code-review-impl)
**Review Target**: S09 (template-impl)
**Date**: 2026-04-22

## What Was Reviewed

S09 updated all agent-facing documentation and prompt templates to reflect the new
migration contract: **agents write migration files, daemon applies them**.

## Review Checklist — All Items PASSED

### 1. R2 in policy doc ✅

`docs/IW_AI_Core_Agent_Constraints.md`:
- R1 (Docker) at line 19, R2 (Migrations) at line 50 — correctly ordered
- Marker phrase `⛔ Migrations: agents generate, daemon applies` appears verbatim at line 50
- R3 placeholder present at line 84
- Allowed/forbidden lists accurate: agents can `revision --autogenerate`, can `history/current/show`; operators can `iw migrations list-pending/dry-run/apply --i-am-operator`; direct `ai-core.sh db migrate` / `make db-migrate` preserved as operator entry points

### 2. All 11 prompt templates carry BOTH markers ✅

Ran the mandated grep:
```bash
for f in ai-dev/templates/*.md; do
  grep -q "⛔ Docker is off-limits" "$f" && \
  grep -q "⛔ Migrations: agents generate, daemon applies" "$f" || echo "MISSING: $f"
done
```
No MISSING lines. All 11 templates confirmed:
- `CR_Design_Template.md`
- `CodeReview_FIX_Final_Prompt_Template.md`
- `CodeReview_FIX_Prompt_Template.md`
- `CodeReview_Final_Prompt_Template.md`
- `CodeReview_Prompt_Template.md`
- `Feature_Design_Template.md`
- `Implementation_Prompt_Template.md`
- `Issue_Design_Template.md`
- `QVBrowser_Prompt_Template.md`
- `QualityValidation_FIX_Prompt_Template.md`
- `QualityValidation_Template.md`

Each template has R1 section (`## ⛔ Docker is off-limits`) immediately followed by R2 section (`## ⛔ Migrations: agents generate, daemon applies`). Both sections include the full command block (upgrade head, upgrade \<revision\>, downgrade, stamp) and the "write the migration FILE" instruction.

### 3. All 5 CLAUDE.md files have BOTH bullets ✅

Checked all 5 files: root `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`. Each contains:
- The Docker rule bullet (CR-00016 R1, preserved as-is)
- The new R2 migrations bullet with exact text: `**NEVER** run alembic upgrade head or any alembic command that modifies the live orchestration DB. Write migration files; the daemon applies them post-merge. See docs/IW_AI_Core_Agent_Constraints.md (R2).`
- Both reference `docs/IW_AI_Core_Agent_Constraints.md` explicitly

### 4. Migration Checklist rewritten cleanly ✅

`docs/IW_AI_Core_Migration_Checklist.md` v2.0.0:
- Old "run alembic upgrade head" step removed entirely
- New 4-phase agent workflow (write file → write test → commit/push → STOP)
- Phase diagram for the 3-phase daemon pipeline in section 2.4
- "For Operators" section at bottom with `iw migrations {list-pending|dry-run|apply}` CLI surface and operator bypass paths (`ai-core.sh db migrate`, `make db-migrate`)

### 5. Tech stack doc updated ✅

`docs/IW_AI_Core_Tech_Stack.md`:
- "Migration model" row now reads "Agent writes file, daemon applies (R2 policy)" with full 3-phase pipeline description
- ASCII diagram showing Phase 1 (dry-run), Phase 2 (apply), Phase 3 (rollback)
- "Agents MUST NOT run `alembic upgrade head`" prose present
- Operator path `db-migrate` and `db-revision` targets still documented in Makefile section (intentional — operator entry points)

### 6. merge_fix_automation.md updated ✅

`docs/reference/03_merge_fix_automation.md`:
- Old "Run `alembic upgrade head` to verify the migration applies cleanly" replaced with: "Verification is now automatic: the daemon's merge pipeline dry-runs the migration against a testcontainer before merging. If dry-run fails, the batch is marked MIGRATION_INVALID and the fix-cycle is triggered."
- References `docs/IW_AI_Core_Migration_Checklist.md` and `docs/IW_AI_Core_Agent_Constraints.md` (R2)

### 7. Grep audit — clean ✅

Ran `grep -rn "alembic upgrade head"` across all `.md` files excluding `.git`, `.worktrees`, `.venv`, `ai-dev/active`.

Remaining hits (all acceptable):
- `docs/IW_AI_Core_Tech_Stack.md:554,588` — Makefile help text documenting `make db-migrate` (operator path)
- `docs/IW_AI_Core_Migration_Checklist.md:74-76` — warning label "Do NOT run `alembic upgrade head`" (this is the correct new behavior)
- `dashboard/CLAUDE.md:8`, `orch/CLAUDE.md:8`, `executor/CLAUDE.md:8`, `CLAUDE.md:37` — the critical rules bullet (correct new behavior)
- `tests/CLAUDE.md:20` — critical rules bullet (correct new behavior)
- `docs/misc/guide_to_create_opencode_commands.md:288` — misc guide (not agent-facing policy)
- `docs/misc/guide_to_create_claude_file.md:145` — misc guide (not agent-facing policy)
- `ai-dev/templates/*.md` — inside the R2 block where it enumerates forbidden commands (correct)
- `skills/iw-doc-generator/references/release-notes-template.md:52` — skill template (not agent-facing)

No agent-facing content instructs agents to run `alembic upgrade head`.

### 8. Not touched ✅

Per instructions and S09 report:
- `ai-core.sh` — untouched ✅
- `Makefile` — untouched (but `db-migrate` target still shown in tech stack docs as operator path, which is correct)
- `scripts/e2e_dashboard_entrypoint.sh` — untouched ✅
- `test_agent_constraints_coverage.py` — untouched ✅ (S11 extends the coverage test for the new marker phrase — see CR-00017_S11 prompt)
- No code files modified in S09 ✅ (S09 report only mentions docs/templates changes)

### 9. Link integrity ✅

All relative links resolve to existing files. Key links checked:
- `[docs/IW_AI_Core_Agent_Constraints.md]` in all CLAUDE.md files — resolves to `docs/IW_AI_Core_Agent_Constraints.md` ✅
- `[docs/IW_AI_Core_Migration_Checklist.md]` in Migration Checklist's policy section — resolves ✅
- `[docs/IW_AI_Core_Tech_Stack.md]` in Migration Checklist — resolves ✅
- `[docs/IW_AI_Core_DB_Setup.md]` in Agent Constraints R1 section — resolves ✅

## Verification Commands Run

```bash
# Check both markers in all templates (no MISSING output)
for f in ai-dev/templates/*.md; do
  grep -q "⛔ Docker is off-limits" "$f" && \
  grep -q "⛔ Migrations: agents generate, daemon applies" "$f" || echo "MISSING: $f"
done

# Grep audit (see section 7 above)
grep -rn "alembic upgrade head" . --include="*.md" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=.venv \
  --exclude-dir=ai-dev/active

# Lint (no issues in S09-changed files)
uv run ruff check ai-dev/templates/ docs/ CLAUDE.md orch/CLAUDE.md \
  dashboard/CLAUDE.md executor/CLAUDE.md tests/CLAUDE.md
# → All checks passed
```

## Notes

- The mypy errors in `orch/daemon/merge_queue.py`, `orch/db/safe_migrate.py`, and other files are pre-existing issues from S03/S05 implementation steps, not introduced by S09. S09 only touched docs and templates.
- `tests/integration/test_agent_constraints_coverage.py` is intentionally NOT modified by S09 — the S11 tests-impl step extends the coverage test with the new MARKER_R2 phrase per the CR-00017 implementation plan.
- The `docs/misc/` files that still mention `alembic upgrade head` are internal how-to guides, not agent-facing policy documents. Their presence is acceptable.

## Verdict

**APPROVED** — S09 correctly implements the template and documentation work described in the CR-00017 design. All 9 review checklist items pass. No fixes required.