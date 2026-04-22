# CR-00015_S07_CodeReview_Final_prompt

**Work Item**: CR-00015 — Remove docker-compose db service foot-gun
**Step**: S07
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00015/CR-00015_CR_Design.md` — full design (AC1–AC7, Rollback Plan)
- All step reports: S01–S06 in `ai-dev/active/CR-00015/reports/`
- Full git diff of the branch against main
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00015/reports/CR-00015_S07_CodeReview_Final_report.md`

## Context

Final cross-layer review. Per-step reviews caught per-layer issues; you verify the system as a whole. Especially watch for: stale references to the old `docker compose up -d db` pattern hiding anywhere; inconsistency between docs; CR-00014 identity check not accidentally broken.

## Review Scope

### 1. End-to-end AC verification

Walk each AC from the design against the actual state:

- **AC1 (root `docker compose up` is a no-op)**: Run `docker compose up -d` from project root. Should produce 0 containers and 0 volumes. (Actually run this if possible — reverse with `docker compose down` which will also no-op.)
- **AC2 (worktree `docker compose up` is a no-op)**: Same from `.worktrees/F-00058/` if that worktree still exists. Should produce 0 containers. **IMPORTANT**: do not accidentally affect the live DB. Use a fresh temp worktree if F-00058 has been cleaned up.
- **AC3 (bootstrap path works on a fresh machine)**: Validate by inspection — confirm `docker-compose.bootstrap.yml` has all required fields. Do NOT actually start the bootstrap DB on this host (port conflict with live DB).
- **AC4 (`ai-core.sh db start` no-op when DB up)**: Run `./ai-core.sh db start` against the live DB. Confirm it prints "already accepting connections" and does not invoke docker.
- **AC5 (every dev-facing doc explains WHY)**: Read each of the five docs. Confirm the 2026-04-22 paragraph + pointer to `docs/IW_AI_Core_DB_Setup.md`.
- **AC6 (production path is documented as primary)**: Read `docs/IW_AI_Core_DB_Setup.md`. Confirm production section comes first and bootstrap is marked dev-only.
- **AC7 (no regression)**:
  - `make check` — all green.
  - `uv run iw db-identity show` — returns the UUID (CR-00014 still works).
  - `./ai-core.sh status` — all services healthy.
  - Dashboard at `http://localhost:9900/healthz/identity` — returns the identity payload.

### 2. Grep audit — final pass

Run the comprehensive grep:

```bash
grep -rn "docker compose up.*db\|docker-compose up.*db" . \
  --include="*.md" --include="*.sh" --include="Makefile" --include="*.yml" \
  --include="*.py" --include="*.yaml" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=node_modules \
  --exclude-dir=.venv --exclude-dir=ai-dev/active
```

Zero hits allowed (outside of CR docs themselves, which are excluded). Anything that appears must include `-f docker-compose.bootstrap.yml` — if it doesn't, flag CRITICAL.

### 3. CI / GitHub Actions

If the repo has `.github/workflows/*.yml` or any CI config that touches Docker or the DB:

- Search for any old compose invocations and update them.
- Ensure CI uses the same patterns as `ai-core.sh` or `Makefile`.
- Any CI-only test DB should be a testcontainer (not the bootstrap file).

### 4. Cross-layer consistency

- `ai-core.sh`, `Makefile`, all docs, and the new `docs/IW_AI_Core_DB_Setup.md` tell the same story.
- The exact `-f docker-compose.bootstrap.yml` spelling is used consistently (no `--file` shorthand elsewhere; no path variations).
- Project-name pinning is present in both layers: top-level `name: iw-ai-core` in the bootstrap file AND `COMPOSE_PROJECT_NAME=iw-ai-core` in `ai-core.sh`. Both kept.

### 5. CR-00014 still green

- The identity check does not regress. `uv run iw db-identity check` exits 0.
- The daemon starts without errors.
- Dashboard `/healthz/identity` serves as expected.

### 6. Rollback verification (mental test)

- Reverting the squash-merge restores the old single `docker-compose.yml` with the `db` service.
- `ai-core.sh` and `Makefile` return to calling default compose.
- Docs revert.
- No data loss; no stranded config.

### 7. Documentation discoverability

Random sanity check: if a new developer opens the repo and looks for "how do I start the DB":

- `README.md` → points to `docs/IW_AI_Core_DB_Setup.md` ✓
- `./ai-core.sh --help` → works without reading docs
- `docs/README.md` index → lists the new doc ✓

All three paths converge on the right answer in under 30 seconds.

### 8. F-00058 worktree stale copy

The `.worktrees/F-00058/` worktree contains a stale `docker-compose.yml` with the old `db` service. This is expected (worktrees are branch-scoped) and will auto-correct when F-00058 rebases. Flag in the report as "known residual; resolves on F-00058 rebase" — no action required in this CR.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Apply fixes in place (this step has edit rights). After fixes, re-run `make check` to confirm nothing regressed.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00015",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "make check: all green; CR-00014 identity check still PASS",
  "findings": [
    {"severity": "...", "file": "...", "issue": "...", "fix_applied": true|false}
  ],
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00015 --step S07
# cross-layer review + fixes ...
uv run iw step-done CR-00015 --step S07 --report ai-dev/active/CR-00015/reports/CR-00015_S07_CodeReview_Final_report.md
```
