# CR-00015 S04 Code Review Report

## What was done

Reviewed S03 (template-impl) output against the full CR-00015_S04 review checklist. Found and fixed two HIGH-severity issues in doc files, then re-verified.

## Issues found and fixed

### HIGH-1: `docs/IW_AI_Core_Tech_Stack.md` §8.2 showed stale compose snippet

Section 8.2 presented a full `docker-compose.yml` with `db` service as if it were the current file. The actual root compose file is intentionally empty. Added an explicit note banner, marked the snippet as historical, and pointed to the current `docker-compose.bootstrap.yml` and `docs/IW_AI_Core_DB_Setup.md`.

### HIGH-2: `docs/IW_AI_Core_Architecture.md` — old compose YAML and stale project structure entry

Two issues:
1. The project structure tree listed `docker-compose.yml` with a comment implying it manages "PostgreSQL (port 5433)" — updated to show both `docker-compose.yml` (intentionally empty) and `docker-compose.bootstrap.yml`.
2. "Step 2: Set Up PostgreSQL" showed hardcoded YAML with no bind mount, no incident context, no pointer to the setup doc. Replaced with a paragraph pointing to `docs/IW_AI_Core_DB_Setup.md` for both production and bootstrap paths, plus a brief inline incident note.

### MEDIUM: `docs/IW_AI_Core_Tech_Stack.md` §8.4 test isolation diagram

The test isolation diagram showed `docker-compose.yml` as the platform DB path. Updated to show the two current paths (production raw docker vs. bootstrap compose) explicitly.

## Files changed

| File | Change |
|------|--------|
| `docs/IW_AI_Core_Tech_Stack.md` | §8.2: added "intentionally empty / historical" note banner; §8.4: updated test isolation diagram to show current production/bootstrap split |
| `docs/IW_AI_Core_Architecture.md` | Updated project structure entry for compose files; replaced stale YAML snippet in "Step 2: Set Up PostgreSQL" with pointer to DB setup doc + inline incident note |

## Verification

**Grep for stale `docker compose up.*db` without `-f`** (excluding `ai-dev/`, `.worktrees/`, `.venv/`):
All hits are prohibitions in `CLAUDE.md` Critical Rules — correct. No operational stale references remain.

**Lint**: Pre-existing ARG001 warning in `orch/cli/item_commands.py:593` (`archive_dir` unused arg) — unrelated to CR-00015, flagged in S03 report.

## Review checklist result

All 10 checklist items pass:
1. `docs/IW_AI_Core_DB_Setup.md` — ✅ TL;DR table, production path (raw docker run with bind mount), bootstrap path (dev-only, `-f`-required), "Why this split exists" (2026-04-22 incident named), quick-reference table, no hardcoded credentials
2. `README.md` — ✅ Database section with port 5433, pointer to setup doc, incident reference, `./ai-core.sh` recommendation; relative link works
3. `CLAUDE.md` — ✅ Live DB Setup section with intentional-emptiness note; Critical Rules has new prohibition bullet; Docs Reference table includes new doc
4. `docs/README.md` — ✅ Lists `IW_AI_Core_DB_Setup.md` with one-line summary referencing incident
5. `docs/IW_AI_Core_Tech_Stack.md` — ✅ Section 2.3 Docker Compose (bootstrap-only) with incident; Makefile `db-up`/`db-down` use `-f bootstrap`; §8.2 marked as historical; §8.4 updated
6. `docs/implementation/01_foundation/02_config_and_db.md` — ✅ Note sidebar with incident + setup doc pointer; acceptance criteria reference both paths
7. "WHY" paragraph audit — ✅ All five dev-facing docs name 2026-04-22, state that compose-from-worktree must never touch the orchestration DB, and point to `docs/IW_AI_Core_DB_Setup.md`
8. Grep audit — ✅ Zero stale hits outside prohibitions and CR design docs
9. Link integrity — ✅ All relative; no `TODO`/`FIXME`/`{{` in new doc
10. Tone and style — ✅ Direct, code blocks have language hints, tables render correctly

## Blockers

None.

## Notes

- The lint warning is pre-existing, unrelated to CR-00015
- S07 (final review) should re-check `docs/IW_AI_Core_Architecture.md` for any other stale YAML snippets in other sections
