# CR-00015_S04_CodeReview_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step Being Reviewed**: S03 (template-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md`
- `ai-dev/active/CR-00015/reports/CR-00015_S03_Template_report.md`
- All doc files listed in the S03 report's `files_changed`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S04_CodeReview_report.md`

## Review Checklist

### 1. `docs/IW_AI_Core_DB_Setup.md` completeness

- File exists at `docs/IW_AI_Core_DB_Setup.md`.
- TL;DR header table at the top showing the two paths (production vs. bootstrap).
- Production path has the exact `docker run` command with bind mount to `/opt/postgres/data`, environment variables from `.env`, and `PGDATA=/var/lib/postgresql/data/pgdata`.
- Bootstrap path has the `-f docker-compose.bootstrap.yml` invocation and is clearly labeled "dev only — throwaway".
- "Why this split exists" section names the 2026-04-22 incident, explains the cwd-basename-as-project-name trap, and references CR-00014 + CR-00015.
- Quick-reference table at the end for common ops (`./ai-core.sh` commands).
- No hardcoded credentials. All sensitive values pulled from `.env` via env-var references.
- A new reader could follow either path end-to-end without additional context.

### 2. `README.md`

- Has a Database section (or the existing one is updated).
- Contains: port 5433 fact, pointer to `docs/IW_AI_Core_DB_Setup.md`, incident reference, `./ai-core.sh` recommendation.
- Did NOT break other README sections.
- Relative link to `docs/IW_AI_Core_DB_Setup.md` works.

### 3. `CLAUDE.md` (top-level)

- **Live DB Setup** section updated with the intentional-emptiness note + pointer to new doc.
- **Critical Rules** list has a NEW bullet forbidding `docker compose up ... db` outside `./ai-core.sh`.
- Existing rules preserved in order.

### 4. `docs/README.md`

- `IW_AI_Core_DB_Setup.md` listed in the appropriate group.
- One-line summary accompanies the entry.

### 5. `docs/IW_AI_Core_Tech_Stack.md`

- Any `docker compose up -d db` reference replaced with the `-f` form OR a pointer to the new setup doc.
- Brief "production = raw docker run; dev bootstrap = compose -f" distinction noted.

### 6. `docs/implementation/01_foundation/02_config_and_db.md`

- Step-by-step guide updated: commands are current.
- Short sidebar or note points to `docs/IW_AI_Core_DB_Setup.md`.

### 7. The "WHY" paragraph audit

For each of the five dev-facing docs (`README.md`, `CLAUDE.md`, `docs/README.md`, `docs/IW_AI_Core_Tech_Stack.md`, `docs/implementation/01_foundation/02_config_and_db.md`), confirm:

- Mentions the 2026-04-22 incident (date OR "recent data-loss incident" phrasing).
- States that `docker compose up` from a worktree must never touch the orchestration DB.
- Points to `docs/IW_AI_Core_DB_Setup.md`.

Missing any of the three in any of the five docs → HIGH severity.

### 8. Grep audit — no stale references

Re-run the grep from the S03 prompt §7. Zero hits of `docker compose up` or `docker-compose up` targeting `db` without `-f docker-compose.bootstrap.yml`.

If any stale references remain (e.g., inside code comments, CI workflows, scripts), flag them for S03 to address.

### 9. Link integrity

- Every cross-document link uses a relative path.
- Every link target exists.
- No `TODO` / `FIXME` / placeholder `{{...}}` left in the new file.

### 10. Tone and style

- Matches the existing docs' voice (direct, no marketing fluff).
- Code blocks have language hints (`bash`, `yaml`, `markdown`).
- Tables render properly (column alignment, pipe escaping where needed).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place. After fixes, re-run the grep audit.

## Subagent Result Contract

Same pattern as prior S02/S04 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S04
# review + fix ...
uv run iw step-done CR-00015 --step S04 --report ai-dev/active/CR-00015/reports/CR-00015_S04_CodeReview_report.md
```
