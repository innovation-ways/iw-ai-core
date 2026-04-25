# F-00062_S12_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## ⛔ Docker is off-limits

Test code legitimately uses real docker (testcontainers + the parallel-isolation integration test). Verify each test that brings up a stack has try/finally teardown and uses unique label prefixes that the production reaper doesn't claim. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Test migrations run inside testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (full AC + Invariant matrix), S01-S11 reports
- All test files in S11's `files_changed`

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S12_CodeReview_report.md`

## Context

You are reviewing the test suite for completeness and correctness. The most critical thing is the AC coverage map: every AC1-10 must be exercised by at least one test, and every Invariant 1-10 must be assertable from at least one test.

## Review Checklist

### 1. AC coverage map (10 ACs)

For each AC1-AC10 in the design, identify which test exercises it. Required mapping:

| AC | Test |
|----|------|
| AC1 | `test_per_worktree_isolation` (setup phase) + `test_worktree_compose.test_up_emits_daemon_event_with_phase_and_success` |
| AC2 | `test_per_worktree_isolation::test_two_parallel_iw_ai_core_worktrees_do_not_interfere` |
| AC3 | `test_safe_migrate::*` (3 tests) |
| AC4 | `test_worktree_reaper_real_containers::test_reaper_classifies_and_reaps_orphan` |
| AC5 | `test_daemon_restart_reattach::test_daemon_restart_reattaches_to_running_stack` |
| AC6 | `test_worktree_compose::test_run_seed_nonzero_exit_returns_failure_with_stderr_tail` + integration |
| AC7 | `test_legacy_fallback::test_project_without_iw_config_falls_back_silently` |
| AC8 | `test_worktree_compose::test_assert_gitignore_safe_*` |
| AC9 | `test_prompt_substitution::*` |
| AC10 | `test_worktrees_view::*` |

If any AC has no test mapping → CRITICAL finding.

### 2. Invariant coverage (10 invariants)

| Invariant | Verification |
|-----------|--------------|
| #1 (executor docker-free) | `test_executor_docker_free.py` |
| #2 (only worktree_compose calls docker compose up/down) | static grep test or manual review |
| #3 (orch DB protection) | `test_safe_migrate::test_blocks_against_orch_db_even_with_per_worktree_flag` |
| #4 (deterministic naming) | `test_worktree_compose::test_compose_project_name_is_lowercase_and_dash_separated` |
| #5 (label invariant) | `test_per_worktree_isolation` checks labels post-up |
| #6 (all-NULL or all-set) | tested implicitly by lifecycle test; document explicitly |
| #7 (reaper never touches active) | `test_worktree_reaper::test_reap_does_not_act_on_active` (CRITICAL) |
| #8 (no secrets in logs) | `test_worktree_compose::test_no_secrets_in_logs` |
| #9 (legacy byte-identical) | `test_legacy_fallback::*` |
| #10 (CR-00021 still uses testcontainer) | tracing test or manual verification — flag if missing |

### 3. Test isolation
- Every test that brings up a real docker stack uses `try/finally` teardown
- Tests use a unique `iwcore-test-*` prefix that the production reaper does NOT match (the production reaper filters on `iwcore.role=worktree-db|worktree-app` — verify your test labels distinguish themselves OR you mock `worktree_reaper` in unit tests)
- Tests do NOT modify the live orch DB on 5433 (testcontainer only — `tests/CLAUDE.md` rule)
- Tests do NOT modify the iw-ai-core repo's `ai-dev/iw-config/` files (read-only consumption)

### 4. Test correctness
- Tests CAN fail (sanity check by mentally injecting a regression — e.g., would removing the safe_migrate relax cause a test to fail?)
- Mocks are tight: `subprocess.run` mocked at the right boundary; not over-mocked
- Integration tests skip cleanly when docker is unavailable (don't hang / silently pass)
- Boundary scenarios from the design's Boundary Behavior table have tests (audit each row)

### 5. Performance
- Integration tests don't run for >2 minutes each
- Real-docker tests bring up the absolute minimum (alpine image, no fixtures unless required)

### 6. Project conventions
- Read `CLAUDE.md` and `tests/CLAUDE.md`
- `psycopg2://` → `psycopg://` substitution where testcontainers are used
- FTS DDL after `create_all()`
- `@pytest.mark.integration` on integration tests
- Test names describe what they verify

### 7. Make targets pass
- `make test-unit` (all unit pass)
- `make test-integration` (all integration pass — including docker-real tests)
- `make lint` and `make quality`

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — all pass
2. Run `make test-integration` — all pass (this WILL spin up real docker; may take minutes)
3. Pick ONE integration test and trace its setup/teardown by hand to verify it actually exercises production code (not just mocks)

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | AC has no test; Invariant has no enforcement; integration test mocks the database; test pollutes live 5433 |
| HIGH | Missing try/finally on real-docker test; test prefix collides with production label; test that "passes" because of an over-broad mock |
| MEDIUM_FIXABLE | Boundary row not covered; test name unclear; missing pytest mark |
| MEDIUM_SUGGESTION | Better fixture organization |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S12",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S11",
  "verdict": "pass|fail",
  "findings": [...],
  "ac_coverage_map": {"AC1": "...", "AC2": "...", ...},
  "invariant_coverage_map": {"INV1": "...", ...},
  "missing_coverage": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "notes": ""
}
```
