# I-00062 S07 Code Review — Final Cross-Agent Review

## What Was Reviewed

Global cross-agent review of the complete I-00062 fix package, covering:
- **S01** (database-impl): 4 new columns + alembic migration
- **S03** (backend-impl): 3-layer defense (snapshot+strip, injection, fail-fast)
- **S05** (tests-impl): 20 tests across 4 new test files + 1 updated pre-existing test
- All per-agent code reviews (S02, S04, S06)

## Pre-Review Lint & Format Gate

| Check | Result |
|-------|--------|
| `make lint` | 8 errors — all in `scripts/arch_check.py` (pre-existing, unrelated to I-00062) |
| `make format` | Clean — 567 files formatted |

**Verdict**: No new lint/format violations introduced by I-00062 changes.

## End-to-End Isolation Guarantee (Checklist §1)

### (1) Compose-stack case — per-worktree DB, NOT 5433 ✅

- `_agent_subprocess_env()` snapshots daemon's `IW_CORE_DB_*` → `IW_CORE_ORCH_DB_*` via `setdefault` (line 1511–1522)
- All 5 `IW_CORE_DB_*` keys stripped (line 1530–1537)
- `_launch_step` injects all 5 vars from `worktree_info` columns (lines 1163–1168) which are populated from `UpResult.discovered_db_credentials` at compose-up (batch_manager.py:604–609)
- `IW_CORE_ORCH_DB_PORT` set to daemon's 5433 (snapshot), NOT overwritten by injection block

### (2) No-compose legacy case — no `IW_CORE_DB_*` inherited ✅

- Strip removes all 5 `IW_CORE_DB_*` keys from env
- `IW_CORE_ORCH_DB_PORT` snapshotted via Layer 1's `setdefault` loop
- If `.env` mirrors main (`IW_CORE_DB_PORT=5433`), `load_dotenv(override=False)` does NOT overwrite the stripped value; but Layer 3 fires because `IW_CORE_ORCH_DB_PORT` is set

### (3) Browser-verification case — bv_env wins, ORCH preserved ✅

- `_agent_subprocess_env()` runs first, then `{**agent_env, **bv_env}` merge (line 1151–1153)
- Snapshot uses `setdefault` — won't clobber existing `IW_CORE_ORCH_DB_*` from `bv_env`
- Injection block runs AFTER merge, so bv-injected DB vars are NOT overwritten

### (4) Legacy worktree with `.env` mirroring main — Layer 3 fires ✅

- `test_legacy_worktree_with_inherited_orch_port_raises` covers this scenario (fails pre-fix twice — no snapshot, no guard — passes post-fix)
- Guard: `IW_CORE_AGENT_CONTEXT=true` AND `IW_CORE_ORCH_DB_PORT` set AND `IW_CORE_DB_PORT == IW_CORE_ORCH_DB_PORT` → RuntimeError

## AC Coverage Check (Checklist §2)

| AC | Implementation | Test | Status |
|----|----------------|------|--------|
| AC1 | `_launch_step` injection block (bm:1163–1168) | `test_compose_stack_injects_all_five_db_vars` — asserts exact port 36216, not 5433 | ✅ |
| AC2 | `_agent_subprocess_env` snapshot+strip (bm:1511–1537) | `test_snapshots_orch_creds_before_strip` + `test_strips_inherited_orch_db_vars` — exact value assertions | ✅ |
| AC3 | `orch/config.py` guard (config:55–66) | `test_agent_context_with_orch_port_raises` + `test_legacy_worktree_with_inherited_orch_port_raises` + `test_runbook_string_in_error_message` | ✅ |
| AC4 | Reproduction tests | All 4 test files | ✅ |
| AC5 | Migration `4cc043748e92` adds 4 nullable TEXT columns | `test_upgrade_adds_four_columns` + downgrade round-trip | ✅ |
| AC6 | `bv_env` merge ordering (bm:1151–1153) | `test_bv_env_overrides_strip` — asserts exact e2e port "39999" | ✅ |

All 6 ACs have both a concrete implementation and a semantic test assertion.

## Migration / Merge Pipeline (Checklist §3) ✅

- `down_revision` of `4cc043748e92` is `4876b3246ff2` (confirmed via `alembic history --verbose`)
- `e53ce8e86a3c` (F-00077's migration) is NOT present in the migration tree — confirmed "NOT FOUND" via grep
- No `alembic upgrade head` or `make db-migrate` against live DB in any agent report
- Migration will be applied by `migration_pipeline.run_post_merge_apply` after I-00062 merges

## Cross-Agent Consistency (Checklist §4) ✅

- `worktree_compose.UpResult.discovered_db_credentials` is consumed only in `batch_manager.py:605–609` (compose-up success path) and `batch_manager.py:829` (passed to `_launch_step` via `worktree_info`)
- `worktree_db_*` columns read only in `_launch_step` (bm:1158–1162) and at compose-up persistence (bm:604–609)
- Fail-fast guard in `orch/config.py` only applies when `IW_CORE_AGENT_CONTEXT=true` — daemon/dashboard run with that var unset
- `get_orch_db_url()` does NOT call the guard — confirmed at config.py:80–97

## Test Pre-Fix vs Post-Fix Verification (Checklist §5) ✅

Key tests that would fail pre-fix:
- `test_strips_inherited_orch_db_vars` — env leaks 5433 pre-fix; strip removes it post-fix
- `test_snapshots_orch_creds_before_strip` — no snapshot pre-fix; `IW_CORE_ORCH_DB_PORT` unset → assertion fails pre-fix
- `test_compose_stack_injects_all_five_db_vars` — no injection pre-fix; env has 5433 → assertion `== "36216"` fails pre-fix
- `test_agent_context_with_orch_port_raises` — no guard pre-fix; no exception → assertion fails pre-fix
- `test_legacy_worktree_with_inherited_orch_port_raises` — fails pre-fix twice (no snapshot AND no guard)

All tests verified semantically correct (exact value assertions, not shape-only).

## Security & Secrets (Checklist §6) ✅

- `RuntimeError` in `_launch_step` (bm:1174–1180) reports booleans only (presence flags: `host=bool(...)`, etc.) — no credentials
- `RuntimeError` in `orch/config.py` runbook string references I-00062 runbook path — no port, no password
- `worktree_db_password` stores dev credentials from `worktree-seed.sh` (dev-only, pre-existing pattern)

## Backward Compatibility (Checklist §7) ✅

- Design doc Notes section (I-00062_Issue_Design.md:446–454) documents the deployment runbook for in-flight items with `worktree_compose_path IS NOT NULL AND worktree_db_host IS NULL`
- F-00077 is the only known affected item; will be re-launched fresh post-merge
- Items WITHOUT `ai-dev/iw-config/` have all 4 columns NULL; strip removes inherited `IW_CORE_DB_*`; Layer 3 fires if `.env` mirrors main — correct behavior (fail rather than silently hit 5433)

## Functional Doc Accuracy (Checklist §8) ✅

`I-00062_Functional.md` accurately describes post-fix behavior:
- "orchestration database stays at the head matching the merged code base" — correct
- "migrations landing in the right place automatically" for compose-stack Features — correct
- Safety net for legacy worktrees — correct ("refuses to boot and prints a one-line error referencing this incident")
- No file paths, class names, or implementation details leaked into operator-facing doc

## Test Suite Results

| Suite | Result |
|-------|--------|
| `make test-unit` | 2500 passed, 2 skipped, 5 xfailed, 1 xpassed ✅ |
| `make test-integration` | 1662 passed, 6 failed, 6 errors (pre-existing failures in F-00055, SSE wiring, impacted_paths backfill — all unrelated to I-00062) |
| I-00062-specific tests | 20 passed, 0 failed ✅ |

Pre-existing integration failures (all unrelated to I-00062):
- `test_migration_impacted_paths_backfill` — F-00055 workflow fixture
- `test_f00055_workflow_fixture` (6 errors/failures) — F-00055 workflow fixture
- `test_chat_templates` — CSS variable definition
- `test_sse_client_wiring` (2 failures) — SSE handler registration
- `test_impacted_paths_backfill_idempotent` (2 errors) — impacted paths backfill

## Findings

No CRITICAL, HIGH, or MEDIUM (fixable) findings.

### Observations (Non-Blocking)

1. **Lint errors in `scripts/arch_check.py`**: 8 pre-existing T201/T203 violations in an unrelated file — 0 new violations introduced by I-00062.

2. **S02 review noted**: S01 report lacked testcontainer migration round-trip evidence. S05 `test_i_00062_migration.py` provides this evidence with full upgrade+downgrade+idempotent+re-upgrade coverage. The structural correctness of the migration was never in doubt; the round-trip evidence simply appears in S05 rather than S01, which is the appropriate step for it.

3. **S06 review noted**: Format fix was applied during S06 review to `test_launch_step_env_isolation.py` (line length). All 4 new test files are now clean on `make lint` and `make format`.

4. **Migration hardcoding in test**: `test_i_00062_migration.py` hardcodes `MIGRATION_REV = "4cc043748e92"` and `PREV_REVISION = "4876b3246ff2"`. If a rebase adds migrations between PREV_REVISION and I-00062 before merge, the test would fail. However, the daemon's migration pipeline handles rebase ordering at merge time, and this is standard project practice (same pattern in `test_migration_impacted_paths_backfill.py`).

---

## Verdict

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "I-00062",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2500 unit passed (make test-unit), 1662 integration passed, 6 pre-existing failures + 6 pre-existing errors (none related to I-00062), 20 I-00062-specific tests all passed",
  "missing_requirements": [],
  "notes": "All 6 ACs verified. End-to-end isolation guarantee confirmed for compose-stack, legacy, and browser-verification paths. Migration chain clean (4cc043748e92 at head, down_revision=4876b3246ff2, e53ce8e86a3c not present). No live-DB writes. No credential exposure in error messages. Deployment runbook documented in design doc Notes. Functional doc accurately describes operator-observable behavior. Pre-existing integration test failures are unrelated to I-00062 (F-00055 fixture, SSE wiring, impacted_paths)."
}
```