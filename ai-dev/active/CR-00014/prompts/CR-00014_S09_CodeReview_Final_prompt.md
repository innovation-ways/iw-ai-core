# CR-00014_S09_CodeReview_Final_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step**: S09
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — full design (AC1–AC6, Rollback Plan, Notes)
- All step reports: S01–S08 in `ai-dev/active/CR-00014/reports/`
- Full git diff of the branch against main
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S09_CodeReview_Final_report.md`

## Context

You are the final cross-layer review. Per-agent reviews caught per-layer issues; you must verify the system as a whole. Look for integration gaps between layers, AC coverage drift, and regressions on paths the per-step reviews didn't touch.

## Review Scope

### 1. End-to-end AC verification

Walk each acceptance criterion from the design doc against the actual code:

- **AC1 (match → green)**: Trace match path through daemon startup, dashboard lifespan, `/healthz/identity`, `ai-core.sh status`. All four paths agree.
- **AC2 (mismatch → refuse)**: Daemon raises and exits, dashboard lifespan raises and aborts startup, endpoint returns 503, `ai-core.sh status` prints FAIL line. No path silently proceeds.
- **AC3 (bootstrap)**: Single INFO line per process (not per request, not per poll). Dashboard serves normally, daemon enters main loop, status prints UNVERIFIED.
- **AC4 (missing row with env set)**: Hard fail from daemon and dashboard. Error message mentions "row missing" and the expected UUID.
- **AC5 (migration reversible)**: Downgrade drops table. Upgrade re-creates with a fresh UUID. Round-trip test present and passing.
- **AC6 (no regressions)**: `make check` stays green. No unrelated test failures.

### 2. Cross-layer consistency

- The error block text is the same across daemon, dashboard, and CLI. A user who sees it from any process gets the same remediation.
- The `IdentityStatus.mode` values (`match`, `mismatch`, `bootstrap`, `missing`) are referenced consistently — no drift where one layer uses `unmatched` or `absent`.
- Exit codes from `iw db-identity check` (0/2/3/1) are consumed correctly by `ai-core.sh`. The bash expects them exactly as the CLI emits them.
- The JSON shape from `/healthz/identity` matches what external monitoring would expect — if there's any existing `/healthz` route, the new one looks idiomatic beside it.

### 3. Integration with the incident-recovery flow

- If someone applies CR-00014 *today* against the real DB (alembic rev `824e6e6f34ee` + one new revision), the bootstrap path works: daemon comes up, logs the UUID, user pastes into `.env`, restarts — mismatch-hard-fail goes live. No step requires downtime or manual SQL.
- If someone restores from the `backup_260422` backup (dumpall or custom format), the restored DB contains the same `iw_core_instance` row → same UUID → matches the expected env → works seamlessly.
- If F-00058 has been re-run and its migration landed, the alembic chain is linear (F-00058's `e5f98332f308` → this CR's new revision, or vice versa — whichever merges first). Check the `down_revision` chain in the final state.

### 4. Regression surface

- Daemon startup health check: still verifies connectivity and still logs "Database connection verified" — the identity check is *added*, not replacing.
- Dashboard routes: full route list (`uv run python -c 'from dashboard.app import create_app; [print(r.path) for r in create_app().routes]'`) matches main + `/healthz/identity`.
- `ai-core.sh status` still shows all its existing lines — identity line is inserted, nothing replaced.
- No new dependencies in `pyproject.toml` / `uv.lock` unless essential.

### 5. Documentation

- `.env.example` updated with the new var.
- If `dashboard/CLAUDE.md` gained a Health endpoints section, it reads well.
- If any top-level `CLAUDE.md` rule changed, changes are called out.
- Design doc's `Status` field is still `Draft` or `In Progress` — the next lifecycle event (squash-merge) will set it to Done.

### 6. Rollback verification (mental test)

Walk through the Rollback Plan:

- `alembic downgrade -1` drops `iw_core_instance` cleanly — no cascading breakage.
- Reverting the squash-merge returns daemon/dashboard/ai-core.sh to pre-CR behavior — no stranded env var references.
- Removing `IW_CORE_EXPECTED_INSTANCE_ID` from `.env` is safe (bootstrap mode).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Apply fixes in place (this step has edit rights). After fixes, re-run `make check` to confirm nothing regressed.

If a CRITICAL or HIGH issue cannot be fixed in this step (requires significant rework), raise it as a blocker for the orchestrator.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-final-impl",
  "work_item": "CR-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "make check: all green",
  "findings": [
    {"severity": "...", "file": "...", "issue": "...", "fix_applied": true|false}
  ],
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S09
# cross-layer review + fixes ...
uv run iw step-done CR-00014 --step S09 --report ai-dev/active/CR-00014/reports/CR-00014_S09_CodeReview_Final_report.md
```
