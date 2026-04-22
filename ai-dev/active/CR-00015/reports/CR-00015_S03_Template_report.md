# CR-00015 S03 Template Report

## What was done

Documentation pass for CR-00015 — updated all developer-facing docs to reflect the compose-file split and to explain WHY the split exists (the 2026-04-22 data-loss incident).

## Files changed

| File | Change |
|------|--------|
| `docs/IW_AI_Core_DB_Setup.md` | **New** — single source of truth for DB setup. Sections: TL;DR table, production path (raw `docker run` with bind mount), bootstrap path (dev only), "Why this split exists" (incident narrative), quick-reference command table. |
| `README.md` | Rewrote entirely. Added Database section explaining the two paths, pointing to `docs/IW_AI_Core_DB_Setup.md`, and referencing the 2026-04-22 incident. |
| `CLAUDE.md` | Replaced Critical Rules bullet (now uses `./ai-core.sh db start` instead of the full docker prohibition list). Replaced "Live DB Setup" section (intentionally empty compose file explanation + incident pointer). Added `IW_AI_Core_DB_Setup.md` to Docs Reference table. |
| `docs/README.md` | Added `IW_AI_Core_DB_Setup.md` entry with description referencing the 2026-04-22 incident. |
| `docs/IW_AI_Core_Tech_Stack.md` | Renumbered sections (old 2.3 Dashboard → 2.4; new 2.3 is "Docker Compose — Bootstrap Only"). Added explanation of the split + incident pointer. Updated Makefile `db-up`/`db-down` targets to use `-f docker-compose.bootstrap.yml`. |
| `docs/implementation/01_foundation/02_config_and_db.md` | Added note sidebar explaining the bootstrap file split and incident. Updated acceptance criteria to reference `./ai-core.sh db start` (bootstrap) and `docs/IW_AI_Core_DB_Setup.md` (production). |

## Verification

**`make lint`**: Pre-existing ARG001 warning in `orch/cli/item_commands.py:593` (unused `archive_dir` arg) — not touched by this CR, unrelated to CR-00015.

**Grep for stale references** (excluding `.worktrees/`, `ai-dev/active/CR-00015/`, `.venv/`):
- Zero stale `docker compose up.*db` references in any doc, script, Makefile, or compose file outside the CR's own directory.
- The two hits in `./CLAUDE.md` (lines 33, 55) are prohibitions — they now explicitly forbid the old pattern rather than describing it. These are the updated Critical Rules and Live DB Setup sections, both correct.

**Human read-through**: `docs/IW_AI_Core_DB_Setup.md` covers TL;DR table, production path (with bind mount command), bootstrap path (with warning banner), incident narrative, and quick-reference command table. A new dev can follow it end-to-end.

## Acceptance criteria check

- AC5 (docs explain WHY): All five files (README.md, CLAUDE.md, docs/README.md, docs/IW_AI_Core_Tech_Stack.md, docs/implementation/01_foundation/02_config_and_db.md) now contain a short paragraph naming the 2026-04-22 incident and pointing to `docs/IW_AI_Core_DB_Setup.md`.
- AC6 (production path primary): `docs/IW_AI_Core_DB_Setup.md` opens with the Production path (raw `docker run` with bind mount), then Bootstrap (dev-only) with a clear warning banner. No hardcoded credentials.

## Blockers

None.

## Notes

- The lint warning is pre-existing and unrelated. S01 report flagged it.
- `ai-dev/active/CR-00015/` is excluded from the grep as specified (those files discuss the old pattern for context and are allowed to).