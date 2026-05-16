# F-00084_S06_Tests_prompt

**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Step**: S06
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in `tests/integration/conftest.py` are exempt. Use the existing testcontainer Postgres fixture for integration tests — do NOT spin up new docker resources.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step writes NO migration files.

## Input Files

- Runtime step state: `uv run iw item-status F-00084 --json`
- Design doc: `ai-dev/active/F-00084/F-00084_Feature_Design.md` — Acceptance Criteria, Boundary Behavior, Invariants
- Canonical reference: `docs/research/R-00076-llm-automated-merge-resolution.md` (esp. acceptance criteria §5.11)
- Existing test patterns:
  - `tests/conftest.py` — main fixtures
  - `tests/integration/conftest.py` — testcontainer pattern
  - `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` — example of testcontainer + alembic
  - `skills/iw-ai-core-testing/SKILL.md` — assertion strength, RED evidence, isolation rules
- S03 unit-test stubs you will expand:
  - `tests/unit/test_auto_merge_config.py`
  - `tests/unit/test_auto_merge_classifier.py`
  - `tests/unit/test_auto_merge_prompt.py`
  - `tests/unit/test_auto_merge_marker.py`

## Output Files

- `ai-dev/active/F-00084/reports/F-00084_S06_Tests_report.md`
- All test files listed under "Requirements" below.
- Fixtures in `tests/fixtures/auto_merge/` (if needed for repo seeding).

## Context

You are writing the test suite that:
1. Expands the RED unit-test stubs from S03 into a complete unit-level contract for `orch/daemon/auto_merge.py`.
2. Adds fixture-based integration tests that reproduce the I-00085 and I-00086 conflict shapes and assert the Phase 1 dry-run path emits the expected DaemonEvent rows with correct metadata.
3. Adds a refuse-list safety integration test.
4. Adds operator-UX-unchanged integration tests for AC4 and AC5.

**Critical**: this is a `tests-impl` step; your job is test coverage, NOT implementation. If your tests reveal a bug in S03's `auto_merge.py`, **stop and raise it as a blocker** — do NOT silently edit production code to make a test pass. The fix-cycle mechanism handles re-running upstream impl steps when tests reveal regressions.

## Requirements

### 1. Unit tests (expand S03's RED stubs)

#### `tests/unit/test_auto_merge_config.py`

| Test | What it asserts |
|------|-----------------|
| `test_load_defaults_when_file_missing` | `AutoMergeConfig.load(Path("/nonexistent"))` returns a config with `phase=0` and the default refuse-list/allowlist/limits |
| `test_load_phase_0` | Loading the default TOML yields `phase == PHASE_DISABLED` |
| `test_load_phase_1` | Loading a TOML with `phase = 1` yields `phase == PHASE_DRY_RUN` |
| `test_load_phase_2_reserved` | Loading a TOML with `phase = 2` causes the caller to refuse (test the consumer, not the loader) |
| `test_load_malformed_toml` | Malformed TOML → defaults + parse-error sentinel; no exception escapes |
| `test_load_runtime_option_id_null` | Default config has `runtime_option_id is None` |
| `test_load_runtime_option_id_int` | Explicit int loads correctly |
| `test_load_allowlist_patterns_default` | Default allowlist contains `tests/**/*.py`, `docs/**/*.md`, etc. |
| `test_load_refuselist_patterns_default` | Default refuse-list contains migration files, .gitleaks.toml, all binary suffixes |
| `test_load_limits_defaults` | `max_conflict_hunk_lines=80`, `max_conflicted_files_per_merge=5`, etc. |

#### `tests/unit/test_auto_merge_classifier.py`

| Test | What it asserts |
|------|-----------------|
| `test_all_files_allowlisted` | 3 conflict files in `tests/` → eligible, no skip |
| `test_one_file_refuse_listed` | 1 file in `orch/db/migrations/versions/x.py` → skipped_reason="refuse_list" |
| `test_mixed_refuse_and_allow` | Mix → skipped_reason="mixed_refuse_list" (refuse wins) |
| `test_binary_file_detected_by_content` | A file with `\x00` in first 8KB → skipped_reason="binary" |
| `test_binary_file_detected_by_suffix` | A `.png` file → skipped_reason="binary" |
| `test_oversized_file` | A file > max_file_size_bytes → skipped_reason="file_too_large" |
| `test_oversized_hunk` | Conflict hunk > 80 lines → skipped_reason="hunk_too_large" |
| `test_too_many_files` | > max_conflicted_files_per_merge → skipped_reason="too_many_files" |
| `test_non_allowlisted_file` | A `dashboard/static/foo.js` conflict (not in allowlist) → skipped_reason="not_allowlisted" |
| `test_decision_tree_determinism_invariant_6` | Same inputs across 10 invocations produce identical ClassificationResult (covers Invariant 6) |
| `test_refuse_list_precedence` | A binary file in `tests/` (e.g. `tests/foo.png`) is classified as refuse via suffix, NOT eligible despite the `tests/**` allowlist (defence-in-depth order) |

#### `tests/unit/test_auto_merge_prompt.py`

| Test | What it asserts |
|------|-----------------|
| `test_prompt_includes_work_item_header` | Output contains item_id, item_title |
| `test_prompt_includes_file_path` | Output contains the relative file path |
| `test_prompt_includes_three_way_content` | Output contains MERGE BASE, MAIN'S CURRENT VERSION (ours), THIS BRANCH'S VERSION (theirs) sections — covers R-00076 §5.5 |
| `test_prompt_includes_recent_commits_both_sides` | Output contains git-log-style sections for main and HEAD |
| `test_prompt_includes_abstain_clause` | Output contains the literal string `ABSTAIN` in the instructions |
| `test_prompt_includes_no_invention_clause` | Output forbids inventing new behaviour |
| `test_prompt_is_deterministic` | Same inputs across 10 invocations produce byte-identical prompt strings (covers Invariant 6) |
| `test_prompt_truncates_oversized_description` | A 10,000-word item description is bounded to ~500 words |
| `test_prompt_no_environment_leakage` | Prompt does NOT contain `os.environ['IW_CORE_DB_PASSWORD']` or any value matching env-style patterns. Set `monkeypatch.setenv("FAKE_SECRET", "leak-this")` and assert "leak-this" is NOT in the prompt. |
| `test_prompt_hash_changes_with_content` | Different file contents → different `sha256(prompt)` |

Fixture for these tests:
- Use a temporary `tmp_path` bare git repo with two diverged branches; expose them via a session-scoped fixture that yields `(worktree_path, main_sha, file_path)`.

#### `tests/unit/test_auto_merge_marker.py`

| Test | What it asserts |
|------|-----------------|
| `test_parse_request_marker_valid` | `AUTO_RESOLVE_REQUESTED={"eligible_files":["tests/a.py"]}` → parsed dict |
| `test_parse_request_marker_absent` | Stdout without marker → None |
| `test_parse_request_marker_malformed_json` | `AUTO_RESOLVE_REQUESTED=not json` → None (with WARNING log) |
| `test_parse_request_marker_multiple` | Multiple markers → first match returned (deterministic) |
| `test_parse_skip_marker_valid` | `AUTO_RESOLVE_SKIPPED={"reason":"refuse_list"}` → parsed |
| `test_request_and_skip_mutually_exclusive` | If both appear, request marker takes precedence (and a WARNING logged); tests intended bash behaviour where only one is ever emitted |
| `test_markers_in_realistic_stdout` | Embed markers in a realistic worktree_commit.sh stdout sample (with `[worktree_commit] INFO:` lines around them) — parsing still works |

### 2. Integration test: `tests/integration/test_auto_merge_phase1.py`

This file holds the AC1, AC2, AC4, AC5, AC6 integration tests. Use the testcontainer Postgres fixture.

**Test fixture pattern** (factor into a shared helper module `tests/integration/auto_merge_fixtures.py`):

```python
@pytest.fixture
def i00085_shape_conflict(tmp_path: Path, db_session) -> ConflictFixture:
    """Build a fixture repo that reproduces I-00085's conflict shape:
       - 3 test files in tests/ directory
       - main has 'theirs' version (I-00084 already merged)
       - branch has 'ours' version (functionally identical, comment-only drift)
       Returns ConflictFixture(repo_path, branch_name, expected_conflict_files).
    """
    ...

@pytest.fixture
def i00086_shape_conflict(tmp_path: Path, db_session) -> ConflictFixture:
    """Build a fixture repo that reproduces I-00086's conflict shape:
       - 3 test files; one with hardcoded-vs-dynamic assertion divergence
       - one with divergent _PREV_REVISION constant
       Returns ConflictFixture(...).
    """
    ...
```

**Tests in `test_auto_merge_phase1.py`**:

| Test | Anchored to | What it asserts |
|------|-------------|-----------------|
| `test_ac1_i00085_shape_phase_1_dry_run` | AC1 | With `phase=1` and a stubbed LLM that returns the correct resolved content, running the merge_queue subprocess against the I-00085 fixture produces: `merge_auto_resolution_attempted` event with 3 conflict_files; 3 LLM subprocess calls (mocked); `merge_auto_resolved` event with proposed_content in metadata; rebase ABORTED; `merge_conflict` event still fires; BatchItem.status == merge_failed |
| `test_ac2_i00086_shape_phase_1_dry_run` | AC2 | Same as AC1 but for the I-00086 fixture; additionally asserts the prompt sent to the mocked LLM contains the three-way content and recent commit logs |
| `test_ac4_operator_ux_unchanged_on_abstain` | AC4 | LLM mock returns `ABSTAIN` for one file; `merge_auto_resolution_failed` event with failed_reason="abstain"; `merge_conflict` still fires; BatchItem.status == merge_failed; `iw merge-queue retry-merge <id>` succeeds and resets state |
| `test_ac5_phase_0_default_behaviour` | AC5 | `phase=0`; `AUTO_RESOLVE_REQUESTED` IS emitted; `merge_auto_resolution_skipped` with `reason="phase_0"`; ZERO subprocess calls to step_executor.sh (mock assertion); `merge_conflict` fires normally |
| `test_ac6_sighup_reloads_config` | AC6 | Start at phase=0; rewrite the TOML to phase=1; send SIGHUP; next merge invokes the LLM mock |
| `test_invariant_3_phase_1_never_modifies_index` | Inv 3 | Snapshot `git rev-parse HEAD` and `git status --porcelain` before and after; both must be byte-identical |
| `test_invariant_5_oversized_metadata_truncated` | Inv 5 | LLM mock returns 1 MB per file; resulting event metadata must be <= 256 KB; metadata must include `truncated_files: [...]` |
| `test_invariant_8_failed_llm_clean_worktree` | Inv 8 | LLM subprocess mocked to return exit=1; worktree git state (status + index) unchanged afterwards |
| `test_boundary_runtime_option_id_missing` | Boundary | `runtime_option_id` points to a deleted/disabled row → `merge_auto_resolution_failed` with `failed_reason="runtime_option_missing"`; no LLM call |
| `test_boundary_malformed_toml` | Boundary | Write invalid TOML; trigger a merge; assert `auto_merge_config_invalid` event AND fallback to phase=0 |
| `test_boundary_malformed_marker` | Boundary | Inject a worktree_commit.sh that emits malformed `AUTO_RESOLVE_REQUESTED=` JSON; merge_queue treats as plain conflict; proceeds to merge_failed |

### 3. Integration test: `tests/integration/test_auto_merge_refuse_list.py`

Anchored to AC3.

| Test | What it asserts |
|------|-----------------|
| `test_ac3_migration_file_refuse_list` | Conflict in `orch/db/migrations/versions/d1e2f3*.py` → `merge_auto_resolution_skipped` with `reason="refuse_list"`; ZERO subprocess calls; bash also classified it as refuse (so `AUTO_RESOLVE_SKIPPED=` marker emitted, no `AUTO_RESOLVE_REQUESTED=`) |
| `test_refuse_list_gitleaks_toml` | Conflict in `.gitleaks.toml` → refused |
| `test_refuse_list_env_files` | Conflict in `.env`, `.env.test`, `.env.local` → all refused |
| `test_refuse_list_executor_scripts` | Conflict in `executor/worktree_setup.sh` → refused |
| `test_refuse_list_uv_lock` | Conflict in `uv.lock` → handled by existing `--ours` rule, NOT auto-resolve (this is a regression check — make sure F-00084 didn't accidentally route uv.lock to LLM) |
| `test_refuse_list_binary_png` | Conflict in `dashboard/static/foo.png` → refused (binary suffix) |
| `test_refuse_list_defence_in_depth` | A path NOT matched by bash's coarse list but matched by Python's rich glob → Python's classifier catches it; `merge_auto_resolution_skipped` fires |
| `test_mixed_refuse_and_allow_refuse_wins` | One file in `tests/`, one in `orch/db/migrations/versions/` → `reason="mixed_refuse_list"`; no LLM call |

### 4. LLM subprocess mocking

Use `pytest.MonkeyPatch` to replace `subprocess.run` (or, better, replace `_run_agent_oneshot`-equivalent at the Python boundary) with a deterministic fake:

```python
class FakeLLM:
    def __init__(self):
        self.calls: list[FakeLLMCall] = []
        self.response_for: dict[str, str] = {}     # filename → response

    def __call__(self, *args, **kwargs):
        # capture call args, return preconfigured response or 'ABSTAIN'
        ...
```

Fixture:

```python
@pytest.fixture
def fake_llm(monkeypatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(
        "orch.daemon.auto_merge.invoke_llm_for_file",
        fake.invoke,
    )
    return fake
```

**Do NOT make real LLM calls in tests.** Real-LLM tests are a manual-smoke item; out of scope for CI.

### 5. Assertion strength rules (from `skills/iw-ai-core-testing/SKILL.md`)

- Assert on **specific event types and metadata keys**, not just "an event fired".
- Compare metadata structure with `assert event.event_metadata["conflict_files"] == [...]`, not loose `in` checks.
- Snapshot git state via `git rev-parse HEAD` + `git status --porcelain` and compare; don't just check exit codes.
- Use `pytest.approx` only for floats; never for integer or string metadata.
- Avoid `assert ... is not None` as the final assertion — that's a smoke check, not a contract.
- Test names MUST describe behaviour, not implementation (e.g., `test_ac1_i00085_shape_phase_1_dry_run` not `test_attempt_resolution_phase_1`).

### 6. Coverage targets

- Targeted coverage on `orch/daemon/auto_merge.py`: ≥ 90 % line coverage (this module is new; aim high).
- `merge_queue.py` new lines: each new branch covered.
- Run `uv run pytest tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py --cov=orch.daemon.auto_merge -v` and include the coverage report in your S06 report.

## TDD Requirement

Tests are the deliverable here. There is no production code in this step. **RED phase is structurally satisfied** by writing tests against the existing (S03-delivered) module; the GREEN phase is making your assertions strong enough that they would fail if S03 had skipped a contract.

**`tdd_red_evidence`** in your report should be a 1-3 line snippet showing that at least one of your new tests would have FAILED against a deliberately-broken version of S03 (e.g., comment out the Phase-0 short-circuit and run `test_ac5_phase_0_default_behaviour` to confirm it fails; then restore and confirm it passes).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix.
2. `make typecheck` — zero errors involving your new test files.
3. `make lint` — zero errors.
4. **Targeted unit + integration tests**: `uv run pytest tests/unit/test_auto_merge_*.py tests/integration/test_auto_merge_*.py -v` must be GREEN.

## Test Verification

- Run ONLY the test files you wrote/modified.
- Do NOT run `make test-unit` or `make test-integration` (those are S13/S14 QV gates).

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "tests-impl",
  "work_item": "F-00084",
  "completion_status": "complete",
  "files_changed": [
    "tests/unit/test_auto_merge_config.py",
    "tests/unit/test_auto_merge_classifier.py",
    "tests/unit/test_auto_merge_prompt.py",
    "tests/unit/test_auto_merge_marker.py",
    "tests/integration/test_auto_merge_phase1.py",
    "tests/integration/test_auto_merge_refuse_list.py",
    "tests/integration/auto_merge_fixtures.py"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "<N> passed, 0 failed; coverage on orch.daemon.auto_merge = <pct>%",
  "tdd_red_evidence": "Confirmed test_ac5_phase_0_default_behaviour fails when Phase-0 short-circuit is removed (asserted ZERO subprocess calls; got 3)",
  "blockers": [],
  "notes": "All AC1..AC6 + every Boundary Behavior row + every Invariant has at least one mapped test. Mocking strategy: FakeLLM replaces invoke_llm_for_file at the Python boundary; no real LLM calls in CI."
}
```
