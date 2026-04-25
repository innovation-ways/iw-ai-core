# F-00062_S11_Tests_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step**: S11
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Your tests legitimately need to spin up real docker containers (for the parallel-isolation integration test). Use **testcontainers** wherever possible — they self-clean via Ryuk. For tests that must use the production `worktree_compose.py` API, ensure they use a unique `iwcore-test-*` label prefix that the production reaper does NOT touch, AND they `try/finally` tear down the stack on test exit. Read-only `docker ps|inspect|logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You do NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Migrations inside testcontainer fixtures are fine (existing pattern in `tests/integration/conftest.py`). Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (ACs 1-10; "TDD Approach" section)
- All implementation reports S01-S10
- `tests/conftest.py` and `tests/integration/conftest.py` — testcontainer setup
- `tests/CLAUDE.md` — testing rules (no DB mocking in integration; FTS DDL after create_all)
- `orch/daemon/worktree_compose.py`, `worktree_reaper.py`, `batch_manager.py`, `safe_migrate.py`
- `ai-dev/iw-config/*` — the reference implementation

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S11_Tests_report.md`

## Context

You are writing the comprehensive test suite. Implementation steps wrote enough tests to drive their RED-GREEN cycle; this step rounds out coverage to match every AC and Invariant in the design.

## ⚠️ Semantic Correctness Warning (I003 lesson)

**Tests must verify SEMANTIC correctness, not merely that code executes without error.** A test that calls a function and asserts no exception is raised proves nothing about correctness — it only proves the function ran. Every test in this work item MUST:

1. **Assert observable, project-defined behavior** (specific values, specific state transitions, specific labels, specific log lines, specific DaemonEvent payloads — not "did not raise" or "is not None" alone).
2. **Bind the assertion to a domain rule** stated in the design's Acceptance Criteria, Invariants, or Boundary Behavior table — cite the AC/Invariant number in the test docstring.
3. **Be falsifiable** — the test must FAIL if the implementation regresses to the wrong-but-syntactically-valid behavior. As a sanity check, after writing each test, mentally (or actually) break the implementation in a plausible way and confirm the test detects the break.
4. **Avoid tautologies** — do not assert that a mocked return value equals itself, or that a value the test set is the value the test reads back. The contract under test is the production code's behavior, not the test fixture's behavior.
5. **For reaper / classification / lifecycle tests**: assert the EXACT classification string (`"orphan"`, `"stale"`, `"active"`), the EXACT count of `down()` invocations, and the EXACT DaemonEvent `phase`/`metadata` payload — never just "was called".

The I003 incident root cause was a test that asserted "ran without exception" while the underlying logic silently returned the wrong result. Do not repeat it.

## Requirements

### 1. Unit tests — `tests/unit/daemon/test_worktree_compose.py`

Audit existing tests (S03 wrote ~10) and ADD these to reach full coverage:

- `test_load_config_raises_when_iw_config_missing` (FileNotFoundError; NOT silent fallback — the legacy fallback decision is upstream of `load_config`)
- `test_has_iw_config_returns_true_when_template_present`
- `test_has_iw_config_returns_false_when_template_missing`
- `test_compose_project_name_is_lowercase_and_dash_separated` (input "CR-00022" → "iwcore-cr-00022")
- `test_render_compose_uses_strict_undefined_so_missing_var_raises`
- `test_up_emits_daemon_event_with_phase_and_success`
- `test_down_idempotent_succeeds_when_no_stack_running`
- `test_down_with_compose_path_uses_minus_f_flag`
- `test_down_without_compose_path_relies_on_project_name_only`
- `test_run_seed_no_op_when_seed_script_missing`
- `test_run_seed_no_op_when_seed_script_not_executable`
- `test_run_seed_loads_worktree_env_into_subprocess_environment`
- `test_no_secrets_in_logs` — render compose + run seed with `.env` containing `SECRET_VALUE=hunter2`; capture all logger output via `caplog`; assert "hunter2" never appears

### 2. Unit tests — `tests/unit/daemon/test_worktree_reaper.py`

Comprehensive (S05 wrote some; ensure all of these exist):

- `test_classify_running_with_active_batchitem_is_active`
- `test_classify_running_with_terminal_batchitem_is_stale` (one per terminal status: merged, archived, restarted_discarded)
- `test_classify_running_with_no_batchitem_is_orphan`
- `test_classify_with_malformed_label_is_malformed_and_reaped`
- `test_reap_only_acts_on_stale_orphan_malformed`
- `test_reap_does_not_act_on_active` (Invariant #7 — CRITICAL)
- `test_reaper_idempotent_on_already_torn_down_stack`
- `test_reaper_emits_daemon_event_per_reap_action`
- `test_reaper_uses_label_filter_in_docker_ps_call` (mock subprocess; assert the command line)
- `test_reattach_recognizes_alive_stack_and_skips_recreate`
- `test_reattach_marks_for_re_setup_when_stack_missing_and_item_non_terminal`

### 3. Unit tests — `tests/unit/test_safe_migrate.py`

(S03 extended the existing flat-convention file; ensure these all exist. **Do NOT create `tests/unit/db/` — that subdirectory is not a project convention.**)

- `test_blocks_against_orch_db_when_agent_context` (existing behavior)
- `test_allows_against_per_worktree_db_when_per_worktree_flag_set`
- `test_blocks_against_orch_db_even_with_per_worktree_flag` (Invariant #3 — CRITICAL)
- `test_url_inspection_distinguishes_orch_vs_worktree_db`
- `test_relax_inert_without_agent_context` (outside agent context, all alembic operations are already allowed; the relax flag is irrelevant)

### 4. Unit tests — `tests/unit/daemon/test_prompt_substitution.py`

(S07 wrote four; ensure they exist):

- `test_substitutes_all_known_placeholders`
- `test_unknown_placeholder_left_alone`
- `test_legacy_mode_with_no_placeholders_unchanged`
- `test_legacy_mode_with_placeholders_raises_clear_error`
- ADD: `test_substitution_handles_repeated_placeholder_in_same_prompt`

### 5. Integration test — `tests/integration/test_per_worktree_isolation.py` (AC2)

End-to-end with REAL docker (not mocks):

```python
def test_two_parallel_iw_ai_core_worktrees_do_not_interfere(tmp_path, postgres_testcontainer):
    """AC2 — two worktrees, two stacks, distinct schema changes, no cross-visibility."""
    # 1. Set up two scratch git worktrees under tmp_path, each containing
    #    a minimal iw-ai-core fixture (or use the actual repo via git worktree).
    # 2. Each gets a distinct fake BatchItem id ("F00062-TESTA", "F00062-TESTB").
    # 3. Use the actual `ai-dev/iw-config/` from the iw-ai-core repo.
    # 4. Override IW_CORE_ORCH_DB_* in the test env to point at the testcontainer
    #    (so seed.sh dumps from the testcontainer, not from real 5433).
    # 5. Call `worktree_compose.up(cfg)` for both. Assert both succeed.
    # 6. Connect `psql` to each worktree's discovered db_port; ALTER TABLE work_items
    #    ADD COLUMN col_a (in A) and col_b (in B).
    # 7. Assert worktree A's `\d work_items` shows col_a but NOT col_b.
    # 8. Assert the testcontainer (the "global orch DB" in this test) shows neither.
    # 9. try/finally: call worktree_compose.down() on both regardless.
```

Mark with `@pytest.mark.integration` and skip if `DOCKER_AVAILABLE` is False.

### 6. Integration test — `tests/integration/test_daemon_restart_reattach.py` (AC5)

```python
def test_daemon_restart_reattaches_to_running_stack(tmp_path, postgres_testcontainer):
    """AC5 — kill daemon mid-batch, restart, verify stack is re-attached and not re-up'd."""
    # 1. Set up a scratch worktree + iw-config.
    # 2. Insert a BatchItem row in the testcontainer with worktree_compose_path set.
    # 3. Bring the stack up via `worktree_compose.up()`. Assert it's alive.
    # 4. Simulate daemon restart: call the startup re-attach helper directly.
    # 5. Capture all DaemonEvent rows for this batch_item_id.
    # 6. Assert NO second `phase='up'` event was emitted (Invariant: re-attach is idempotent).
    # 7. Assert worktree_compose.is_alive() returns True.
    # 8. try/finally: down().
```

### 7. Integration test — `tests/integration/test_worktree_reaper_real_containers.py`

```python
def test_reaper_classifies_and_reaps_orphan(postgres_testcontainer):
    """AC4 — orphan container detection + reap on daemon startup."""
    # 1. Manually start a labelled container: `docker run --rm -d --label iwcore.role=worktree-db
    #    --label iwcore.batch_item=GHOST-99999 postgres:16-alpine`.
    # 2. Confirm no BatchItem row with id "GHOST-99999".
    # 3. Call `worktree_reaper.reap(db)`.
    # 4. Assert the container is gone (`docker ps --filter label=iwcore.batch_item=GHOST-99999`
    #    returns empty).
    # 5. Assert a DaemonEvent was emitted with classification='orphan'.
```

### 8. Integration test — `tests/integration/test_legacy_fallback.py` (AC7)

```python
def test_project_without_iw_config_falls_back_silently(tmp_path):
    """AC7 — quiet opt-in: no compose stack, no warning, no error."""
    # 1. Set up a scratch worktree WITHOUT iw-config.
    # 2. Call has_iw_config(worktree_path). Assert False.
    # 3. Assert no compose project named iwcore-* exists for this fake batch_item_id.
    # 4. Assert no DaemonEvent of event_type='worktree_compose' was emitted (silent).
    # 5. Capture log output; assert nothing at WARNING or ERROR level.
```

### 9. Invariant tests — `tests/integration/test_executor_docker_free.py`

```python
def test_executor_scripts_have_zero_docker_invocations():
    """Invariant #1 — executor bash scripts must not call docker."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "-E", r"\bdocker\b", "executor/"],
        capture_output=True, text=True
    )
    # Allow lines that are comments or refer to forbidden patterns
    docker_lines = [
        line for line in result.stdout.splitlines()
        if not line.strip().startswith("#")
        and "docker compose" not in line.lower() or True  # tweak as needed
    ]
    # Expectation: ZERO non-comment docker invocations in executor/
    assert result.returncode != 0 or not docker_lines, \
        f"executor/ scripts contain docker calls: {docker_lines}"
```

(Adjust the grep pattern to be precise; the goal is Invariant #1 enforcement.)

### 10. Tests — dashboard view (S09 wrote some; round out)

`tests/dashboard/test_worktrees_view.py`:

- (existing from S09) `test_worktrees_table_includes_container_status_columns`
- (existing) `test_orphan_container_appears_in_table_with_orphan_class`
- (existing) `test_force_teardown_invokes_compose_down`
- ADD: `test_legacy_worktree_row_renders_with_na_classification`
- ADD: `test_logs_stream_endpoint_caps_duration`

## Project Conventions

- Read `CLAUDE.md` and `tests/CLAUDE.md`
- NEVER mock the database in integration tests
- testcontainer fixtures via `tests/integration/conftest.py` — REPLACE `psycopg2://` with `psycopg://`
- Run FTS DDL (`FTS_FUNCTION_SQL`/`FTS_TRIGGER_SQL`) after `Base.metadata.create_all()` (existing pattern; see `tests/CLAUDE.md`)
- Mark integration tests with `@pytest.mark.integration`
- Use `try/finally` to guarantee container teardown in tests that bring up real stacks

## TDD Requirement

This step's goal is COVERAGE; you may not always need new code, just new tests. For any test exposing a missed implementation bug, file a finding in your report and stop — do NOT fix the implementation in this step (that's a fix-cycle concern).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all unit tests pass
2. `make test-integration` — all integration tests pass (this is the big one — may take minutes due to docker startup)
3. `make lint` and `make quality`
4. Verify the new tests CAN fail by temporarily breaking the implementation (sanity check that the tests actually exercise the code)

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "tests-impl",
  "work_item": "F-00062",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/daemon/test_worktree_compose.py",
    "tests/unit/daemon/test_worktree_reaper.py",
    "tests/unit/test_safe_migrate.py",
    "tests/unit/daemon/test_prompt_substitution.py",
    "tests/integration/test_per_worktree_isolation.py",
    "tests/integration/test_daemon_restart_reattach.py",
    "tests/integration/test_worktree_reaper_real_containers.py",
    "tests/integration/test_legacy_fallback.py",
    "tests/integration/test_executor_docker_free.py",
    "tests/dashboard/test_worktrees_view.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "blockers": [],
  "notes": "AC coverage map: AC1→test_X, AC2→test_Y, ..."
}
```
