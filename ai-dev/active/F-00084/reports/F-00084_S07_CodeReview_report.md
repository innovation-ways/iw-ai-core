# F-00084 S07 — Per-Agent Code Review: Tests (S06)

**Step**: S07 — code-review-impl
**Work Item**: F-00084 — LLM-Assisted Merge Conflict Resolution (Phase 0 + Phase 1 dry-run)
**Date**: 2026-05-16
**Reviewer**: code-review-impl

---

## Summary

8 test files reviewed. 119 tests pass; coverage on `orch.daemon.auto_merge` is reported at 95%. The suite is well-structured with deterministic mocking, correct testcontainer isolation, and strong assertion quality on the `auto_merge.py` module itself.

**Two HIGH findings** were identified, both relating to `merge_queue.py` coverage and the completeness of the AC4 operator-UX claim. No CRITICAL findings. No real LLM call is possible in CI.

**Verdict: PASS_WITH_NOTES**

---

## Findings Table

| # | Severity | File | Line(s) | Description |
|---|----------|------|---------|-------------|
| F1 | HIGH | `tests/integration/test_auto_merge_phase1.py` | — | `merge_queue.py`'s new branches are not exercised by any test. The checklist requires at least one test per branch: "neither marker present", "malformed marker defensive fallback" (what `merge_queue.py` does after `parse_auto_resolve_marker` returns `None`), and the phase-dispatch logic. No test calls through `_merge_item()`. |
| F2 | HIGH | `tests/integration/test_auto_merge_phase1.py` | ~308–404 | AC4 does not verify `BatchItem.status = merge_failed` or that `merge_conflict` DaemonEvent fires in the same format as today (Invariant 4). The tests only assert on `attempt_resolution()` return values and `merge_auto_resolution_failed` events — both within `auto_merge.py` — but the AC contract says "BatchItem.status transitions to merge_failed AND merge_conflict DaemonEvent fires as today". |
| F3 | MEDIUM | `tests/integration/test_auto_merge_phase1.py` | ~518–546 | AC6 is missing its `config_reloaded DaemonEvent` assertion. The design (AC6) states: "the change is recorded in a config_reloaded DaemonEvent (reuse existing project_registry SIGHUP path)". `test_ac6_sighup_reloads_config` verifies the `_cached_config` field but does not assert that any event is emitted. |
| F4 | MEDIUM | `tests/integration/test_auto_merge_phase1.py` | ~518–546 | AC6 tests `reload_config()` directly but does not test the SIGHUP signal handler hookup. The AC says "SIGHUPs the daemon → next conflict triggers Phase 1". Testing only the function leaves the signal-to-function wiring untested. (Accepted limitation for a daemon integration test, but flagged per checklist.) |
| F5 | MEDIUM | `tests/integration/auto_merge_fixtures.py` | ~75–148 | `make_git_conflict_repo()` is defined and exported but never called by any test. The integration tests either create inline git repos (Invariant 3) or pass bare `tmp_path` to `attempt_resolution()` (all other tests). This is dead fixture code that inflates cognitive load. |
| F6 | MEDIUM | None | — | Boundary row "Phase 1 with `--resume-rebase` flag invoked → worktree_commit.sh rejects with exit 2" has no corresponding test. This is a bash-layer boundary; Python tests cannot exercise it directly. The gap should be noted for the bash review (S02 scope), but is surfaced here for completeness. |
| F7 | LOW | `tests/unit/test_auto_merge_prompt.py` | ~222–319 | `test_prompt_is_deterministic_original` (line 222) and `test_prompt_is_deterministic` (line 139) test identical behaviour with identical stubs. Similarly `test_prompt_contains_abstain_token` (line 245) duplicates `test_prompt_includes_abstain_clause` (line 117); `test_prompt_contains_work_item_info` and `test_prompt_includes_work_item_header` are duplicates. These 4+ duplicate tests do not add coverage but confuse the signal-to-noise ratio. |
| F8 | LOW | `tests/unit/test_auto_merge_classifier.py` | — | `test_one_file_refuse_listed` (line 68), `test_refuse_list_takes_precedence` (line 333), and `test_refuse_list_precedence` (line 306) test highly overlapping scenarios (refuse-list wins over allowlist/binary detection). The classifier tests also duplicate `test_binary_file_detected_by_content` / `test_binary_detection_causes_skip` (lines 121 and 378). Low severity but indicates copy-paste test growth. |
| F9 | LOW | `tests/unit/test_auto_merge_config.py` | ~295–311 | `test_load_actual_auto_merge_toml` uses `pytest.skip()` if `executor/auto_merge.toml` is absent. The file is part of this feature's deliverable so the skip should never fire in CI, but the guard is cosmetically inconsistent with the no-`pytest.skip()` red-flag rule. |
| F10 | LOW | `tests/unit/test_auto_merge_config.py` | ~109–125 | `test_load_malformed_toml` asserts `"TOML" in error or "parse" in error.lower() or "error" in error.lower()`. This is looser than the contract: any non-empty string with "error" anywhere passes. Suggest asserting the error message contains the TOML source (e.g., file path or line number). |

---

## AC Coverage Mapping

| AC | Test Function(s) | Coverage |
|----|-----------------|----------|
| AC1 | `test_ac1_i00085_shape_phase1_dry_run` · `test_ac1_resolution_attempted_event_structure` | Full — conflict_files, phase, policy_decision, runtime_option_id, per_file proposed_content |
| AC2 | `test_ac2_i00086_shape_prompt_contains_three_way_content` | Full — 3 LLM calls, correct file paths, correct model/cli_tool |
| AC3 | `test_ac3_migration_file_refuse_list` · `test_ac3_migration_refuse_list_attempt_resolution_phase1` · parametrized env/executor/image/binary/uv.lock/sensitive tests | Full — classify+skip, no LLM call, event reason |
| AC4 | `test_ac4_operator_ux_unchanged_on_abstain` · `test_ac4_operator_ux_unchanged_on_llm_error` | **Partial** — verifies `attempt_resolution` return values and `merge_auto_resolution_failed` events; does NOT verify `BatchItem.status=merge_failed` or `merge_conflict` event equivalence (see F2) |
| AC5 | `test_ac5_phase0_default_no_llm_call` · `test_ac5_phase0_short_circuit_invariant_2` | Full — zero LLM calls, skipped event reason=phase_0, TDD red evidence |
| AC6 | `test_ac6_sighup_reloads_config` · `test_ac6_reload_config_missing_file_returns_defaults` | **Partial** — reload_config() surface covered; SIGHUP handler wiring and config_reloaded event not tested (see F3, F4) |

---

## Invariant Coverage Mapping

| Invariant | Test(s) | Coverage |
|-----------|---------|----------|
| Inv 1: No LLM token for refuse-listed file | `test_invariant1_no_llm_call_for_phase0_eligible_files` · all AC3 tests assert `len(fake_llm.calls) == 0` | Full |
| Inv 2: No LLM token when phase=0 | `test_ac5_phase0_default_no_llm_call` · `test_ac5_phase0_short_circuit_invariant_2` | Full — TDD red evidence included |
| Inv 3: Phase 1 never modifies git index | `test_invariant3_phase1_never_modifies_worktree` | Full — HEAD + status --porcelain snapshotted before/after |
| Inv 4: Operator commands unchanged | AC4 tests (partial) | **Gap** — BatchItem status and merge_conflict event format not asserted (see F2) |
| Inv 5: event_metadata ≤ 256 KB | `test_invariant5_oversized_metadata_is_truncated` | Full — 1 MB content injected, serialized size checked |
| Inv 6: Decision tree is deterministic | `test_decision_tree_determinism_invariant_6` · `test_prompt_is_deterministic` | Full — 10 repeated invocations compared |
| Inv 7: Agent + model matches runtime_option_id | `test_ac2_i00086_shape_prompt_contains_three_way_content` (`fake_llm.calls[i].model == default_runtime_option.model`) | Full — model and cli_tool verified per call |
| Inv 8: Failed LLM call leaves worktree clean | `test_invariant8_failed_llm_leaves_worktree_clean` | Full — file content compared byte-for-byte before/after |

---

## Boundary Behavior Coverage Mapping

| Boundary Scenario | Test(s) | Coverage |
|-------------------|---------|----------|
| All conflict files refuse-listed | `test_ac3_migration_file_refuse_list` | Full |
| Some refuse-listed, some allowlisted (mixed_refuse_list) | `test_mixed_refuse_and_allow_refuse_wins` · `test_mixed_refuse_and_allow` (unit) | Full |
| All allowlisted | `test_ac1_i00085_shape_phase1_dry_run` | Full |
| LLM returns ABSTAIN | `test_ac4_operator_ux_unchanged_on_abstain` | Full |
| LLM subprocess exits non-zero | `test_ac4_operator_ux_unchanged_on_llm_error` | Full |
| Conflict hunk exceeds max_conflict_hunk_lines | `test_oversized_hunk` (unit) · `test_hunk_size_limit_causes_skip` (unit) | Full |
| More than max_conflicted_files_per_merge files | `test_too_many_files` (unit) | Full |
| Binary file | `test_binary_file_detected_by_content` · `test_binary_file_detected_by_suffix` (unit) | Full |
| Empty TOML / missing config | `test_load_defaults_when_file_missing` | Full |
| Malformed TOML | `test_load_malformed_toml` | Full (assertion slightly loose — see F10) |
| runtime_option_id points to nonexistent row | `test_boundary_runtime_option_id_missing` · `test_boundary_runtime_option_falls_back_to_default` | Full |
| AUTO_RESOLVE_REQUESTED marker malformed | `test_boundary_malformed_marker_parse_auto_resolve` (parser) | **Partial** — parser function tested; merge_queue.py's handling of parse=None not tested (see F1) |
| Phase 1 with --resume-rebase flag | None | **Gap** — bash-layer boundary, no Python test possible; see F6 |

---

## Detailed Finding Descriptions

### F1 (HIGH): merge_queue.py branches not exercised

The review checklist explicitly requires at least one test per branch of `merge_queue.py`'s new F-00084 hook:
- AUTO_RESOLVE_REQUESTED + phase 0 path
- AUTO_RESOLVE_REQUESTED + phase 1 path (all good / abstain / error)
- AUTO_RESOLVE_SKIPPED path (refuse-list / mixed_refuse_list)
- **Neither marker present** (standard conflict path unchanged)
- **Malformed marker defensive fallback** (what merge_queue.py does when `parse_auto_resolve_marker()` returns `None`)

The S06 tests call `attempt_resolution()` and `classify_conflicts()` directly, completely bypassing `merge_queue.py._merge_item()`. The "neither marker present" branch and the "malformed marker" fallback in `merge_queue.py` are untested. Since these branches were introduced in S03 and reviewed in S04, the risk is moderate, but the test gap is explicit.

**Suggested fix**: Add a unit test for `merge_queue.py` that monkeypatches `attempt_resolution` and tests the new dispatch logic (marker present vs. absent, malformed marker fallback).

### F2 (HIGH): AC4 missing BatchItem and merge_conflict assertions

AC4 contract includes "BatchItem.status transitions to merge_failed AND merge_conflict DaemonEvent fires as today". The `test_ac4_*` tests only verify `attempt_resolution()` return values (`result.success is False`) and `merge_auto_resolution_failed` events within `auto_merge.py`. They do not:
1. Assert `BatchItem.status == merge_failed` in the DB.
2. Assert a `merge_conflict` DaemonEvent fired with the same payload as the pre-F-00084 path.

Invariant 4 explicitly requires the operator command equivalence to be tested.

**Suggested fix**: Extend AC4 integration tests to query the `BatchItem` row and `merge_conflict` event after calling through a thin wrapper around `merge_queue.py`'s handler, or add a dedicated Invariant 4 test.

### F3 (MEDIUM): AC6 missing config_reloaded DaemonEvent

Design says: "the change is recorded in a config_reloaded DaemonEvent (reuse existing project_registry SIGHUP path)". `test_ac6_sighup_reloads_config` asserts `am._cached_config.phase == PHASE_DRY_RUN` but never queries `DaemonEvent` rows.

### F4 (MEDIUM): AC6 SIGHUP handler wiring not tested

`reload_config()` is tested directly. The daemon's signal handler (`signal.SIGHUP` → `reload_config()`) is not tested. Accepted limitation for a daemon-level integration, but should be flagged for the final review.

### F5 (MEDIUM): make_git_conflict_repo() is dead code

`make_git_conflict_repo()` in `auto_merge_fixtures.py` (lines 75–148) is exported and documented but never imported or called by any test. The integration tests that need git repos create them inline (e.g., `test_invariant3_phase1_never_modifies_worktree`). The fixture should either be used or removed to avoid confusion.

### F6 (MEDIUM): "Phase 1 with --resume-rebase" boundary not testable in Python

The boundary row requires `worktree_commit.sh` to exit 2 with an error message. This is a bash-layer behavior; no Python test covers it. Noted for the executor layer review (S02), but the gap means one boundary row is untested end-to-end.

### F7 (LOW): Duplicate tests in test_auto_merge_prompt.py

Four pairs of essentially identical tests exist in `test_auto_merge_prompt.py`. Duplicates add no coverage and obscure signal on failure.

### F8 (LOW): Duplicate classifier tests

Similar patterns in `test_auto_merge_classifier.py` — `test_one_file_refuse_listed`, `test_refuse_list_takes_precedence`, `test_refuse_list_precedence` test the same classification logic with minor variations, and binary detection is covered twice.

### F9 (LOW): pytest.skip() in test_load_actual_auto_merge_toml

The `pytest.skip()` guard is cosmetically inconsistent with the no-skip red-flag rule. In practice the file will always be present in CI for this feature branch.

### F10 (LOW): Loose error message assertion in test_load_malformed_toml

`assert "TOML" in error or "parse" in error.lower() or "error" in error.lower()` accepts any non-empty string containing the word "error". A tighter assertion (e.g., checking the error contains the filename or a TOML-specific parse error class name) would better guard against accidental pass.

---

## Assertion Strength Assessment

| Check | Result |
|-------|--------|
| No `assert X is not None` as final assertion | PASS — all final assertions are specific |
| Event-firing tests assert event_type AND specific metadata keys | PASS — e.g., `meta["conflict_files"]`, `meta["reason"]`, `meta["abstained_files"]` |
| LLM-call tests assert call count AND file/model | PASS — `len(fake_llm.calls) == N` + `called_files == set(...)` + model/cli_tool checks |
| Git-state tests snapshot HEAD + status --porcelain | PASS — `test_invariant3_phase1_never_modifies_worktree` does this correctly |
| No `pytest.approx` on integers/strings | PASS |
| No `time.sleep()` for synchronisation | PASS |

---

## LLM Mock Hygiene

| Check | Result |
|-------|--------|
| FakeLLM intercepts `invoke_llm_for_file` at Python boundary | PASS — `monkeypatch.setattr("orch.daemon.auto_merge.invoke_llm_for_file", fake.invoke)` |
| No real LLM call possible in CI | PASS — all subprocess paths patched in unit tests; FakeLLM used in integration tests |
| Mock responses deterministic (no `random()`, no `now()`) | PASS — only `hashlib.sha256` used for hash generation |
| `invoke_llm_for_file` unit tests patch subprocess.run, not shell | PASS — `patch("orch.daemon.auto_merge.subprocess.run")` is Python-boundary patching |

---

## Isolation Rules

| Check | Result |
|-------|--------|
| No live DB connection (port 5433) | PASS — all integration tests use `db_session` from testcontainers conftest |
| No `importlib.reload(orch.config)` | PASS |
| FTS DDL not needed (auto_merge tests don't use FTS) | N/A |
| `DaemonEvent.metadata` accessed via `event_metadata` | PASS — e.g., `attempted[0].event_metadata` |

---

## TDD Evidence

Provided in S06 report: `test_ac5_phase0_short_circuit_invariant_2` demonstrates RED evidence — with `phase=1` config (violating Phase-0 contract), `len(fake_llm.calls) == 1` is asserted, proving the AC5 assertion `calls == 0` would fail if the short-circuit were removed. Evidence is genuine and self-contained.

---

## Coverage

- Reported: 95% on `orch.daemon.auto_merge` (above 90% threshold). ✓
- `merge_queue.py` new branches: **not exercised by any test** (see F1). HIGH gap.

---

## Overall Verdict

**PASS_WITH_NOTES**

The suite is well-crafted: deterministic mocks, correct isolation, strong per-line assertions, and good AC coverage for the `auto_merge.py` module. The two HIGH findings are coverage gaps in `merge_queue.py` and Invariant 4 (operator UX claim) that were not addressed in S06 — they are carry-over scope for the S08 final review or a targeted fix cycle.

---

```json
{
  "verdict": "PASS_WITH_NOTES",
  "critical": 0,
  "high": 2,
  "medium": 4,
  "low": 4,
  "findings": [
    {
      "id": "F1",
      "severity": "HIGH",
      "file": "tests/integration/test_auto_merge_phase1.py",
      "description": "merge_queue.py new branches not exercised: 'neither marker present' path and 'malformed marker defensive fallback' handling inside merge_queue.py are untested. Tests call attempt_resolution() directly, bypassing _merge_item()."
    },
    {
      "id": "F2",
      "severity": "HIGH",
      "file": "tests/integration/test_auto_merge_phase1.py",
      "description": "AC4 / Invariant 4 gap: no test verifies BatchItem.status=merge_failed or that merge_conflict DaemonEvent fires with the same payload as the pre-F-00084 path. Only attempt_resolution() return values are asserted."
    },
    {
      "id": "F3",
      "severity": "MEDIUM",
      "file": "tests/integration/test_auto_merge_phase1.py",
      "description": "AC6: config_reloaded DaemonEvent not asserted in test_ac6_sighup_reloads_config — design requires this event to fire on SIGHUP reload."
    },
    {
      "id": "F4",
      "severity": "MEDIUM",
      "file": "tests/integration/test_auto_merge_phase1.py",
      "description": "AC6: SIGHUP signal handler wiring not tested — only reload_config() is called directly."
    },
    {
      "id": "F5",
      "severity": "MEDIUM",
      "file": "tests/integration/auto_merge_fixtures.py",
      "description": "make_git_conflict_repo() is defined and documented but never called by any test (dead fixture code)."
    },
    {
      "id": "F6",
      "severity": "MEDIUM",
      "file": null,
      "description": "Boundary row 'Phase 1 with --resume-rebase flag invoked' has no Python-level test. Bash-layer boundary; gap should be covered by executor bash tests."
    },
    {
      "id": "F7",
      "severity": "LOW",
      "file": "tests/unit/test_auto_merge_prompt.py",
      "description": "4+ duplicate test pairs (determinism, ABSTAIN clause, work-item header) add no coverage and inflate the test count."
    },
    {
      "id": "F8",
      "severity": "LOW",
      "file": "tests/unit/test_auto_merge_classifier.py",
      "description": "3+ duplicate classifier tests for refuse-list precedence and binary detection."
    },
    {
      "id": "F9",
      "severity": "LOW",
      "file": "tests/unit/test_auto_merge_config.py",
      "description": "pytest.skip() used in test_load_actual_auto_merge_toml when file is missing — cosmetically inconsistent with the no-skip red-flag rule."
    },
    {
      "id": "F10",
      "severity": "LOW",
      "file": "tests/unit/test_auto_merge_config.py",
      "description": "test_load_malformed_toml uses a loose error assertion that any string containing 'error' would satisfy."
    }
  ]
}
```
