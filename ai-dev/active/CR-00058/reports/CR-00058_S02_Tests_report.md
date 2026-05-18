# CR-00058 S02 Tests Report

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S02 Tests (integration)
**Agent**: tests-impl (recovered manually — see "Recovery context" below)
**Status**: Complete

---

## Recovery context

Steps S02 run 1 and run 2 both failed with `Process exited without reporting completion (PID dead)` after ~180 s — the `opencode + minimax/MiniMax-M2.7` agent died mid-task before producing the test file. Both run logs (`ai-dev/logs/CR-00058_S02_run{1,2}.log`) show the agent still in the "read context / list directory" phase when it crashed; no test file was created and `iw step-done` was never called. With the per-step retry budget exhausted, the operator wrote the integration test file directly using the S01-shipped contracts so the workflow can advance to S03.

This report covers the **manual recovery**, not a third opencode run.

## Summary

Created `tests/integration/daemon/test_overlap_gate_policy.py` with the 4 integration tests specified in the prompt. Each test exercises `BatchManager._process_batch` end-to-end against a real PostgreSQL testcontainer (per-test template clone via `pgtestdbpy`), constructs the manager with a tailored `ProjectConfig` policy, and asserts on both `BatchItem.status` transitions and the `DaemonEvent` audit rows.

## Files changed

| File | Purpose |
|------|---------|
| `tests/integration/daemon/test_overlap_gate_policy.py` | 4 new integration tests covering AC1–AC5 of CR-00058 (new file) |

No other files touched — `tests/integration/daemon/__init__.py` was already created in S01.

## Tests

**File**: `tests/integration/daemon/test_overlap_gate_policy.py`

| Test | Behaviour pinned |
|------|------------------|
| `test_default_policy_holds_source_overlap_across_batches` | With the synthesized default (no `.iw-orch.json` `overlap_gate` block), Batch 2's candidate B remains `pending` when it shares `dashboard/foo.py` with Batch 1's in-flight A. Exactly one `item_held_for_scope` event is emitted with `conflicting_globs` containing the file, and zero `item_overlap_allowed_by_policy` events. |
| `test_permissive_allow_releases_overlap_and_emits_audit_event` | With `block_on_overlap=["**/*"]` and `allow_on_overlap=["dashboard/**", ...]`, B transitions out of `pending` (to `setting_up`/`executing` under the `_launch_item` stub). Exactly one `item_overlap_allowed_by_policy` row is emitted with `candidate_item_id=B`, `in_flight_item_ids=[A]`, `dropped_globs` containing `dashboard/foo.py`, and `matched_allow_patterns` listing `dashboard/**`. Zero `item_held_for_scope` rows. |
| `test_per_conflicting_glob_precedence` | A's paths `["dashboard/x.py", "orch/foo.py"]` vs B's `["dashboard/y.py", "orch/foo.py"]` with `allow_on_overlap=["dashboard/**"]`: B stays held because `orch/foo.py` is not allow-listed, and the `item_held_for_scope` event's `conflicting_globs` lists `orch/foo.py` only — `dashboard/y.py` is dropped per the allow filter. |
| `test_dependency_graph_not_affected_by_policy` | An everything-allowed policy (`block=["**/*"]`, `allow=["**/*"]`) must not override the in-batch execution-group ordering. B in `execution_group=1` remains `pending` while A in group 0 is still `executing`, and **neither** `item_held_for_scope` nor `item_overlap_allowed_by_policy` is emitted for B (the gate doesn't run when the dependency check already gates the item). |

### Targeted test run (GREEN)

```
$ uv run pytest tests/integration/daemon/test_overlap_gate_policy.py -v --no-cov

tests/integration/daemon/test_overlap_gate_policy.py::TestOverlapGatePolicy::test_default_policy_holds_source_overlap_across_batches PASSED
tests/integration/daemon/test_overlap_gate_policy.py::TestOverlapGatePolicy::test_permissive_allow_releases_overlap_and_emits_audit_event PASSED
tests/integration/daemon/test_overlap_gate_policy.py::TestOverlapGatePolicy::test_per_conflicting_glob_precedence PASSED
tests/integration/daemon/test_overlap_gate_policy.py::TestOverlapGatePolicy::test_dependency_graph_not_affected_by_policy PASSED

============================== 4 passed in 5.42s ===============================
```

Re-run with `--randomly-seed=99999` — also 4 passed (order-independent).

## TDD RED evidence

The four tests are integration-level coverage of contracts that S01 already shipped, so per the prompt's TDD section we record the *behavioural* failure modes each test would produce against pre-S01 code:

| Test | Pre-S01 behaviour |
|------|-------------------|
| `test_default_policy_holds_source_overlap_across_batches` | Pre-S01, `find_blocking_items` took positional args and ran an implicit `_strip_test_globs` — this test would still pass (default behaviour is unchanged), so it serves as a regression net against accidental default-policy drift. |
| `test_permissive_allow_releases_overlap_and_emits_audit_event` | Pre-S01 there was no `block_patterns`/`allow_patterns` parameter and no `item_overlap_allowed_by_policy` event at all — both the post-launch status assertion and the event-count assertion would have failed with the candidate held (`status == pending`, `len(allowed) == 0`). |
| `test_per_conflicting_glob_precedence` | Pre-S01 the gate had no per-glob allow filter; B would have been held with `conflicting_globs == ["dashboard/y.py", "orch/foo.py"]`, failing the `dashboard/y.py not in conflicting` assertion. |
| `test_dependency_graph_not_affected_by_policy` | Pre-S01 had no policy at all, so this scenario was implicit; the post-S01 risk this test guards is "policy short-circuits dependency ordering" — which would fail the `pending` assertion if a future refactor wired the policy ahead of the group check. |

No code outside the test file was modified — per the prompt, any S01 contract gap would have been a blocker, not a silent patch.

## Pre-flight quality gates

| Gate | Command | Result |
|------|---------|--------|
| format | `uv run ruff format tests/integration/daemon/test_overlap_gate_policy.py` | `1 file left unchanged` ✓ |
| lint | `uv run ruff check tests/integration/daemon/test_overlap_gate_policy.py` | `All checks passed!` ✓ |
| typecheck | `uv run mypy tests/integration/daemon/test_overlap_gate_policy.py` | `Success: no issues found in 1 source file` ✓ |

Project-wide gates (`make format`, `make lint`, `make typecheck`) are run by S09/S10/S11 — not duplicated here.

## Notes

* `_build_manager` takes the project policy explicitly via the `ProjectConfig` dataclass instead of routing through `Project.config["overlap_gate"]` + `_parse_overlap_gate`. The parser path is covered exhaustively by the S01 unit tests in `tests/unit/daemon/test_project_registry_overlap_gate.py` (11 cases), so duplicating it at integration level would be redundant.
* The fixture set includes a private `work_dir` fixture backed by `tempfile.TemporaryDirectory` instead of pytest's built-in `tmp_path`. This is a deliberate workaround for a basetemp race on this dev host: a long-running mutmut sweep in a sibling worktree (CR-00059) re-runs `tests/integration/daemon/` per mutant and its cleanup of `/tmp/pytest-of-<user>` deletes our session's basetemp mid-run, blowing up `tmp_path` setup with `FileNotFoundError`. Switching to a dedicated `TemporaryDirectory` removes the shared dir entirely. The comment in the fixture docstring explains why for future readers.
* `_launch_isolation` patches `check_db_at_head`, `_setup_worktree`, `subprocess.Popen`, `_complete_item`, and the filesystem writes inside `_launch_item` — mirroring the autouse fixture in the existing `test_batch_manager_scope_gate.py` integration file. The gate decision logic and the `DaemonEvent` writes still run for real.

## Blockers

None.
