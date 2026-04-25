# F-00062_S14_CodeReview_Final_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Review Step**: S14 (Final Cross-Layer Review)
**Implementation Steps Reviewed**: S01..S13

---

## ⛔ Docker is off-limits

State-changing docker commands MUST be confined to `orch/daemon/worktree_compose.py` (the new module). Verify globally that no other code path was extended with docker calls. Read-only `docker ps|inspect|logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

The Feature relaxes safe_migrate for the per-worktree DB ONLY. Verify globally that no other code path bypasses the live-5433 protection. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc + ALL implementation reports (S01, S03, S05, S07, S09, S11, S13)
- ALL per-step code review reports (S02, S04, S06, S08, S10, S12)
- ALL files listed in all implementation reports' `files_changed`
- The new doc `docs/IW_AI_Core_Worktree_Isolation.md`
- CR-00021 design doc (`ai-dev/active/CR-00021/CR-00021_CR_Design.md` if still active, or its archive) — to verify CR-00021's merge-time rebase remains uncompromised

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S14_CodeReview_Final_report.md`

## Context

You are performing the final cross-layer review for F-00062. Per-step reviews already happened; your job is to catch what they could not — cross-cutting issues, integration failures, missed requirements traceability, regressions to existing flows (especially CR-00021 and `browser_env.py`).

## Review Checklist

### 1. Completeness vs Design Document

- Trace every section of the design through to implementation. Particularly:
  - All 10 ACs have corresponding tests AND production code (cross-check with S12's coverage map)
  - All 10 Invariants are enforced (some via runtime checks, some via tests)
  - Boundary Behavior table — every row has either a test or a documented intentional gap
  - Out-of-scope items are NOT accidentally implemented (e.g., no innoforge `iw-config/` snuck in)
- Missing requirements list (per the contract) — populate if any AC/Invariant has no implementation

### 2. Cross-agent consistency

- `worktree_compose.py` API (S03) matches what `batch_manager.py` (S05) calls
- `worktree-env.toml` schema (S07) matches what `worktree_compose.py` parses (S03)
- Placeholder substitution (S07) matches what tests verify (S11)
- Dashboard (S09) consumes `worktree_reaper.classify` (S05) correctly

### 3. Integration points

- The lifecycle from `batch_manager._setup_worktree` → `worktree_compose.up()` → first step launch is fully wired
- The lifecycle from terminal status → `worktree_compose.down()` is wired for the FULL `BatchItemStatus` terminal set: `{merged, failed, stalled, skipped, migration_invalid, migration_rolled_back, migration_rebase_failed, setup_failed}`. **`archived`/`restarted_discarded` are NOT batch-item statuses** (they belong to `BatchStatus`). Flag any code that conflates them as a CRITICAL finding.
- Daemon startup: reaper runs ONCE before the main poll loop; re-attach scan runs ONCE; periodic reaper schedules correctly
- Dashboard reads container status via the same path the reaper uses (no divergent docker queries)

### 4. CR-00021 interaction

- The pre-merge dry-run STILL uses a fresh testcontainer, NOT the per-worktree DB (Invariant #10)
- CR-00021's `migration_rebase` phase is unchanged
- `safe_migrate.dry_run` (used by CR-00021) is NOT affected by the per-worktree DB relax
- Trace CR-00021's `merge_queue._merge_item` flow and verify F-00062's hooks don't interleave incorrectly

### 5. browser_env.py regression check

- Existing `browser_verification` step lifecycle is unchanged
- `worktree_compose.py` and `browser_env.py` don't share state, ports, or labels (verify label namespaces don't collide; `iwcore.*` vs whatever browser_env uses)
- Both can coexist on the same daemon for the same project

### 6. Executor constraint preservation (Invariant #1)

- `git grep -n -E "\\bdocker\\b|\\bdocker-compose\\b|\\balembic\\b" executor/` returns ZERO non-comment hits
- Test `test_executor_docker_free.py` enforces this and passes

### 7. Security

- No secrets logged anywhere (run `git grep -n "logger\\.\\|print(" orch/daemon/worktree_compose.py` and audit each)
- `safe_migrate` relax tightly scoped (Invariant #3)
- POST handlers (force teardown, orphan teardown) follow CSRF/auth precedent
- Subprocess calls use `shell=False`, parameter lists, timeouts everywhere

### 8. Testing (holistic)

- `make test-unit` passes
- `make test-integration` passes (this is the big test — real docker, may take minutes)
- `make lint`, `make quality` pass
- The two parallel-isolation integration test (AC2) actually demonstrates schema separation via `psql`, not just ORM mocks
- The legacy fallback test (AC7) demonstrates byte-identical behavior to pre-Feature

### 9. Documentation

- New doc `docs/IW_AI_Core_Worktree_Isolation.md` exists, accurate, and links resolve
- `CLAUDE.md` Quick Navigation row added
- `CLAUDE.md` Critical Rules updated for `.env` / `.iw/` enforcement
- `orch/CLAUDE.md` Daemon Modules table includes the new module(s)
- `tests/CLAUDE.md` clarifies per-worktree DB vs testcontainers
- `executor/CLAUDE.md` clarifies compose ownership
- `docs/IW_AI_Core_Agent_Constraints.md` documents the safe_migrate exception

### 10. iw-ai-core reference implementation correctness

- Render `ai-dev/iw-config/worktree-compose.template.yml` manually with sample vars; verify YAML
- `bash -n ai-dev/iw-config/worktree-seed.sh` returns 0
- `python -c "import tomllib; tomllib.loads(open('ai-dev/iw-config/worktree-env.toml').read())"` succeeds
- Seed script's `pg_dump` source URL uses `IW_CORE_ORCH_DB_*` (not the per-worktree DB — that would be a cycle)
- The dashboard module path in the compose template (`dashboard.main:app`) matches actual iw-ai-core source

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make lint` and `make quality` — pass
4. Trace at least three end-to-end paths by hand:
   - Setup happy path: project with iw-config → up succeeds → ports persisted → first step launches with placeholders substituted
   - Setup failure path: seed.sh exits 1 → stack torn down → setup_failed → DaemonEvent
   - Daemon restart path: kill daemon, restart, verify re-attach via worktree_compose_path

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | AC unimplemented; Invariant violated; safe_migrate relax weakens 5433 protection; CR-00021 broken; secrets in logs |
| HIGH | Cross-agent integration bug; missing terminal-state teardown; reaper false-positive risk; legacy fallback broken |
| MEDIUM_FIXABLE | Doc inconsistency; missing CLAUDE.md update; weak test |
| MEDIUM_SUGGESTION | Refactor opportunity; clearer boundary |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S14",
  "agent": "code-review-final-impl",
  "work_item": "F-00062",
  "steps_reviewed": ["S01","S03","S05","S07","S09","S11","S13"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "...",
      "category": "completeness|consistency|integration|cr_00021_interaction|security|testing|documentation",
      "file": "...",
      "line": 42,
      "description": "...",
      "suggestion": "...",
      "cross_cutting": true
    }
  ],
  "ac_coverage_complete": true,
  "invariants_enforced": true,
  "cr_00021_unaffected": true,
  "browser_env_unaffected": true,
  "executor_docker_free": true,
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
