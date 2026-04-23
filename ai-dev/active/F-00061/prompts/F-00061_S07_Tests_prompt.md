# F-00061_S07_Tests_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S07
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

(Same policy as S01. Read-only `docker ps/inspect/logs` only. Testcontainers spun up by pytest fixtures are the ONLY allowed docker interaction. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(NEVER `alembic upgrade|downgrade|stamp` against port 5433. Your tests run migrations inside testcontainer fixtures — `tests/conftest.py` + `tests/integration/conftest.py` handle this. Do NOT manually invoke alembic CLI.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — **Acceptance Criteria AC1–AC7** (every one is a test), **Boundary Behavior** (every row is a test), **Invariants** (every one is a test), **TDD Approach** (test layout)
- `ai-dev/active/F-00061/reports/F-00061_S03_Backend_QvBaseline_report.md` — pure module public API (parsers, `subtract`, `Fingerprint`, serializers)
- `ai-dev/active/F-00061/reports/F-00061_S05_Backend_Integration_report.md` — hook insertion line numbers (important for integration fixtures)
- `tests/CLAUDE.md` — testcontainer rules (hard requirement: no live DB, testcontainer replace `postgresql+psycopg2://` with `postgresql+psycopg://`, `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all`, no `importlib.reload`)
- `tests/conftest.py` — existing fixtures (`db_session`, `db_engine`, etc.)
- `tests/integration/conftest.py` — integration-specific setup including real PostgreSQL container
- `tests/unit/` — existing patterns to mirror for unit-test files
- `tests/integration/` — existing patterns for integration tests
- `orch/daemon/qv_baseline.py` — S03's pure module (unit test target)
- `orch/daemon/batch_manager.py`, `orch/daemon/fix_cycle.py` — S05's integration (integration test target)
- `executor/scope_gate.py` — P1 helper the bundled AC7 tests cover

## Output Files

- New: `tests/unit/orch/daemon/test_qv_baseline.py` — parsers + algebra unit tests (AC1/AC2 correctness anchor, Boundary Behavior rows 3–5, Invariants 3, 4, 6)
- New: `tests/integration/daemon/test_baseline_qv_pipeline.py` — AC1–AC6 integration coverage
- New: `tests/unit/executor/test_scope_gate.py` — bundled P1 coverage (AC7)
- `ai-dev/active/F-00061/reports/F-00061_S07_Tests_report.md` — step report

**Do NOT create `__init__.py` package markers in `tests/unit/orch/daemon/`, `tests/integration/daemon/`, or `tests/unit/executor/`.** Pytest's rootdir-based collection (`testpaths = ["tests"]` in `pyproject.toml`) discovers nested test modules without them — the existing pattern in `tests/integration/api/` and `tests/integration/dashboard/` is the precedent. Adding `__init__.py` would violate `scope.allowed_paths` and get rejected by the P1 scope gate at merge.

## Context

You are the test-coverage owner for F-00061. Your suite is the GREEN check on every AC. Mandatory TDD loop: for each AC, write the test first (RED on pre-S03/S05 code), then confirm it's GREEN on current code. If any test passes on the base branch too, the test isn't actually exercising the feature — rewrite it.

You ALSO own the bundled unit tests for the P1 helper at `executor/scope_gate.py` — those close AC7.

## Semantic Correctness (I003 lesson — MANDATORY)

I003's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed. But the bug was NOT fixed. Your tests must verify SPECIFIC VALUES and BOUNDED COUNTS, not presence-only:

- BAD: `assert len(subtract(H, B).failures) > 0` (truthy — passes even if subtraction is a no-op)
- GOOD: `assert [f.key for f in subtract(H, B).failures] == ["tests/unit/bar.py::test_new_regression"]` (exact match on expected delta)

- BAD: `assert baseline_row is not None` (passes on an empty baseline — misses the fingerprint mismatch bug)
- GOOD: `assert baseline_row.fingerprint == {"failures": [{"kind": "test", "key": "tests/unit/foo.py::test_flaky"}], "unparseable": []}` (byte-precise payload)

- BAD: `assert "test_flaky" not in findings` (passes on empty findings)
- GOOD: `assert "test_flaky" not in findings and "test_new_regression" in findings` (both poles)

- BAD: `assert query_count > 0` (any non-zero — misses N+1 regressions)
- GOOD: `assert query_count <= K_GATES + 2` for the specific `K_GATES` in the fixture (tight bound against N² drift)

- BAD: `assert db.query(QvBaseline).count() > 0` (AC3 passes on 1 row when 3 gates were configured)
- GOOD: `assert db.query(QvBaseline).count() == 3` AND enumerate the expected `(gate_name, base_sha)` triples

Apply this posture to EVERY assertion. If a test would pass on `pass`-only production code, tighten it.

## Requirements

### 1. `tests/unit/orch/daemon/test_qv_baseline.py` — parser + algebra unit tests

One test class per parser:

- `TestRuffParser`:
  - `test_happy_path_json_output` — feed a representative `ruff check --output-format json` sample; assert `Fingerprint.failures` contains one entry per violation with keys of shape `"<file>::<rule>"`
  - `test_happy_path_text_output` — feed the default ruff text output; same fingerprint emerges
  - `test_line_number_change_collapses` — two samples differing only in line numbers produce identical `fingerprint_to_jsonable` output (Boundary Behavior row 4)
  - `test_determinism` — parse same input twice, assert byte-identical JSON
  - `test_unparseable_lines` — corrupt output where some lines don't match the regex; they land in `unparseable` and `failures` contains the parseable ones

- `TestPytestParser`:
  - `test_happy_path_failed_lines` — representative pytest stdout with `FAILED tests/unit/x.py::test_a - AssertionError`; assert Fingerprint nodeid keys extracted
  - `test_error_message_variation_collapses` — two samples with same nodeid but different error messages produce identical fingerprint (Boundary Behavior row 5)
  - `test_summary_only_treated_as_unparseable` — pytest output with only a summary "3 failed" and no per-test FAILED lines → Fingerprint unparseable populated, failures empty
  - `test_determinism` — idempotent parse

- `TestMypyParser`:
  - `test_happy_path` — standard mypy output; key shape `"<file>::<error-code>"`
  - `test_line_number_change_collapses` — drift-tolerance check
  - `test_determinism`

- `TestSubtract`:
  - `test_identity` — `subtract(H, Fingerprint(()))` returns a Fingerprint equal to H
  - `test_full_overlap` — `subtract(H, H).failures == ()` but unparseable from `current` survives
  - `test_partial_overlap_preserves_order` — `subtract` over `{a, b, c}` with baseline `{b}` returns `(a, c)` in that order
  - `test_monotonicity` — property-style: for many random-ish inputs, `len(subtract(H, B).failures) <= len(H.failures)`
  - `test_unparseable_always_surfaces` — even if baseline has the same raw unparseable text, `current.unparseable` is preserved in the result

- `TestFingerprintRoundTrip`:
  - `test_to_jsonable_from_jsonable_is_identity` — for several hand-crafted Fingerprints with mixed kinds and unparseable entries

- `TestGateParsers`:
  - `test_lint_maps_to_parse_ruff` — `GATE_PARSERS["lint"] is parse_ruff`
  - `test_typecheck_maps_to_parse_mypy`
  - `test_unit_tests_maps_to_parse_pytest`
  - `test_integration_tests_maps_to_parse_pytest`
  - `test_frontend_tests_maps_to_parse_pytest`
  - `test_format_is_absent` — `"format" not in GATE_PARSERS` (defends against a future edit re-introducing the `ruff format --check` mapping that would break AC1 for S11)

Use `pytest.mark.parametrize` for the multi-case tests. Fixtures for sample gate outputs live in a module-level string literal or under `tests/unit/orch/daemon/fixtures/` — your choice, but keep them inline if short.

### 2. `tests/integration/daemon/test_baseline_qv_pipeline.py` — AC1–AC6 integration coverage

Use `db_session` from `tests/integration/conftest.py` (testcontainer-backed). One test per AC:

- `test_ac1_pre_existing_failure_excluded_from_fix_cycle` — seed a `WorkItem` + `WorkflowStep(gate="unit-tests")` + a matching `QvBaseline` with one failing nodeid; simulate a gate run by feeding raw output through `_get_qv_findings` (or its test-friendly split-out); assert returned findings are empty.
- `test_ac2_regression_surfaced_cleanly` — baseline contains `test_flaky`; current run contains `test_flaky` + `test_new_regression`; assert the findings-for-fix-cycle contain ONLY `test_new_regression` and preserve the string formatting the downstream prompt builder expects.
- `test_ac3_baselines_created_at_setup` — exercise `_compute_qv_baselines` (you may call the private method directly via the class; see existing integration tests for the pattern); assert exactly one `QvBaseline` row per configured qv-gate step with matching `base_sha`.
- `test_ac4_rebase_invalidates_baseline` — seed a baseline at `base_sha=Y`; simulate the branch moving to `Z` (mock `git merge-base` via monkeypatch on the helper); trigger `_get_qv_findings`; assert the row at Y is gone and a row at Z exists with a fresh fingerprint.
- `test_ac5_kill_switch_disables` — `monkeypatch.setenv("IW_CORE_BASELINE_QV", "false")`; call `_compute_qv_baselines`; assert zero rows created; call `_get_qv_findings`; assert legacy (raw) findings pass through unchanged.
- `test_ac6_legacy_item_graceful` — do NOT create any `QvBaseline` rows; call `_get_qv_findings` for a qv-gate step; assert no exception raised and the legacy raw findings flow through (same shape as pre-F-00061).

Boundary-behavior tests (add to the same file or a `TestBaselineBoundary` class):
- `test_baseline_compute_timeout_is_contained` — make the gate subprocess time out; confirm no partial row is persisted; setup does not fail; WARNING logged (capture via `caplog`).
- `test_baseline_empty_passing_gate_persists_sentinel_row` — gate passes on base (no failures); row is still inserted with `fingerprint={"failures": [], "unparseable": []}`.
- `test_rebase_during_gate_uses_snapshot_sha` — (simulated via monkeypatch) the subtraction uses the SHA resolved at the START of `_get_qv_findings`, not a later value.

Mock/fake strategy:
- For subprocess invocation, patch the daemon's existing subprocess helper to return canned stdout/stderr/returncode per gate command. Do NOT actually run `make test-integration` inside these tests — that would be recursive.
- Provide a small fake `WorkflowStep` + `QvBaseline` fixture set with 2–3 gates (lint, unit-tests, integration-tests) to cover the main gates F-00061 supports.

### 3. `tests/unit/executor/test_scope_gate.py` — bundled P1 coverage (AC7)

The helper at `executor/scope_gate.py` is a pure Python script. Invoke it via `subprocess.run([sys.executable, "executor/scope_gate.py", manifest_path, item_id], input=file_list, capture_output=True, text=True)` inside the test. Write the manifest JSON to a `tmp_path` fixture per test.

Required tests (one function each):

- `test_legacy_mode_no_scope_field_exits_zero` — manifest `{"id": "X"}` with no `scope` key; stdin contains arbitrary paths; expect rc=0, stdout empty, stderr contains a "skipping gate" warning.
- `test_legacy_mode_empty_allowed_paths_exits_zero` — manifest `{"scope": {}}`; same expectation.
- `test_exact_path_match_allows` — `allowed_paths: ["dashboard/routers/items.py"]`; stdin has `dashboard/routers/items.py`; expect rc=0.
- `test_exact_path_mismatch_flags_as_violation` — same allow-list; stdin has `dashboard/routers/other.py`; expect rc=1, stdout contains exactly that path.
- `test_dir_double_star_allows_nested` — `allowed_paths: ["dashboard/routers/**"]`; stdin has `dashboard/routers/items.py` and `dashboard/routers/sub/nested.py`; expect rc=0.
- `test_dir_double_star_blocks_siblings` — same allow-list; stdin has `dashboard/app.py`; expect rc=1 and the path in stdout.
- `test_fnmatch_single_level_wildcard` — `allowed_paths: ["dir/*.py"]`; allow `dir/foo.py`, block `dir/sub/foo.py` and `dir/foo.js`.
- `test_implicit_ai_dev_active_allow` — `allowed_paths: []`... actually wait: empty allowed triggers legacy mode. Use `allowed_paths: ["x.py"]` and confirm `ai-dev/active/<ID>/some_report.md` is allowed without being listed. (This is where the implicit rule fires.)
- `test_implicit_ai_dev_archive_allow` — same shape with `ai-dev/archive/<ID>/evidence.png`.
- `test_violation_listing_preserves_input_order` — stdin has `["z.py", "a.py", "m.py"]` where none match allow-list; stdout lists them in that exact input order.
- `test_malformed_manifest_exits_two` — write invalid JSON to the manifest file; expect rc=2 and a stderr error line.
- `test_missing_manifest_exits_two` — point at a non-existent path; expect rc=2.

Keep tests isolated: each uses its own `tmp_path / "manifest.json"` so they don't interfere.

### 4. TDD discipline

For each integration test in (2) and each qv_baseline unit test in (1):
- Write the test FIRST against a current-main checkout of the file(s) you're testing
- Confirm it FAILS (RED) — the production code is either missing (`ImportError`) or produces wrong results
- Add the production change — but ACTUALLY, production code already exists via S03 + S05 checkouts, so the RED phase is a historical check: mentally confirm the test would have failed against pre-S03/S05 code and document that in the report.

For scope_gate.py tests (bundled P1 coverage): the production code already exists from commit `42feca2`. RED phase is N/A for these — they're retroactive coverage. Note this in the S07 report's "TDD compliance" section.

### 5. Query-count / N+1 discipline

For the integration tests that exercise `_compute_qv_baselines` and `_get_qv_findings`, add a single `test_no_n_plus_one_in_compute_qv_baselines` that uses the `sqlalchemy.event` listen API (see existing tests/integration/test_* for the pattern) to count queries and asserts the count is bounded (O(N gates) + O(1) per gate, not O(N^2)).

## Project Conventions

Read `tests/CLAUDE.md`. Hard rules for this step:
- NEVER connect to port 5433. Use `db_session` fixture only.
- NEVER call `importlib.reload(orch.config)`. Use `monkeypatch.setenv` / `delenv`.
- In testcontainer URLs, `postgresql+psycopg2://` MUST be replaced with `postgresql+psycopg://` (conftest handles this).
- After `Base.metadata.create_all()`, run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` (conftest handles this).

## TDD Requirement

Follow Red-Green-Refactor as above. Document RED-confirmation in the report for each integration test.

## Test Verification (NON-NEGOTIABLE)

Before reporting complete:
1. `make test-unit` — all new unit tests in `tests/unit/orch/daemon/test_qv_baseline.py` AND `tests/unit/executor/test_scope_gate.py` pass; no pre-existing test now fails because of your work (diff-only regression check)
2. `make test-integration` — all new integration tests in `tests/integration/daemon/test_baseline_qv_pipeline.py` pass; pre-existing tests unchanged in behavior
3. `uv run mypy tests/` — zero errors on your new files
4. `uv run ruff check tests/unit/orch/daemon/ tests/unit/executor/ tests/integration/daemon/` — zero errors on your new files
5. Scope discipline: `git diff main..HEAD --name-only` shows ONLY your new test files (plus F-00061 design/report artefacts)

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "F-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/orch/daemon/test_qv_baseline.py",
    "tests/integration/daemon/test_baseline_qv_pipeline.py",
    "tests/unit/executor/test_scope_gate.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed (unit), Y integration passed, Z scope-gate tests passed",
  "acceptance_criteria_coverage": {
    "AC1": "test_ac1_pre_existing_failure_excluded_from_fix_cycle",
    "AC2": "test_ac2_regression_surfaced_cleanly",
    "AC3": "test_ac3_baselines_created_at_setup",
    "AC4": "test_ac4_rebase_invalidates_baseline",
    "AC5": "test_ac5_kill_switch_disables",
    "AC6": "test_ac6_legacy_item_graceful",
    "AC7": "test_scope_gate.py (12 test functions covering all AC7 sub-cases)"
  },
  "blockers": [],
  "notes": ""
}
```
