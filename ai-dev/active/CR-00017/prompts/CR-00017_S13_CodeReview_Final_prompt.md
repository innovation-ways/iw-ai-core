# CR-00017_S13_CodeReview_Final_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S13
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md` — full design
- All step reports S01–S12 in `ai-dev/active/CR-00017/reports/`
- Full git diff of the branch against main
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S13_CodeReview_Final_report.md`

## Context

This is the largest CR in the 2026-04-22 defense sequence. Final cross-layer review verifies the system as a whole, confirms compatibility with CR-00014, CR-00015, CR-00016, and validates that the rollback plan is sound.

## Review Scope

### 1. AC verification (walk all 10)

For each AC in the design doc, trace the implementation + test:

- **AC1** (agent-context guard): grep for `AgentContextForbidden` across codebase; confirm guard is exercised in safe_migrate + both CLIs + daemon agent spawn tests.
- **AC2** (dry-run rejects broken migration): integration test present and green.
- **AC3** (happy-path apply): integration test present and green. `iw_core_instance.instance_id` (CR-00014) still matches after a test apply.
- **AC4** (rollback paths): both success and failure paths covered.
- **AC5** (frozen queue): freeze/unfreeze round-trip + agent refusal.
- **AC6** (multi-head): detection → rejection → clear message.
- **AC7** (CLI exit codes): every code 0/1/2/3/4/5 has a test.
- **AC8** (prompt templates): coverage test extended with R2; every template carries both markers.
- **AC9** (observability): `pending_migration_log` populated; `daemon_events` entries; dashboard banner for frozen; `ai-core.sh status` line.
- **AC10** (no regression): `make check` green; CR-00014 identity check green; CR-00015 compose-split test green; CR-00016 coverage test (original R1) still passing.

### 2. Defense-in-depth layering

Confirm the layered defenses still stack correctly:

- CR-00014 identity check catches DB-swap — still fires.
- CR-00015 compose split — unchanged.
- CR-00016 Docker rule — R1 intact; tests still enforce.
- CR-00017 R2 (Migrations) — new layer; agents refuse to apply; daemon gates with 3-phase pipeline.

All four layers together mean: to cause a 2026-04-22-class incident post-CR-00017, an attacker would need to (a) bypass R1 (run docker commands) AND (b) bypass R2 (run alembic upgrade against live DB) AND (c) match the expected instance UUID from CR-00014 (near-impossible to forge) AND (d) evade the daemon's freeze logic. Deep defense.

### 3. Rollback sanity

Mental walk-through:

- Revert the squash-merge.
- `pending_migration_log` table remains but is inert (no code reads it).
- `daemon_events` with `event_type='merge_queue_frozen'` remain but are inert.
- Daemon returns to no-migration-hook behavior; agents can apply migrations again (regression, but the pre-CR-00017 state).
- Prompt templates revert to pre-CR-00017 versions.
- Coverage test reverts to R1-only.
- No data loss.

If operator needs to roll back and the queue is currently frozen: the revert restores the pre-CR-00017 behavior where no such concept exists; document in the report that operators should unfreeze BEFORE reverting (clean shutdown) to avoid confusing state.

### 4. CR-00014/15/16 still green

Run (or confirm the coverage test, identity check, compose-config check):

```bash
uv run iw db-identity check                            # CR-00014 green
docker compose config                                  # CR-00015: no services
docker compose -f docker-compose.bootstrap.yml config  # CR-00015: db present
pytest tests/integration/test_agent_constraints_coverage.py  # CR-00016 + CR-00017
./ai-core.sh status                                    # full green
```

### 5. Grep audit — no stale agent-facing `alembic upgrade head`

```bash
grep -rn "alembic upgrade head" . \
  --include="*.md" --include="*.py" --include="*.sh" --include="Makefile" \
  --exclude-dir=.git --exclude-dir=.worktrees --exclude-dir=.venv \
  --exclude-dir=ai-dev/active --exclude-dir=node_modules
```

Allowed hits: operator-paths only (`ai-core.sh`, `Makefile`, `scripts/e2e_dashboard_entrypoint.sh`, `docs/IW_AI_Core_DB_Setup.md`'s operator sections). Any agent-facing hit → CRITICAL.

### 6. Dashboard banner

If S05 added a dashboard banner for `merge_queue_frozen=true`: confirm it renders when the flag is set, disappears when unfrozen, does not break the existing dashboard layout, and is accessible (no `aria-hidden` shenanigans).

### 7. F-00058 impact documented

S13 report must note: "F-00058 S01 prompt is incompatible with CR-00017; needs re-prompting when that work item resumes." Also confirm no other in-flight work item has the same issue — grep `ai-dev/active/*/prompts/*.md` for `alembic upgrade head`.

### 8. Operator runbook sanity

Someone new to the system opens `docs/IW_AI_Core_Migration_Checklist.md`. Can they:
- Understand what changed? ✓
- Know what to do when the queue is frozen? ✓
- Know the right CLI to resume? ✓
- Know where to find the underlying `pending_migration_log` entries? ✓

If any answer is No → MEDIUM severity.

### 9. Sibling-repo propagation list

Extend CR-00016's propagation list with CR-00017 additions:
- `docs/IW_AI_Core_Agent_Constraints.md` (now has R1 + R2).
- Updated prompt templates (both markers).
- Updated CLAUDE.md files (both bullets).
- `docs/IW_AI_Core_Migration_Checklist.md` (rewritten).

Document for operator follow-up sync to IW-AI-DEV and InnoForge.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW. Fix in place where possible. Large structural issues → blocker for orchestrator.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "code-review-final-impl",
  "work_item": "CR-00017",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "make check green; all 10 ACs covered; CR-00014/15/16 intact",
  "findings": [
    {"severity": "...", "file": "...", "issue": "...", "fix_applied": true|false}
  ],
  "sibling_repo_sync_list": [...],
  "blockers": [],
  "notes": "F-00058 S01 prompt needs re-authoring when resumed."
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S13
uv run iw step-done CR-00017 --step S13 --report ai-dev/active/CR-00017/reports/CR-00017_S13_CodeReview_Final_report.md
```
